from oura import OuraClient
from ..api.sqlalchemy_declarative import ouraReadinessSummary, ouraActivitySummary, \
    ouraActivitySamples, ouraSleepSamples, ouraSleepSummary, apiTokens
from ..api.database import engine
from sqlalchemy import func, delete
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from ..app import app
import ast
from ..utils import config
from functools import reduce
import pickle

client_id = config.get('oura', 'client_id')
client_secret = config.get('oura', 'client_secret')
redirect_uri = config.get('oura', 'redirect_uri')


def current_token_dict():
    try:
        token_dict = app.session.query(apiTokens.tokens).filter(apiTokens.service == 'Oura').first().tokens
        token_pickle = pickle.loads(token_dict)
        app.session.remove()
    except BaseException as e:
        app.server.logger.error(e)
        token_pickle = {}

    return token_pickle


# Function for auto saving oura token_dict to db
def save_oura_token(token_dict):
    # Delete current key
    app.session.execute(delete(apiTokens).where(apiTokens.service == 'Oura'))
    # Insert new key
    try:
        app.session.add(apiTokens(date_utc=datetime.utcnow(), service='Oura', tokens=pickle.dumps(token_dict)))
        app.session.commit()
    except:
        app.session.rollback()

    app.session.remove()


def oura_connected():
    token_dict = current_token_dict()
    try:
        if token_dict:
            oura = OuraClient(client_id=client_id, client_secret=client_secret, access_token=token_dict['access_token'],
                              refresh_token=token_dict['refresh_token'], refresh_callback=save_oura_token)
            app.server.logger.debug('Oura Connected')
            return True
    except BaseException as e:
        app.server.logger.error('Oura not connected')
        app.server.logger.error(e)
        return False


## For manual pulling of tokens
# def connect_oura():
#     # IF refresh tokens required ##
#     auth_client = OuraOAuth2Client(client_id=client_id, client_secret=client_secret)
#     url = auth_client.authorize_endpoint(scope=["email", "personal", "daily"],
#                                          redirect_uri=redirect_uri)
#     print(url)
#     auth_code = input('code')
#     ###
#     auth_client.fetch_access_token(auth_code)
#
#     ## Take code and manually test with OuraClient()
#     save_oura_token(auth_client.app.session.token)


## Provide link for button on settings page
def connect_oura_link(auth_client):
    url = auth_client.authorize_endpoint(scope=["email", "personal", "daily"],
                                         redirect_uri=redirect_uri)
    return url[0]


def pull_readiness_data(oura, days_back=7):
    # Get latest date in db and pull everything after
    start = app.session.query(func.max(ouraReadinessSummary.report_date))

    app.session.remove()
    start = '1999-01-01' if start[0][0] is None else datetime.strftime(start[0][0] - timedelta(days=days_back),
                                                                       '%Y-%m-%d')

    app.server.logger.debug('Pulling readiness from max date in oura_readiness_summary {}'.format(start))
    oura_data = oura.readiness_summary(start=start)['readiness']

    if len(oura_data) > 0:
        df_readiness_summary = pd.DataFrame.from_dict(oura_data)
        # Readiness shows the 'summary' of the previous day.
        # To align with charts when filtering on date use readiness summary_date + 1 day
        df_readiness_summary['report_date'] = (
                pd.to_datetime(df_readiness_summary['summary_date']) + timedelta(days=1)).dt.date

        # Only take max period_id from readiness data (don't want naps in our readiness data screwing up main daily scores)
        df_readiness_summary = df_readiness_summary.loc[
            df_readiness_summary.reset_index().groupby(['summary_date'])['period_id'].idxmax()]

        df_readiness_summary.set_index('report_date', inplace=True)

        return df_readiness_summary
    else:
        return []


