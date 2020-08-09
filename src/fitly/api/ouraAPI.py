from oura import OuraClient
from ..api.sqlalchemy_declarative import db_connect, db_insert, ouraReadinessSummary, ouraActivitySummary, \
    ouraActivitySamples, ouraSleepSamples, ouraSleepSummary, apiTokens
from sqlalchemy import func, delete
from datetime import datetime, timedelta
import pandas as pd
from ..app import app
import ast
from ..utils import config

client_id = config.get('oura', 'client_id')
client_secret = config.get('oura', 'client_secret')
redirect_uri = config.get('oura', 'redirect_uri')


def current_token_dict():
    try:
        # token_dict = ast.literal_eval(config.get('oura', 'token_dict'))
        session, engine = db_connect()
        token_dict = session.query(apiTokens.tokens).filter(apiTokens.service == 'Oura').first()
        token_dict = ast.literal_eval(token_dict[0]) if token_dict else {}
        engine.dispose()
        session.close()
    except BaseException as e:
        app.server.logger.error(e)
        token_dict = {}

    return token_dict


# Function for auto saving oura token_dict to db
def save_oura_token(token_dict):
    session, engine = db_connect()
    # Delete current key
    session.execute(delete(apiTokens).where(apiTokens.service == 'Oura'))
    # Insert new key
    try:
        session.add(apiTokens(date_utc=datetime.utcnow(), service='Oura', tokens=str(token_dict)))
        session.commit()
    except:
        session.rollback()
    # config.set("oura", "token_dict", str(token_dict))
    # with open('config.ini', 'w') as configfile:
    #     config.write(configfile)
    engine.dispose()
    session.close()


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
#     save_oura_token(auth_client.session.token)


## Provide link for button on settings page
def connect_oura_link(auth_client):
    url = auth_client.authorize_endpoint(scope=["email", "personal", "daily"],
                                         redirect_uri=redirect_uri)
    return url[0]


def pull_readiness_data(oura, days_back=7):
    session, engine = db_connect()
    # Get latest date in db and pull everything after
    start = session.query(func.max(ouraReadinessSummary.report_date))
    engine.dispose()
    session.close()
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
        df_readiness_summary.set_index('report_date', inplace=True)

        # add a new 'primary key' column (hash of the row) on each row which we'll use to cleanup bad data
        ids = pd.DataFrame(df_readiness_summary.apply(lambda x: hash(tuple(x)), axis = 1))
        df_readiness_summary['id'] = ids

        # when we have 2 entries for the same report_date, we want to exclude the first one (lower period_id)
        dupes = df_readiness_summary.groupby('report_date').filter(lambda x: len(x) > 1)
        dupes = (dupes.assign(rn=dupes.groupby(['report_date'])['period_id']
                          .rank(method='first', ascending=True))
                          .query('rn == 1'))

        # we want everything from df_readiness_summary NOT IN dupes
        df_readiness_summary = df_readiness_summary[~df_readiness_summary['id'].isin(dupes['id'])]
        df_readiness_summary = df_readiness_summary.drop(columns=['id'])

        return df_readiness_summary
    else:
        return []


def insert_readiness_data(df_readiness_summary, days_back=7):
    session, engine = db_connect()
    start = session.query(func.max(ouraReadinessSummary.report_date))
    start = '1999-01-01' if start[0][0] is None else datetime.strftime(start[0][0] - timedelta(days=days_back),
                                                                       '%Y-%m-%d')
    # Delete latest dates records from db to ensure values are being overridden from api pull
    try:
        app.server.logger.debug('Deleting >= {} records from oura_readiness_summary'.format(start))
        session.execute(delete(ouraReadinessSummary).where(ouraReadinessSummary.summary_date >= start))
        session.commit()
    except BaseException as e:
        app.server.logger.error(e)

    engine.dispose()
    session.close()

    app.server.logger.debug('Inserting oura readiness summary')
    db_insert(df_readiness_summary, 'oura_readiness_summary')


