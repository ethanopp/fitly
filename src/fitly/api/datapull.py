from ..api.stravaApi import get_strava_client, strava_connected
from ..api.ouraAPI import pull_oura_data
from ..api.withingsAPI import pull_withings_data
from ..api.fitbodAPI import pull_fitbod_data
from ..api.pelotonApi import get_peloton_class_names
from ..api.sqlalchemy_declarative import *
from sqlalchemy import func, delete
import datetime
from ..api.fitlyAPI import *
import pandas as pd
from ..app import app
from ..utils import config, withings_credentials_supplied, oura_credentials_supplied, nextcloud_credentials_supplied


def latest_refresh():
    latest_date = app.session.query(func.max(dbRefreshStatus.timestamp_utc))[0][0]

    app.session.remove()
    return latest_date


def refresh_database(refresh_method='system', truncate=False, truncateDate=None):
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    processing = app.session.query(dbRefreshStatus).filter(dbRefreshStatus.refresh_method == 'processing').first()

    app.session.remove()

    if not processing:
        try:
            # If athlete settings are defined
            if athlete_info.name and athlete_info.birthday and athlete_info.sex and athlete_info.weight_lbs and athlete_info.resting_hr and athlete_info.run_ftp and athlete_info.ride_ftp:
                # Insert record into table for 'processing'

                run_time = datetime.utcnow()
                record = dbRefreshStatus(timestamp_utc=run_time, truncate=truncate, refresh_method='processing')
                # Insert and commit
                try:
                    app.session.add(record)
                    app.session.commit()
                    app.server.logger.debug('Inserting processing records into db_refresh...')
                except BaseException as e:
                    app.session.rollback()
                    app.server.logger.error('Failed to insert processing record into db_refresh :', str(e))

                app.session.remove()

                # If either truncate parameter is passed
                if truncate or truncateDate:

                    # If only truncating past a certain date
                    if truncateDate:
                        try:
                            app.server.logger.debug('Truncating strava_summary')
                            app.session.execute(
                                delete(stravaSummary).where(stravaSummary.start_date_utc >= truncateDate))
                            app.server.logger.debug('Truncating strava_samples')
                            app.session.execute(
                                delete(stravaSamples).where(stravaSamples.timestamp_local >= truncateDate))
                            app.server.logger.debug('Truncating strava_best_samples')
                            app.session.execute(
                                delete(stravaBestSamples).where(stravaBestSamples.timestamp_local >= truncateDate))
                            app.server.logger.debug('Truncating oura_readiness_summary')
                            app.session.execute(
                                delete(ouraReadinessSummary).where(ouraReadinessSummary.report_date >= truncateDate))
                            app.server.logger.debug('Truncating oura_sleep_summary')
                            app.session.execute(
                                delete(ouraSleepSummary).where(ouraSleepSummary.report_date >= truncateDate))
                            app.server.logger.debug('Truncating oura_sleep_samples')
                            app.session.execute(
                                delete(ouraSleepSamples).where(ouraSleepSamples.report_date >= truncateDate))
                            app.server.logger.debug('Truncating oura_activity_summary')
                            app.session.execute(
                                delete(ouraActivitySummary).where(ouraActivitySummary.summary_date >= truncateDate))
                            app.server.logger.debug('Truncating oura_activity_samples')
                            app.session.execute(
                                delete(ouraActivitySamples).where(ouraActivitySamples.timestamp_local >= truncateDate))
                            app.server.logger.debug('Truncating hrv_workout_step_log')
                            app.session.execute(delete(hrvWorkoutStepLog).where(hrvWorkoutStepLog.date >= truncateDate))
                            app.server.logger.debug('Truncating withings')
                            app.session.execute(delete(withings).where(withings.date_utc >= truncateDate))
                            app.session.commit()
                        except BaseException as e:
                            app.session.rollback()
                            app.server.logger.error(e)
                    else:
                        try:
                            app.server.logger.debug('Truncating strava_summary')
                            app.session.execute(delete(stravaSummary))
                            app.server.logger.debug('Truncating strava_samples')
                            app.session.execute(delete(stravaSamples))
                            app.server.logger.debug('Truncating strava_best_samples')
                            app.session.execute(delete(stravaBestSamples))
                            app.server.logger.debug('Truncating oura_readiness_summary')
                            app.session.execute(delete(ouraReadinessSummary))
                            app.server.logger.debug('Truncating oura_sleep_summary')
                            app.session.execute(delete(ouraSleepSummary))
                            app.server.logger.debug('Truncating oura_sleep_samples')
                            app.session.execute(delete(ouraSleepSamples))
                            app.server.logger.debug('Truncating oura_activity_summary')
                            app.session.execute(delete(ouraActivitySummary))
                            app.server.logger.debug('Truncating oura_activity_samples')
                            app.session.execute(delete(ouraActivitySamples))
                            app.server.logger.debug('Truncating hrv_workout_step_log')
                            app.session.execute(delete(hrvWorkoutStepLog))
                            app.server.logger.debug('Truncating withings')
                            app.session.execute(delete(withings))
                            app.server.logger.debug('Truncating fitbod')
                            app.session.execute(delete(fitbod))
                            app.session.commit()
                        except BaseException as e:
                            app.session.rollback()
                            app.server.logger.error(e)

                    app.session.remove()

                ### Pull Weight Data ###

                # If withings credentials in config.ini, populate withings table
                if withings_credentials_supplied:
                    try:
                        app.server.logger.info('Pulling withings data...')
                        pull_withings_data()
                        withings_status = 'Successful'
                    except BaseException as e:
                        app.server.logger.error('Error pulling withings data: {}'.format(e))
                        withings_status = str(e)
                else:
                    withings_status = 'No Credentials'

                ### Pull Fitbod Data ###

                # If nextcloud credentials in config.ini, pull fitbod data from nextcloud location
                if nextcloud_credentials_supplied:
                    try:
                        app.server.logger.info('Pulling fitbod data...')
                        pull_fitbod_data()
                        fitbod_status = 'Successful'
                    except BaseException as e:
                        app.server.logger.error('Error pulling fitbod data: {}'.format(e))
                        fitbod_status = str(e)
                else:
                    fitbod_status = 'No Credentials'

                ### Pull Oura Data ###

                if oura_credentials_supplied:
                    # Pull Oura Data before strava because resting heart rate used in strava sample heart rate zones
                    try:
                        app.server.logger.info('Pulling oura data...')
                        oura_status = pull_oura_data()
                        oura_status = 'Successful' if oura_status else 'Oura cloud not yet updated'
                    except BaseException as e:
                        app.server.logger.error('Error pulling oura data: {}'.format(e))
                        oura_status = str(e)
                else:
                    oura_status = 'No Credentials'

                ### Pull Strava Data ###

                # Only pull strava data if oura cloud has been updated with latest day, or no oura credentials so strava will use athlete static resting hr
                if oura_status == 'Successful' or oura_status == 'No Credentials':
                    try:
                        app.server.logger.info('Pulling strava data...')

                        if strava_connected():
                            athlete_id = 1  # TODO: Make this dynamic if ever expanding to more users
                            client = get_strava_client()
                            after = config.get('strava', 'activities_after_date')
                            activities = client.get_activities(after=after,
                                                               limit=0)  # Use after to sort from oldest to newest

                            athlete_info = app.session.query(athlete).filter(athlete.athlete_id == athlete_id).first()
                            min_non_warmup_workout_time = athlete_info.min_non_warmup_workout_time
                            # Loop through the activities, and create a dict of the dataframe stream data of each activity
                            db_activities = pd.read_sql(
                                sql=app.session.query(stravaSummary.activity_id).filter(
                                    stravaSummary.athlete_id == athlete_id).distinct(
                                    stravaSummary.activity_id).statement,
                                con=engine)

                            app.session.remove()
                            new_activities = []
                            for act in activities:
                                # If not already in db, parse and insert
                                if act.id not in db_activities['activity_id'].unique():
                                    new_activities.append(FitlyActivity(act))
                                    app.server.logger.info('New Workout found: "{}"'.format(act.name))
                            # If new workouts found, analyze and insert
                            if len(new_activities) > 0:
                                for fitly_act in new_activities:
                                    fitly_act.stravaScrape(athlete_id=athlete_id)
                            # Only run hrv training workflow if oura connection available to use hrv data
                            if oura_status == 'Successful':
                                hrv_training_workflow(min_non_warmup_workout_time=min_non_warmup_workout_time)

                        app.server.logger.debug('stravaScrape() complete...')
                        strava_status = 'Successful'
                    except BaseException as e:
                        app.server.logger.error('Error pulling strava data: {}'.format(e))
                        strava_status = str(e)
                else:
                    app.server.logger.info('Oura cloud not yet updated. Waiting to pull Strava data')
                    strava_status = 'Awaiting oura cloud update'

                app.session.query(dbRefreshStatus).filter(dbRefreshStatus.timestamp_utc == run_time).first().update([
                    {dbRefreshStatus.oura_status: oura_status}, {dbRefreshStatus.fitbod_status: fitbod_status},
                    {dbRefreshStatus.strava_status: strava_status}, {dbRefreshStatus.withings_status: withings_status},
                    {dbRefreshStatus.refresh_method: refresh_method}])

                # Refresh peloton class types local json file
                if peloton_credentials_supplied:
                    get_peloton_class_names()

                app.server.logger.info('Refresh Complete')

                app.session.remove()

                return run_time

            else:
                app.server.logger.info('Please define all athlete settings prior to refreshing data')
        except:
            # Just in case the job fails, remove any processing records that may have been added to audit log as to not lock the next job

            app.session.query(dbRefreshStatus).filter(dbRefreshStatus.refresh_method == 'processing').delete()
            app.session.commit()

            app.session.remove()
    else:
        if refresh_method == 'manual':
            app.server.logger.info('Database is already running a refresh job')