def insert_readiness_data(df_readiness_summary, days_back=7):
    start = app.session.query(func.max(ouraReadinessSummary.report_date))
    start = '1999-01-01' if start[0][0] is None else datetime.strftime(start[0][0] - timedelta(days=days_back),
                                                                       '%Y-%m-%d')
    # Delete latest dates records from db to ensure values are being overridden from api pull
    try:
        app.server.logger.debug('Deleting >= {} records from oura_readiness_summary'.format(start))
        app.session.execute(delete(ouraReadinessSummary).where(ouraReadinessSummary.summary_date >= start))
        app.session.commit()
    except BaseException as e:
        app.server.logger.error(e)

    app.session.remove()

    app.server.logger.debug('Inserting oura readiness summary')
    df_readiness_summary.to_sql('oura_readiness_summary', engine, if_exists='append', index=True)


def pull_activity_data(oura, days_back=7):
    # Activity data updates throughout day and score is generated based off current day (in data)
    # Do not need to generate 'report date'

    # Get latest date in db and pull everything after
    start = app.session.query(func.max(ouraActivitySummary.summary_date))[0][0]

    app.session.remove()

    start = '1999-01-01' if start is None else datetime.strftime(start - timedelta(days=days_back), '%Y-%m-%d')

    app.server.logger.debug('Pulling activity from max date in oura_activity_summary {}'.format(start))
    oura_data = oura.activity_summary(start=start)['activity']

    if len(oura_data) > 0:
        df_activity_summary = pd.DataFrame.from_dict(oura_data)
        df_activity_summary['summary_date'] = pd.to_datetime(df_activity_summary['summary_date']).dt.date
        df_activity_summary.set_index('summary_date', inplace=True)
        df_activity_summary['day_end_local'] = pd.to_datetime(
            df_activity_summary['day_end']).apply(lambda x: x.replace(tzinfo=None))
        df_activity_summary['day_start_local'] = pd.to_datetime(
            df_activity_summary['day_start']).apply(lambda x: x.replace(tzinfo=None))
        df_activity_summary = df_activity_summary.drop(columns=['met_1min', 'day_end', 'day_start'], axis=1)

        # Generate Activity Samples
        df_1min_list, df_5min_list = [], []
        for x in oura_data:
            # build 1 min metrics df
            df_1min = pd.Series(x.get('met_1min'), name='met_1min').to_frame()
            df_1min['timestamp_local'] = pd.to_datetime(x.get('day_start')) + pd.to_timedelta(df_1min.index, unit='m')
            df_1min = df_1min.set_index('timestamp_local')
            # Remove timezone info from date, we are just storing whatever the local time was, where the person was
            df_1min.index = df_1min.index.tz_localize(None)
            df_1min['summary_date'] = pd.to_datetime(x.get('summary_date')).date()
            df_1min_list.append(df_1min)

            # build 5 min metrics df
            df_5min = pd.Series([int(y) for y in x.get('class_5min')], name='class_5min').to_frame()
            df_5min['class_5min_desc'] = df_5min['class_5min'].fillna('5').astype('str').map(
                {'0': 'Rest', '1': 'Inactive', '2': 'Low', '3': 'Medium', '4': 'High', '5': 'Non-Wear'})
            df_5min.index += 1
            df_5min['timestamp_local'] = (pd.to_datetime(x.get('day_start')) + pd.to_timedelta(df_5min.index * 5,
                                                                                               unit='m')) - pd.to_timedelta(
                5, unit='m')
            df_5min = df_5min.set_index('timestamp_local')
            # Remove timezone info from date, we are just storing whatever the local time was, where the person was
            df_5min.index = df_5min.index.tz_localize(None)
            df_5min['summary_date'] = pd.to_datetime(x.get('summary_date')).date()
            df_5min_list.append(df_5min)

        df_1min = pd.concat(df_1min_list)
        df_5min = pd.concat(df_5min_list)

        df_activity_samples = df_1min.merge(df_5min, how='left', left_index=True, right_index=True)
        df_activity_samples['summary_date'] = df_activity_samples['summary_date_x']
        df_activity_samples = df_activity_samples.drop(columns=['summary_date_x', 'summary_date_y'], axis=1)

        return df_activity_summary, df_activity_samples
    else:
        return [], []