def pull_activity_data(oura, days_back=7):
    # Activity data updates throughout day and score is generated based off current day (in data)
    # Do not need to generate 'report date'
    session, engine = db_connect()
    # Get latest date in db and pull everything after
    start = session.query(func.max(ouraActivitySummary.summary_date))[0][0]
    engine.dispose()
    session.close()

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
    session, engine = db_connect()
    start = session.query(func.max(ouraActivitySummary.summary_date))[0][0]
    start = '1999-01-01' if start is None else datetime.strftime(start - timedelta(days=days_back), '%Y-%m-%d')

    # Delete latest dates records from db to ensure values are being overridden from api pull
    try:
        app.server.logger.debug('Deleting >= {} records from oura_activity_summary'.format(start))
        session.execute(delete(ouraActivitySummary).where(ouraActivitySummary.summary_date >= start))
        app.server.logger.debug('Deleting >= {} records from oura_activity_samples'.format(start))
        session.execute(delete(ouraActivitySamples).where(ouraActivitySamples.timestamp_local >= start))
        session.commit()
    except BaseException as e:
        app.server.logger.error(e)

    engine.dispose()
    session.close()

    # Insert Activity Summary
    app.server.logger.debug('Inserting oura activity summary')
    try:
        db_insert(df_activity_summary, 'oura_activity_summary')
    except BaseException as e:
        app.server.logger.error(e)

    # Insert Activity Samples
    app.server.logger.debug('Inserting oura activity samples')
    try:
        db_insert(df_activity_samples, 'oura_activity_samples')
    except BaseException as e:
        app.server.logger.error(e)


def pull_sleep_data(oura, days_back=7):
    session, engine = db_connect()
    # Get latest date in db and pull everything after
    start = session.query(func.max(ouraSleepSummary.report_date))[0][0]
    engine.dispose()
    session.close()
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
    session, engine = db_connect()
    start = session.query(func.max(ouraSleepSummary.report_date))[0][0]
    start = '1999-01-01' if start is None else datetime.strftime(start - timedelta(days=days_back), '%Y-%m-%d')

    # Delete latest dates records from db to ensure values are being overridden from api pull
    try:
        app.server.logger.debug('Deleting >= {} records from oura_sleep_summary'.format(start))
        session.execute(delete(ouraSleepSummary).where(ouraSleepSummary.summary_date >= start))
        app.server.logger.debug('Deleting >= {} records from oura_sleep_samples'.format(start))
        session.execute(delete(ouraSleepSamples).where(ouraSleepSamples.summary_date >= start))
        session.commit()
    except BaseException as e:
        app.server.logger.error(e)

    engine.dispose()
    session.close()

    # Insert Sleep Summary
    app.server.logger.debug('Inserting oura sleep summary')
    try:
        db_insert(df_sleep_summary, 'oura_sleep_summary')
    except BaseException as e:
        app.server.logger.error(e)

    # Insert Sleep Samples
    # app.server.logger.debug('Inserting oura sleep samples')
    try:
        db_insert(df_sleep_samples, 'oura_sleep_samples')
    except BaseException as e:
        app.server.logger.error(e)


def pull_oura_data():
    if oura_connected():
        days_back = int(config.get('oura', 'days_back'))

        token_dict = current_token_dict()
        oura = OuraClient(client_id=client_id, client_secret=client_secret, access_token=token_dict['access_token'],
                          refresh_token=token_dict['refresh_token'], refresh_callback=save_oura_token)
        df_readiness_summary = pull_readiness_data(oura, days_back)
        df_activity_summary, df_activity_samples = pull_activity_data(oura, days_back)
        df_sleep_summary, df_sleep_samples = pull_sleep_data(oura, days_back)

        insert_readiness_data(df_readiness_summary, days_back)
        insert_activity_data(df_activity_summary, df_activity_samples, days_back)
        insert_sleep_data(df_sleep_summary, df_sleep_samples, days_back)

        return df_sleep_summary.index.max() == df_readiness_summary.index.max()  # == df_activity_summary.index.max()

    # Oura API returns times (bedtime_start, bedtime_end etc. in the timezone of the location where went to sleep.
    # Do not need to convert to UTC because we want the time we went to sleep wherever we went to sleep, not necessarily always EST
    # API also returns what the timezone was, so storing in MySQL as datetime is not an issue as we can always convert back by adding
    # [timezone] minuts to the datetime that is stored to get to UTC, and then convert to anywhere else if necessary