def insert_activity_data(df_activity_summary, df_activity_samples, days_back=7):
    start = app.session.query(func.max(ouraActivitySummary.summary_date))[0][0]
    start = '1999-01-01' if start is None else datetime.strftime(start - timedelta(days=days_back), '%Y-%m-%d')

    # Delete latest dates records from db to ensure values are being overridden from api pull
    try:
        app.server.logger.debug('Deleting >= {} records from oura_activity_summary'.format(start))
        app.session.execute(delete(ouraActivitySummary).where(ouraActivitySummary.summary_date >= start))
        app.server.logger.debug('Deleting >= {} records from oura_activity_samples'.format(start))
        app.session.execute(delete(ouraActivitySamples).where(ouraActivitySamples.timestamp_local >= start))
        app.session.commit()
    except BaseException as e:
        app.server.logger.error(e)

    app.session.remove()

    # Insert Activity Summary
    app.server.logger.debug('Inserting oura activity summary')
    try:
        df_activity_summary.to_sql('oura_activity_summary', engine, if_exists='append', index=True)


    except BaseException as e:
        app.server.logger.error(e)

    # Insert Activity Samples
    app.server.logger.debug('Inserting oura activity samples')
    try:
        df_activity_samples.to_sql('oura_activity_samples', engine, if_exists='append', index=True)

    except BaseException as e:
        app.server.logger.error(e)


def pull_sleep_data(oura, days_back=7):
    # Get latest date in db and pull everything after
    start = app.session.query(func.max(ouraSleepSummary.report_date))[0][0]

    app.session.remove()
    start = '1999-01-01' if start is None else datetime.strftime(start - timedelta(days=days_back), '%Y-%m-%d')

    app.server.logger.debug('Pulling sleep from max date in oura_sleep_summary {}'.format(start))
    oura_data = oura.sleep_summary(start=start)['sleep']

    if len(oura_data) > 0:
        # Sleep Summary
        df_sleep_summary = pd.DataFrame.from_dict(oura_data)
        # Sleep shows the 'summary' of the previous day.
        # To align with charts when filtering on date use readiness summary_date + 1 day
        df_sleep_summary['report_date'] = (pd.to_datetime(df_sleep_summary['summary_date']) + timedelta(days=1)).dt.date
        df_sleep_summary = df_sleep_summary.set_index('report_date')
        # Remove timestamps from bedtimes as we want whatever the time was locally
        df_sleep_summary['bedtime_end_local'] = pd.to_datetime(
            df_sleep_summary['bedtime_end']).apply(lambda x: x.replace(tzinfo=None))
        df_sleep_summary['bedtime_start_local'] = pd.to_datetime(
            df_sleep_summary['bedtime_start']).apply(lambda x: x.replace(tzinfo=None))

        df_sleep_summary = df_sleep_summary.drop(columns=['rmssd_5min', 'hr_5min', 'bedtime_end', 'bedtime_start'],
                                                 axis=1)

        # Sleep Samples
        df_samples_list = []
        for x in oura_data:
            df = pd.concat(
                [pd.Series(x.get('hr_5min'), name='hr_5min'), pd.Series(x.get('rmssd_5min'), name='rmssd_5min'),
                 pd.Series([int(y) for y in x.get('hypnogram_5min')], name='hypnogram_5min')],
                axis=1)
            df['hypnogram_5min_desc'] = df['hypnogram_5min'].map(
                {1: 'Deep', 2: 'Light', 3: 'REM', 4: 'Awake'})

            df.index += 1
            df['timestamp_local'] = (pd.to_datetime(x.get('bedtime_start')) + pd.to_timedelta(df.index * 5,
                                                                                              unit='m')) - pd.to_timedelta(
                5, unit='m')

            df['summary_date'] = pd.to_datetime(x.get('summary_date')).date()
            df['report_date'] = df['summary_date'] + timedelta(days=1)
            df = df.set_index('timestamp_local')
            # Remove timezone info from date, we are just storing whatever the local time was, where the person was
            df.index = df.index.tz_localize(None)
            df_samples_list.append(df)

        df_sleep_samples = pd.concat(df_samples_list)

        return df_sleep_summary, df_sleep_samples
    else:
        return [], []


def insert_sleep_data(df_sleep_summary, df_sleep_samples, days_back=7):
    start = app.session.query(func.max(ouraSleepSummary.report_date))[0][0]
    start = '1999-01-01' if start is None else datetime.strftime(start - timedelta(days=days_back), '%Y-%m-%d')

    # Delete latest dates records from db to ensure values are being overridden from api pull
    try:
        app.server.logger.debug('Deleting >= {} records from oura_sleep_summary'.format(start))
        app.session.execute(delete(ouraSleepSummary).where(ouraSleepSummary.summary_date >= start))
        app.server.logger.debug('Deleting >= {} records from oura_sleep_samples'.format(start))
        app.session.execute(delete(ouraSleepSamples).where(ouraSleepSamples.summary_date >= start))
        app.session.commit()
    except BaseException as e:
        app.server.logger.error(e)

    app.session.remove()

    # Insert Sleep Summary
    app.server.logger.debug('Inserting oura sleep summary')
    try:
        df_sleep_summary.to_sql('oura_sleep_summary', engine, if_exists='append', index=True)

    except BaseException as e:
        app.server.logger.error(e)

    # Insert Sleep Samples
    # app.server.logger.debug('Inserting oura sleep samples')
    try:
        df_sleep_samples.to_sql('oura_sleep_samples', engine, if_exists='append', index=True)

    except BaseException as e:
        app.server.logger.error(e)


def generate_oura_correlations(lookback_days=180):
    '''
    Generates correlations of oura metrics

    '''
    lookback = pd.to_datetime(datetime.today() - timedelta(days=lookback_days)).date()

    activity = pd.read_sql(
        sql=app.session.query(ouraActivitySummary).filter(ouraActivitySummary.summary_date >= lookback).statement,
        con=engine,
        index_col='summary_date').sort_index(
        ascending=True)
    # Drop columns we don't want to correlate over
    activity.drop(
        columns=['inactivity_alerts', 'met_min_high', 'met_min_inactive', 'met_min_low', 'met_min_medium',
                 'rest_mode_state', 'score_meet_daily_targets', 'score_move_every_hour', 'score_recovery_time',
                 'score_stay_active', 'score_training_frequency', 'score_training_volume', 'target_calories',
                 'target_km', 'target_miles', 'to_target_km', 'to_target_miles', 'timezone'], inplace=True)
    activity = activity.add_prefix('Activity_')

    readiness = pd.read_sql(
        sql=app.session.query(ouraReadinessSummary).filter(ouraReadinessSummary.summary_date >= lookback).statement,
        con=engine,
        index_col='summary_date').sort_index(
        ascending=True)
    readiness.drop(
        columns=[
            'period_id', 'score_activity_balance', 'score_previous_day', 'score_previous_night', 'score_recovery_index',
            'score_resting_hr', 'score_sleep_balance', 'score_temperature', 'score_hrv_balance', 'rest_mode_state'],
        inplace=True)
    readiness = readiness.add_prefix('Readiness_')

    sleep = pd.read_sql(
        sql=app.session.query(ouraSleepSummary).filter(ouraSleepSummary.summary_date >= lookback).statement,
        con=engine,
        index_col='summary_date').sort_index(
        ascending=True)

    sleep.drop(
        columns=['bedtime_end_delta', 'is_longest', 'midpoint_at_delta', 'period_id', 'score_alignment', 'score_deep',
                 'score_disturbances', 'score_efficiency', 'score_latency', 'score_rem', 'score_total',
                 'temperature_delta', 'temperature_trend_deviation',
                 'timezone'],
        inplace=True)

    sleep = sleep.add_prefix('Sleep_')

    friendly_names = {'Activity_average_met': 'Average METs',
                      'Activity_cal_active': 'Activity burn',
                      'Activity_cal_total': 'Total burn',
                      'Activity_daily_movement': 'Walking equivalent',
                      'Activity_high': 'High activity time',
                      'Activity_inactive': 'Inactive time',
                      'Activity_low': 'Low activity time',
                      'Activity_medium': 'Med activity time',
                      'Activity_non_wear': 'Non-wear time',
                      'Activity_rest': 'Rest time',
                      'Activity_score': 'Activity score',
                      'Activity_steps': 'Steps',
                      'Activity_total': 'Total activity time',
                      'Readiness_score': 'Readiness score',
                      'Sleep_awake': 'Time awake in bed',
                      'Sleep_bedtime_start_delta': 'Late to bedtime',
                      'Sleep_breath_average': 'Respiratory rate',
                      'Sleep_deep': 'Deep sleep',
                      'Sleep_duration': 'Time in bed',
                      'Sleep_efficiency': 'Sleep efficiency',
                      'Sleep_hr_average': 'Average HR',
                      'Sleep_hr_lowest': 'Lowest HR',
                      'Sleep_light': 'Light sleep',
                      'Sleep_midpoint_time': 'Sleep midpoint',
                      'Sleep_onset_latency': 'Sleep latency',
                      'Sleep_rem': 'REM sleep',
                      'Sleep_restless': 'Restlessness',
                      'Sleep_rmssd': 'Average HRV',
                      'Sleep_score': 'Sleep score',
                      'Sleep_temperature_deviation': 'Temp. deviation',
                      'Sleep_total': 'Total sleep'}

    dfs = [sleep, readiness, activity]
    df = reduce(lambda left, right: pd.merge(left, right, left_index=True, right_index=True), dfs)

    df.columns = df.columns.to_series().map(friendly_names)

    # Create Prev/Next day for all columns
    for col in friendly_names.values():
        df[col + ' (prev)'] = df[col].shift(1)
        df[col + ' (next)'] = df[col].shift(-1)

    df = df.corr().replace(1, np.nan)
    # Store lookback days that was used for filtering historic data to run correlation on
    df['rolling_days'] = lookback_days
    df.index.name = 'Metric'

    # df.to_sql('correlations', engine, if_exists='replace', index=True)

    app.session.remove()
    return df


def top_n_correlations(n, column, days=180):
    df = generate_oura_correlations(lookback_days=days)
    positive = df[column].nlargest(n).reset_index()
    positive.columns = ['Positive', 'Pos Corr Coef.']

    negative = df[column].nsmallest(n).reset_index()
    negative.columns = ['Negative', 'Neg Corr Coef.']

    return pd.merge(positive, negative, left_index=True, right_index=True)


def pull_oura_data():
    if oura_connected():
        days_back = int(config.get('oura', 'days_back'))

        token_dict = current_token_dict()
        oura = OuraClient(client_id=client_id, client_secret=client_secret, access_token=token_dict['access_token'],
                          refresh_token=token_dict['refresh_token'], refresh_callback=save_oura_token)
        df_readiness_summary = pull_readiness_data(oura, days_back)
        df_readiness_summary.to_csv('readiness.csv', sep=',')
        df_activity_summary, df_activity_samples = pull_activity_data(oura, days_back)
        df_sleep_summary, df_sleep_samples = pull_sleep_data(oura, days_back)

        insert_readiness_data(df_readiness_summary, days_back)
        insert_activity_data(df_activity_summary, df_activity_samples, days_back)
        insert_sleep_data(df_sleep_summary, df_sleep_samples, days_back)

        # # Generate correlation table - Depricated, no longer storing in table
        # generate_oura_correlations(lookback_days=9999)

        return df_sleep_summary.index.max() == df_readiness_summary.index.max()  # == df_activity_summary.index.max()

    # Oura API returns times (bedtime_start, bedtime_end etc. in the timezone of the location where went to sleep.
    # Do not need to convert to UTC because we want the time we went to sleep wherever we went to sleep, not necessarily always EST
    # API also returns what the timezone was, so storing in MySQL as datetime is not an issue as we can always convert back by adding
    # [timezone] minuts to the datetime that is stored to get to UTC, and then convert to anywhere else if necessary
