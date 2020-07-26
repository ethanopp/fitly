from datetime import datetime, timedelta
import numpy as np
from ..api.sqlalchemy_declarative import db_connect, ouraSleepSummary, withings, athlete, db_insert, stravaSummary, \
    fitbod, hrvWorkoutStepLog
from sqlalchemy import func, cast, Date
from sweat.io.models.dataframes import WorkoutDataFrame, Athlete
from sweat.pdm import critical_power
from sweat.metrics.core import weighted_average_power
from sweat.metrics.power import *
import stravalib
from ..api.stravaApi import get_strava_client
from stravalib import unithelper
from ..api.pelotonApi import peloton_mapping_df, roundTime, set_peloton_workout_recommendations
from ..api.strydAPI import get_stryd_df_summary
from dateutil.relativedelta import relativedelta
from ..app import app
from ..utils import peloton_credentials_supplied, stryd_credentials_supplied, config

types = ['time', 'latlng', 'distance', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp',
         'moving', 'grade_smooth']


def calctime(time_sec, startdate):
    try:
        timestamp = startdate + timedelta(seconds=int(time_sec))
    except BaseException as e:
        timestamp = startdate
    return timestamp


class FitlyActivity(stravalib.model.Activity):

    def __new__(cls, activity):
        activity.__class__ = FitlyActivity
        return activity

    def stravaScrape(self, athlete_id):
        # # Set up athlete for the workout
        app.server.logger.debug('Activity id "{}": Assigning athlete id {}'.format(self.id, athlete_id))
        self.assign_athlete(athlete_id)
        # Update strava names of peloton workouts
        if peloton_credentials_supplied:
            app.server.logger.debug('Activity id "{}": Pulling peloton title'.format(self.id))
            self.get_peloton_workout_title()
        # Build activity samples df
        app.server.logger.debug('Activity id "{}": Building df_samples'.format(self.id))
        self.build_df_samples()
        # Build activity summary df
        app.server.logger.debug('Activity id "{}": Building df_summary'.format(self.id))
        self.build_df_summary()
        # Get FTP
        app.server.logger.debug('Activity id "{}": Pulling ftp'.format(self.id))
        self.get_ftp()
        # Get most recent resting heart rate
        app.server.logger.debug('Activity id "{}": Pulling resting hr'.format(self.id))
        self.get_rest_hr()
        # Get most recent weight
        app.server.logger.debug('Activity id "{}": Pulling weight'.format(self.id))
        self.get_weight()
        # Calculate power zones
        app.server.logger.debug('Activity id "{}": Calculating power zones'.format(self.id))
        self.calculate_power_zones()
        # Calculate heartrate zones
        app.server.logger.debug('Activity id "{}": Calculating heartrate zones'.format(self.id))
        self.calculate_heartate_zones()
        # Calculate zone intensities
        app.server.logger.debug('Activity id "{}": Calculating zones intensities'.format(self.id))
        self.calculate_zone_intensities()
        # Get summary analytics
        app.server.logger.debug('Activity id "{}": Calculating summary analytics'.format(self.id))
        self.get_summary_analytics()
        # Write strava_best_samples
        app.server.logger.debug('Activity id "{}": Writing mean max power to DB'.format(self.id))
        self.compute_mean_max_power(dbinsert=True)
        # Write df_summary and df_samples to db
        app.server.logger.debug('Activity id "{}": Writing df_summary and df_samples to DB'.format(self.id))
        self.write_dfs_to_db()

    def assign_athlete(self, athlete_id):
        session, engine = db_connect()
        self.Athlete = session.query(athlete).filter(athlete.athlete_id == athlete_id).first()
        engine.dispose()
        session.close()

        self.hearrate_zones = {
            1: float(self.Athlete.hr_zone_threshold_1),
            2: float(self.Athlete.hr_zone_threshold_2),
            3: float(self.Athlete.hr_zone_threshold_3),
            4: float(self.Athlete.hr_zone_threshold_4)
        }
        if 'ride' in self.type.lower():
            self.power_zones = {
                1: float(self.Athlete.cycle_power_zone_threshold_1),
                2: float(self.Athlete.cycle_power_zone_threshold_2),
                3: float(self.Athlete.cycle_power_zone_threshold_3),
                4: float(self.Athlete.cycle_power_zone_threshold_4),
                5: float(self.Athlete.cycle_power_zone_threshold_5),
                6: float(self.Athlete.cycle_power_zone_threshold_6)
            }
        elif 'run' in self.type.lower() or 'walk' in self.type.lower():
            self.power_zones = {
                1: float(self.Athlete.run_power_zone_threshold_1),
                2: float(self.Athlete.run_power_zone_threshold_2),
                3: float(self.Athlete.run_power_zone_threshold_3),
                4: float(self.Athlete.run_power_zone_threshold_4)
            }

    def get_peloton_workout_title(self, write_to_strava=True):
        ## Assumes recorded ride is started within 5 minutes of peloton video
        client = get_strava_client()
        peloton_df = peloton_mapping_df()
        start = roundTime(self.start_date)
        activity = peloton_df[
            (peloton_df['start'] >= (start - timedelta(minutes=5))) & (
                    peloton_df['start'] <= (start + timedelta(minutes=5)))]
        if len(activity) > 0:
            self.peloton_title = activity.name.values[0]
            self.name = self.peloton_title if len(self.peloton_title) > 0 else self.name
            if write_to_strava and client.get_activity(activity_id=self.id).name != self.peloton_title:
                client.update_activity(activity_id=self.id, name=self.peloton_title)

    def get_rest_hr(self):
        # TODO: Build this out so hearrate data can be pulled from other data sources
        # Assign rhr to activities by their start date
        session, engine = db_connect()
        # Try grabbing last resting heartrate from oura
        hr_lowest = session.query(ouraSleepSummary.hr_lowest).filter(
            ouraSleepSummary.report_date <= self.start_date.date()).order_by(
            ouraSleepSummary.report_date.desc()).first()
        # If activity is prior to first oura data record, use first oura data record
        if not hr_lowest:
            hr_lowest = \
                session.query(ouraSleepSummary.hr_lowest).order_by(ouraSleepSummary.report_date.asc()).first()
        engine.dispose()
        session.close()

        if hr_lowest:
            self.hr_lowest = hr_lowest[0]
        # Resort to manaully entered static athlete resting heartrate if no data source to pull from
        else:
            self.hr_lowest = self.Athlete.resting_hr

    def get_weight(self):
        # TODO: Build this out so weight data can be pulled from other data sources
        session, engine = db_connect()
        # Try grabbing last weight in withings before current workout
        weight = session.query(withings.weight).filter(withings.date_utc <= self.start_date).order_by(
            withings.date_utc.desc()).first()
        # Else try getting most recent weight from withings
        if not weight:
            weight = session.query(withings.weight).order_by(withings.date_utc.asc()).first()

        engine.dispose()
        session.close()

        if weight:
            weight = float(weight[0])
        # If no weights in withings, resort to manually entered static weight from athlete table

        if not weight:
            weight = self.Athlete.weight_lbs

        self.weight = weight
        self.kg = weight * 0.453592

    def get_ftp(
            self):  # TODO: Update with auto calculated critical power so users do not have to flag (or take) FTP tests
        self.stryd_metrics = []
        if 'run' in self.type.lower() or 'walk' in self.type.lower():
            # If stryd credentials in config, grab ftp
            if stryd_credentials_supplied:
                stryd_df = get_stryd_df_summary()
                start = roundTime(self.start_date_local)
                # Save stryd df for current workout to instance to use metrics later and avoid having to hit API again
                self.stryd_metrics = stryd_df[
                    (stryd_df.index >= (start - timedelta(minutes=5))) & (
                            stryd_df.index <= (start + timedelta(minutes=5)))]
                try:
                    self.ftp = self.stryd_metrics.iloc[0].stryd_ftp
                    if self.ftp == 0:
                        self.ftp = self.Athlete.run_ftp
                except:
                    # If no FTP test prior to current activity
                    self.ftp = self.Athlete.run_ftp
            else:
                self.ftp = self.Athlete.run_ftp
        elif 'ride' in self.type.lower():
            # TODO: Switch over to using Critical Power for everything once we get the critical power model working
            session, engine = db_connect()
            try:
                self.ftp = float(
                    session.query(stravaSummary.average_watts).order_by(stravaSummary.start_date_local.desc()).filter(
                        stravaSummary.start_date_local < self.start_date_local,
                        stravaSummary.type.ilike('%ride%'),
                        stravaSummary.name.ilike('%ftp test%')).first()[0]) * .95
            except:
                # If no FTP test prior to current activity
                self.ftp = self.Athlete.ride_ftp

        else:
            self.ftp = None

        if self.ftp is not None:
            self.ftp = None if float(self.ftp) == 0.0 else self.ftp

    def wss_score(self):
        '''
        Loop through each workout, calculate 1rm for all exercises for the given date, save to fitbod table, and calculate wSS for summary table
        :param date: Date of workout
        :param workout_seconds:
        :return:
        '''

        # Calculating inol at individual exercise level
        # https://www.powerliftingwatch.com/files/prelipins.pdf

        # Default inol to provide bodyweight exercises where INOL cannot be calculated
        base_inol = .45
        # Set max inol an exercise can hit per workout (sum of sets)
        max_inol_per_exercise = 2

        # Convert pd date to datetime to compare in sqlalchemy queries
        date = self.start_date.date()

        # Query exercises within trailing 6 weeks of exercise date
        session, engine = db_connect()
        df = pd.read_sql(
            sql=session.query(fitbod).filter(
                # Only use past 6 months of workouts to calculate 1rm
                (date - timedelta(days=180)) <= fitbod.date_utc,
                fitbod.date_utc <= date + timedelta(days=1)
            ).statement, con=engine).sort_index(ascending=True)
        engine.dispose()
        session.close()

        # If no workout data found, return None as a WSS score can not be generated
        if len(df) == 0:
            return None, None

        else:
            df['Volume'] = df['Reps'].replace(0, 1) * df['Weight'].replace(0, 1) * df['Duration'].replace(0, 1)
            # Get 'Best' sets on all exercises in the 6 weeks preceeding current workout being analyzed
            df_1rm = df.copy()
            # Dont include current workout to get 1RMs to compare against
            df_1rm = df_1rm[df_1rm['date_UTC'].dt.date != date]
            df_1rm = df_1rm.loc[df_1rm.groupby('Exercise')['Volume'].agg(pd.Series.idxmax)].reset_index()
            # Calculate Brzycki 1RM based off last 6 weeks of workouts
            df_1rm['one_rep_max'] = (df_1rm['Weight'] * (36 / (37 - df_1rm['Reps'])))

            # TODO: Update from just adding 30% to max to a more accurate 1 'rep' max formula
            # Calculate max weight_duration for intensity on timed exercises that could use weights (i.e. planks) (+30% on max weight_duratopm)
            df_1rm.at[df_1rm['Reps'] == 0, 'weight_duration_max'] = (df_1rm['Weight'].replace(0, 1) * df_1rm[
                'Duration'].replace(0, 1)) * 1.3
            # Calculate max reps (for bodyweight exercises) (+30% on max reps)
            df_1rm.at[df_1rm['Weight'] == 0, 'max_reps'] = df_1rm['Volume'] * 1.3

            # Filter main df back to current workout which we are assigning 1rms to
            df = df[df['date_UTC'].dt.date == date]

            # Cap workout time at 2 mins per set - temporary fix until fitbod expoorts at timestamp level
            workout_time = self.df_samples['time'].max() if self.df_samples['time'].max() < (len(df) * 120) else (
                    len(df) * 120)

            # Merge in 1rms
            df = df.merge(df_1rm[['Exercise', 'one_rep_max', 'weight_duration_max']], how='left',
                          left_on='Exercise', right_on='Exercise')

            # Replace table placeholders with max values
            df['one_rep_max'] = df['one_rep_max_y'].fillna(0.0)
            df['weight_duration_max'] = df['weight_duration_max_y'].fillna(0)

            # Save 1rms to fitbod table
            session, engine = db_connect()
            for exercise in df[~np.isnan(df['one_rep_max'])]['Exercise'].drop_duplicates():
                records = session.query(fitbod).filter(cast(fitbod.date_utc, Date) == date,
                                                       fitbod.exercise == exercise).all()
                for record in records:
                    record.one_rep_max = float(df.loc[df['Exercise'] == exercise]['one_rep_max'].values[0])
                    record.weight_duration_max = int(
                        df.loc[df['Exercise'] == exercise]['weight_duration_max'].values[0])
                    session.commit()
            engine.dispose()
            session.close()

            df['set_intensity'] = df['Weight'] / df['one_rep_max']
            # Restrict max intensity from being 1 or greater for INOL calc
            df.at[df['set_intensity'] >= 1, 'set_intensity'] = .99

            # Set all inol to base INOLs so score gets applied to bodyweight exercises
            df['inol'] = base_inol
            # Calculate INOL where one_rep_max's exist in last 6 weeks
            df.at[((df['Weight'] != 0) & (df['one_rep_max'] != 0)), 'inol'] = df['Reps'] / (
                    (1 - (df['set_intensity'])) * 100)

            # If one rep max was hit, set the exercise inol to max inol per exercise
            df = df.groupby(['date_UTC', 'Exercise']).sum().reset_index()
            df.at[(df['inol'] > max_inol_per_exercise), 'inol'] = max_inol_per_exercise

            # ## Doesn't Work well with INOL Formula since both reps and weight are really required for it to work
            # # For bodyweight exercise, there is no weight, so use reps/max reps for intensity
            # df.at[df['Weight'] == 0, 'inol'] = df['Reps'] / ((1 - (df['Reps'] / df['max_reps'])) * 100)
            # # For timed exercises i.e. plank, there are no reps, use max duration * weight for intensity, and '1' for the numerator
            # df['weight_duration'] = (df['Duration'].replace(0, 1) * df['Weight'].replace(0, 1))
            # df.at[((df['Reps'] == 0) & (df['Duration'] != 0)), 'inol'] = 1 / ((1 - (df['weight_duration'] / df['weight_duration_max'])) * 100)
            # ####

            # Convert INOLs to WSS
            # Get max amount of possible INOL from workout at a rate of 2 INOL per exercise
            max_inol_possible = df['Exercise'].nunique() * max_inol_per_exercise
            # Calculate intensity factor (how hard you worked out of the hardest that could have been worked expressed in inol)
            ri = df['inol'].sum() / max_inol_possible
            # Estimate TSS Based on Intensity Factor and Duration
            # https://www.trainingpeaks.com/blog/how-to-plan-your-season-with-training-stress-score/
            workout_tss = ri * ri * (workout_time / 3600) * 100

            # Get max amount of possible TSS based on TSS per sec
            # max_tss_per_sec = (100 / 60 / 60)

            # TODO: Update seconds with datediff once set timestamps are added to dataset, for now use entire length of workout
            # max_tss_possible = workout_seconds * max_tss_per_sec
            # workout_tss = max_tss_possible * relative_intensity
            # df['seconds'] = 60
            # max_tss_possible = df['seconds'].sum() * max_tss_per_sec

            # Calculate WSS
            # df['wSS'] = (max_tss_per_sec * df['seconds']) * (df['inol'] / max_inol_possible)
            # return df['wSS'].sum()

            df.to_csv('workout.csv', sep=',')

            return workout_tss, ri

    def get_summary_analytics(self):
        self.trimp, self.hrss, self.wap, self.tss, self.ri, self.variability_index, self.efficiency_factor = None, None, None, None, None, None, None
        activity_length = self.df_samples['time'].max()

        # Calculate power metrics
        if 'weighttraining' in self.type.lower():
            self.tss, self.ri = self.wss_score()

        elif self.max_watts is not None and self.ftp is not None:
            self.wap = weighted_average_power(self.df_samples['watts'].to_numpy())
            self.ri = relative_intensity(self.wap, self.ftp)

            # Use Stryd RSS instead of TrainingPeaks calculation for RSS
            if len(self.stryd_metrics) > 0:
                self.tss = self.stryd_metrics.iloc[0].RSS
            else:
                self.tss = stress_score(self.wap, self.ftp, activity_length)
            self.variability_index = self.wap / self.df_samples['watts'].mean()

        if self.max_heartrate is not None:
            # Calculate heartrate metrics
            athlete_lthr = .89 * self.athlete_max_hr
            self.df_samples['hrr'] = self.df_samples['heartrate'].apply(
                lambda x: (x - self.hr_lowest) / (self.athlete_max_hr - self.hr_lowest))
            self.trimp = ((1 / 60) * self.df_samples['hrr'] * (0.64 * np.exp(1.92 * self.df_samples['hrr']))).sum()
            athlete_hrr_lthr = (athlete_lthr - self.hr_lowest) / (self.athlete_max_hr - self.hr_lowest)
            self.hrss = (self.trimp / (60 * athlete_hrr_lthr * (0.64 * np.exp(1.92 * athlete_hrr_lthr)))) * 100
            self.df_samples = self.df_samples.drop(columns='hrr')

        if self.max_heartrate is not None and self.wap is not None:
            self.efficiency_factor = self.wap / self.df_samples['heartrate'].mean()

    def build_df_summary(self):
        self.df_summary = pd.DataFrame()
        self.df_summary['activity_id'] = [self.id]

        if self.start_latlng is not None:
            self.df_summary['start_lat'] = [self.start_latlng[0]]
            self.df_summary['start_lon'] = [self.start_latlng[1]]
        else:
            self.df_summary['start_lat'] = None
            self.df_summary['start_lon'] = None
        if self.end_latlng is not None:
            self.df_summary['end_lat'] = [self.end_latlng[0]]
            self.df_summary['end_lon'] = [self.end_latlng[1]]
        else:
            self.df_summary['end_lat'] = None
            self.df_summary['end_lon'] = None

        self.df_summary['achievement_count'] = [self.achievement_count]
        self.df_summary['activity_id'] = [self.id]
        self.df_summary['average_heartrate'] = [self.average_heartrate]
        self.df_summary['average_speed'] = [unithelper.mph(self.average_speed).num]
        self.df_summary['average_watts'] = [self.average_watts]
        self.df_summary['calories'] = [self.calories]
        self.df_summary['commute'] = [self.commute]
        self.df_summary['description'] = [self.description]
        self.df_summary['device_name'] = [self.device_name]
        self.df_summary['distance'] = [unithelper.miles(self.distance).num]
        self.df_summary['elapsed_time'] = [self.elapsed_time.seconds]
        self.df_summary['gear_id'] = [self.gear_id]
        self.df_summary['kilojoules'] = [self.kilojoules]
        self.df_summary['location_city'] = [self.location_city]
        self.df_summary['location_country'] = [self.location_country]
        self.df_summary['location_state'] = [self.location_state]
        self.df_summary['max_heartrate'] = [self.max_heartrate]
        self.df_summary['max_speed'] = [unithelper.mph(self.max_speed).num]
        self.df_summary['max_watts'] = [self.max_watts]
        self.df_summary['moving_time'] = [self.moving_time.seconds]
        self.df_summary['name'] = [self.name]
        self.df_summary['pr_count'] = [self.pr_count]
        self.df_summary['start_date_local'] = [self.start_date_local]
        self.df_summary['start_date_utc'] = [self.start_date]
        self.df_summary['start_day_local'] = [self.start_date_local.date()]
        self.df_summary['timezone'] = [str(self.timezone)]
        self.df_summary['total_elevation_gain'] = [unithelper.feet(self.total_elevation_gain).num]
        self.df_summary['trainer'] = [self.trainer]
        self.df_summary['type'] = [self.type]
        self.df_summary.set_index(['start_date_utc'], inplace=True)

    def build_df_samples(self):
        seconds = 1
        streams = get_strava_client().get_activity_streams(self.id, types=types)
        self.df_samples = pd.DataFrame(columns=types)
        # Write each row to a dataframe
        for item in types:
            if item in streams.keys():
                self.df_samples[item] = pd.Series(streams[item].data, index=None)
        self.df_samples['start_date_local'] = self.start_date_local
        self.df_samples['timestamp_local'] = pd.Series(
            map(calctime, self.df_samples['time'], self.df_samples['start_date_local']))
        self.df_samples.set_index('timestamp_local', inplace=True)

        # Parse latlngs into seperate columns
        try:
            self.df_samples['latitude'] = self.df_samples['latlng'].apply(
                lambda x: x[0] if isinstance(x, list) else None).apply(
                pd.to_numeric,
                errors='coerce')
            self.df_samples['longitude'] = self.df_samples['latlng'].apply(
                lambda x: x[1] if isinstance(x, list) else None).apply(
                pd.to_numeric,
                errors='coerce')
        except KeyError:
            self.df_samples['latitude'] = None
            self.df_samples['longitude'] = None

        # Interpolate samples - each workout in samples data should already be at 1s intervals, calling resample fills in gaps so mean() does not matter
        self.df_samples = self.df_samples.resample(str(seconds) + 'S').mean()
        self.df_samples = self.df_samples.interpolate(
            limit_direction='both')  # TODO: Consider if interpolating of nans is skuing data too much

        try:  # Indoor activity samples wont have altitudes
            self.df_samples['altitude'] = self.df_samples['altitude'] * 3.28084
        except KeyError:
            self.df_samples['altitude'] = None

        try:
            # Convert celcius to farenheit
            self.df_samples['temp'] = unithelper.c2f(self.df_samples['temp'])
        except:
            pass

        try:
            # Convert meter per second to mph
            self.df_samples['velocity_smooth'] = unithelper.mph(self.df_samples['velocity_smooth']).num
        except:
            pass
        try:
            # Convert meters to feet
            self.df_samples['distance'] = unithelper.feet(self.df_samples['distance']).num
        except:
            pass

        # Add Time Interval
        epoch = pd.to_datetime('1970-01-01')
        self.df_samples['time_interval'] = self.df_samples['time'].astype('int').apply(
            lambda x: epoch + timedelta(seconds=x))

        # Add date column
        self.df_samples['date'] = self.df_samples.index.date
        # Add activity id and name back in
        self.df_samples['activity_id'] = self.id
        self.df_samples['act_name'] = self.name

    def calculate_power_zones(self):
        if self.max_watts is not None:
            if self.ftp is not None:
                if 'ride' in self.type.lower():
                    pz_5, pz_6 = self.power_zones[5], self.power_zones[6]
                elif 'run' in self.type.lower() or 'walk' in self.type.lower():
                    pz_5, pz_6 = 99, 99
                self.df_samples['power_zone'] = np.nan

                for i in self.df_samples.index:
                    watts = self.df_samples.loc[i].watts
                    if watts is not None:
                        if watts <= round(self.ftp * self.power_zones[1]):
                            self.df_samples.at[i, 'power_zone'] = 1
                        elif watts <= round(self.ftp * self.power_zones[2]):
                            self.df_samples.at[i, 'power_zone'] = 2
                        elif watts <= round(self.ftp * self.power_zones[3]):
                            self.df_samples.at[i, 'power_zone'] = 3
                        elif watts <= round(self.ftp * self.power_zones[4]):
                            self.df_samples.at[i, 'power_zone'] = 4
                        elif watts <= round(self.ftp * pz_5):
                            self.df_samples.at[i, 'power_zone'] = 5
                        elif watts <= round(self.ftp * pz_6):
                            self.df_samples.at[i, 'power_zone'] = 6
                        else:
                            self.df_samples.at[i, 'power_zone'] = 7
                    else:
                        return np.nan

    def calculate_heartate_zones(self):
        if self.max_heartrate is not None:
            age = relativedelta(datetime.today(), self.Athlete.birthday).years
            self.athlete_max_hr = 220 - age
            self.rhr = self.hr_lowest
            self.hrr = self.athlete_max_hr - self.rhr
            z1 = round((self.hrr * self.hearrate_zones[1]) + self.rhr)
            z2 = round((self.hrr * self.hearrate_zones[2]) + self.rhr)
            z3 = round((self.hrr * self.hearrate_zones[3]) + self.rhr)
            z4 = round((self.hrr * self.hearrate_zones[4]) + self.rhr)

            self.df_samples['hr_zone'] = np.nan
            for i in self.df_samples.index:
                heartrate = self.df_samples.loc[i].heartrate
                if heartrate is not None:
                    if heartrate <= z1:
                        self.df_samples.at[i, 'hr_zone'] = 1
                    elif heartrate <= z2:
                        self.df_samples.at[i, 'hr_zone'] = 2
                    elif heartrate <= z3:
                        self.df_samples.at[i, 'hr_zone'] = 3
                    elif heartrate <= z4:
                        self.df_samples.at[i, 'hr_zone'] = 4
                    else:
                        self.df_samples.at[i, 'hr_zone'] = 5
                else:
                    return np.nan

    def calculate_zone_intensities(self):
        df_zone_intensities = self.df_samples.copy()
        df_zone_intensities = df_zone_intensities[df_zone_intensities['time'] != 0]
        # Check if power data, if not use heartrate data
        metric = 'power' if self.max_watts is not None and self.ftp is not None else 'heartrate' if self.max_heartrate is not None else 'none'

        for i in df_zone_intensities.index:
            # Check if power or heartrate data
            if metric == 'power':
                # If power data, check if run zones or ride zones should be used
                if 'run' in self.type.lower() or 'walk' in self.type.lower():
                    df_zone_intensities.at[i, 'intensity'] = 'low' if df_zone_intensities.at[
                                                                          i, 'power_zone'] in [1,
                                                                                               2] else 'med' if \
                        df_zone_intensities.at[i, 'power_zone'] == 3 else 'high' if \
                        df_zone_intensities.at[
                            i, 'power_zone'] in [4, 5] else None
                elif 'ride' in self.type.lower():
                    df_zone_intensities.at[i, 'intensity'] = 'low' if df_zone_intensities.at[
                                                                          i, 'power_zone'] in [1, 2,
                                                                                               3] else 'med' if \
                        df_zone_intensities.at[i, 'power_zone'] == 4 else 'high' if \
                        df_zone_intensities.at[
                            i, 'power_zone'] in [5, 6, 7] else None
            elif metric == 'heartrate':
                df_zone_intensities.at[i, 'intensity'] = 'low' if df_zone_intensities.at[
                                                                      i, 'hr_zone'] in [1,
                                                                                        2] else 'med' if \
                    df_zone_intensities.at[i, 'hr_zone'] == 3 else 'high' if df_zone_intensities.at[
                                                                                 i, 'hr_zone'] in [4,
                                                                                                   5] else None
        if 'intensity' in df_zone_intensities.columns:
            intensity_seconds = df_zone_intensities['intensity'].value_counts()
            try:
                self.df_summary['low_intensity_seconds'] = [intensity_seconds.low]
            except AttributeError:
                self.df_summary['low_intensity_seconds'] = None
            try:
                self.df_summary['med_intensity_seconds'] = [intensity_seconds.med]
            except AttributeError:
                self.df_summary['med_intensity_seconds'] = None
            try:
                self.df_summary['high_intensity_seconds'] = [intensity_seconds.high]
            except AttributeError:
                self.df_summary['high_intensity_seconds'] = None

    def compute_mean_max_power(self, dbinsert=False):
        if self.max_watts is not None:
            df = self.df_samples.copy()
            df = df.rename(columns={"watts": "power", "velocity_smooth": "speed"})
            self.mmp_df = pd.Series(WorkoutDataFrame(df).compute_mean_max_power(), name='mmp').to_frame()
            # Update time index so it starts at 1 second (instead of 0)
            self.mmp_df['time'] = [x for x in range(1, len(self.mmp_df) + 1)]
            self.mmp_df.set_index('time', inplace=True)
            if dbinsert:
                df = self.df_samples.copy()
                df.rename(columns={'time': 'interval'}, inplace=True)
                for col in ['distance', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'moving', 'grade_smooth',
                            'latitude', 'longitude', 'altitude', 'power_zone', 'hr_zone', 'temp']:
                    if col in df.columns:
                        df = df.drop(columns=col)
                df = df[df['interval'] != 0]
                df['mmp'] = df['interval'].map(self.mmp_df['mmp'].to_dict())
                df['watts_per_kg'] = df['mmp'] / self.kg
                df['timestamp_local'] = df.index
                df['type'] = self.type
                df['athlete_id'] = self.Athlete.athlete_id
                df['ftp'] = self.ftp
                df.set_index(['activity_id', 'interval'], inplace=True)
                db_insert(df, 'strava_best_samples')

    def sweatpy_cp_model(self, model='3_parameter_non_linear'):
        # Models that can be passed = '2_parameter_non_linear', '3_parameter_non_linear', 'extended_5_3','extended_7_3'
        # Run CP model to return fitted params
        return critical_power.model_fit(self.mmp_df.index, self.mmp_df['mmp'], model=model)

    def write_dfs_to_db(self):
        # Add athlete_id to df_summary
        self.df_summary['athlete_id'] = [self.Athlete.athlete_id]
        self.df_summary['ftp'] = [self.ftp]
        self.df_summary['trimp'] = [self.trimp]
        self.df_summary['hrss'] = [self.hrss]
        self.df_summary['relative_intensity'] = [self.ri]
        self.df_summary['efficiency_factor'] = [self.efficiency_factor]
        self.df_summary['tss'] = [self.tss]
        self.df_summary['variability_index'] = [self.variability_index]
        self.df_summary['weighted_average_power'] = [self.wap]
        self.df_summary['weight'] = [self.weight]
        # Add other columns to samples df
        self.df_samples['type'] = self.type
        self.df_samples['athlete_id'] = self.Athlete.athlete_id

        db_insert(self.df_summary.fillna(np.nan), 'strava_summary')
        db_insert(self.df_samples.fillna(np.nan), 'strava_samples')


def hrv_training_workflow(min_non_warmup_workout_time, athlete_id=1):
    '''
    Query db for oura hrv data, calculate rolling 7 day average, generate recommended workout and store in db.
    Once stored, continuously check if workout has been completed and fill in 'Compelted' field
    '''

    # https://www.trainingpeaks.com/coach-blog/new-study-widens-hrv-evidence-for-more-athletes/

    session, engine = db_connect()

    # Check if entire table is empty, if so the earliest hrv plan can start is after 30 days of hrv readings
    db_test = pd.read_sql(
        sql=session.query(hrvWorkoutStepLog).filter(hrvWorkoutStepLog.athlete_id == athlete_id).statement,
        con=engine, index_col='date')

    if len(db_test) == 0:
        min_oura_date = pd.to_datetime(
            session.query(func.min(ouraSleepSummary.report_date))[0][0] + timedelta(29)).date()
        db_test.at[min_oura_date, 'athlete_id'] = athlete_id
        db_test.at[min_oura_date, 'hrv_workout_step'] = 0
        db_test.at[min_oura_date, 'hrv_workout_step_desc'] = 'Low'
        db_test.at[min_oura_date, 'completed'] = 0
        db_test.at[min_oura_date, 'rationale'] = 'This is the first date 30 day hrv thresholds could be calculated'
        db_insert(db_test, 'hrv_workout_step_log')

    # Check if a step has already been inserted for today and if so check if workout has been completed yet
    todays_plan = session.query(hrvWorkoutStepLog).filter(hrvWorkoutStepLog.athlete_id == athlete_id,
                                                          hrvWorkoutStepLog.date == datetime.today().date()).first()

    if todays_plan:
        # If not yet "completed" keep checking throughout day
        if todays_plan.completed == 0:
            # If rest day, mark as completed
            if todays_plan.hrv_workout_step == 4 or todays_plan.hrv_workout_step == 5:
                todays_plan.completed = 1
                session.commit()
            else:
                workout = session.query(stravaSummary).filter(stravaSummary.start_day_local == datetime.today().date(),
                                                              stravaSummary.elapsed_time > min_non_warmup_workout_time).first()
                if workout:
                    todays_plan.completed = 1
                    session.commit()

    # If plan not yet created for today, create it
    else:
        hrv_df = pd.read_sql(sql=session.query(ouraSleepSummary.report_date, ouraSleepSummary.rmssd).statement,
                             con=engine, index_col='report_date').sort_index(ascending=True)

        # Wait for today's hrv to be loaded into cloud
        if hrv_df.index.max() == datetime.today().date():  # or (datetime.now() - timedelta(hours=12)) > pd.to_datetime(datetime.today().date()):

            step_log_df = pd.read_sql(
                sql=session.query(hrvWorkoutStepLog.date, hrvWorkoutStepLog.hrv_workout_step,
                                  hrvWorkoutStepLog.completed).filter(
                    hrvWorkoutStepLog.athlete_id == 1).statement,
                con=engine, index_col='date').sort_index(ascending=False)

            # Store the last value of step 2 "HIIT" or "Mod" to cycle between the 2
            try:
                last_hiit_mod = step_log_df[(step_log_df['hrv_workout_step'] == 2) & (step_log_df['completed'] == 1)][
                    'hrv_workout_step_desc'].head(1).values[0]
            except:
                last_hiit_mod = 'HIIT'
            next_hiit_mod = 'HIIT' if last_hiit_mod == 'Mod' else 'Mod'

            step_log_df = step_log_df[step_log_df.index == step_log_df.index.max()]

            # Store last step in variable for starting point in loop
            last_db_step = step_log_df['hrv_workout_step'].iloc[0]

            # Resample to today
            step_log_df.at[pd.to_datetime(datetime.today().date()), 'hrv_workout_step'] = None
            step_log_df.set_index(pd.to_datetime(step_log_df.index), inplace=True)
            step_log_df = step_log_df.resample('D').mean()

            # Remove first row from df so it does not get re inserted into db
            step_log_df = step_log_df.iloc[1:]

            # We already know there is no step for today from "current_step" parameter, so manually add today's date
            step_log_df.at[pd.to_datetime(datetime.today().date()), 'completed'] = 0

            # Check if gap between today and max date in step log, if so merge in all workouts for 'completed' flag
            if step_log_df['completed'].isnull().values.any():
                workouts = pd.read_sql(
                    sql=session.query(stravaSummary.start_day_local, stravaSummary.activity_id).filter(
                        stravaSummary.elapsed_time > min_non_warmup_workout_time)
                        .statement, con=engine,
                    index_col='start_day_local')
                # Resample workouts to the per day level - just take max activity_id in case they were more than 1 workout for that day to avoid duplication of hrv data
                workouts.set_index(pd.to_datetime(workouts.index), inplace=True)
                workouts = workouts.resample('D').max()
                step_log_df = step_log_df.merge(workouts, how='left', left_index=True, right_index=True)
                # Completed = True if a workout (not just warmup) was done on that day or was a rest day
                for x in step_log_df.index:
                    step_log_df.at[x, 'completed'] = 0 if np.isnan(step_log_df.at[x, 'activity_id']) else 1

            # Generate row with yesterdays plan completions status for looping below through workout cycle logic
            step_log_df['completed_yesterday'] = step_log_df['completed'].shift(1)

            # Drop historical rows that were used for 'yesterday calcs' so we are only working with todays data
            # step_log_df = step_log_df.iloc[1:]

            # Calculate HRV metrics
            hrv_df.set_index(pd.to_datetime(hrv_df.index), inplace=True)
            hrv_df = hrv_df.resample('D').mean()

            hrv_df['rmssd_7'] = hrv_df['rmssd'].rolling(7, min_periods=0).mean()
            hrv_df['rmssd_7_yesterday'] = hrv_df['rmssd_7'].shift(1)
            hrv_df['rmssd_30'] = hrv_df['rmssd'].rolling(30, min_periods=0).mean()
            hrv_df['stdev_rmssd_30_threshold'] = hrv_df['rmssd'].rolling(30, min_periods=0).std() * .5
            hrv_df['swc_upper'] = hrv_df['rmssd_30'] + hrv_df['stdev_rmssd_30_threshold']
            hrv_df['swc_lower'] = hrv_df['rmssd_30'] - hrv_df['stdev_rmssd_30_threshold']
            hrv_df['under_low_threshold'] = hrv_df['rmssd_7'] < hrv_df['swc_lower']
            hrv_df['under_low_threshold_yesterday'] = hrv_df['under_low_threshold'].shift(1)
            hrv_df['over_upper_threshold'] = hrv_df['rmssd_7'] > hrv_df['swc_upper']
            hrv_df['over_upper_threshold_yesterday'] = hrv_df['over_upper_threshold'].shift(1)
            for i in hrv_df.index:
                if hrv_df.at[i, 'under_low_threshold_yesterday'] == False and hrv_df.at[
                    i, 'under_low_threshold'] == True:
                    hrv_df.at[i, 'lower_threshold_crossed'] = True
                else:
                    hrv_df.at[i, 'lower_threshold_crossed'] = False
                if hrv_df.at[i, 'over_upper_threshold_yesterday'] == False and hrv_df.at[
                    i, 'over_upper_threshold'] == True:
                    hrv_df.at[i, 'upper_threshold_crossed'] = True
                else:
                    hrv_df.at[i, 'upper_threshold_crossed'] = False

            # Merge dfs
            df = pd.merge(step_log_df, hrv_df, how='left', right_index=True, left_index=True)

            last_step = last_db_step
            for i in df.index:
                # Completed / Completed_yesterday could show erroneous data for rest days, as the 0 is brought in based off if a workout is found in strava summary
                df.at[i, 'completed_yesterday'] = 1 if last_step == 4 or last_step == 5 else df.at[
                    i, 'completed_yesterday']

                hrv_increase = df.at[i, 'rmssd_7'] >= df.at[i, 'rmssd_7_yesterday']

                ### Low Threshold Exceptions ###
                # If lower threshold is crossed, switch to low intensity track
                if df.at[i, 'lower_threshold_crossed'] == True:
                    current_step = 4
                    rationale = '7 day HRV average crossed the 30 day baseline lower threshold.'
                    app.server.logger.debug('Lower threshold crossed. Setting current step = 4')
                # If we are below lower threshold, rest until back over threshold
                elif df.at[i, 'under_low_threshold'] == True:
                    current_step = 5
                    rationale = '7 day HRV average is under the 30 day baseline lower threshold.'
                    app.server.logger.debug('HRV is under threshold. Setting current step = 5')

                ### Upper Threshold Exceptions ###
                # If upper threshold is crossed, switch to high  intensity
                elif df.at[i, 'upper_threshold_crossed'] == True:
                    current_step = 1
                    rationale = '7 day HRV average crossed the 30 day baseline upper threshold.'
                    app.server.logger.debug('Upper threshold crossed. Setting current step = 1')
                # If we are above upper threshold, load high intensity until back under threshold
                elif df.at[i, 'over_upper_threshold'] == True:
                    if hrv_increase:
                        current_step = 1
                        rationale = '7 day HRV average increased and is still over the 30 day baseline upper threshold.'
                    else:
                        current_step = 2
                        rationale = "7 day HRV average decreased but is still over the 30 day baseline upper threshold."
                    app.server.logger.debug(
                        'HRV is above threshold. Setting current step = {}.'.format(current_step))

                ### Missed Workout Exceptions ###
                # If workout was not completed yesterday but we are still within thresholds and current step is high/moderate go high if hrv increases, or stay on moderate if hrv decreases
                elif df.at[i, 'completed_yesterday'] == 0 and df.at[i, 'under_low_threshold'] == False and df.at[
                    i, 'over_upper_threshold'] == False and (last_step == 1 or last_step == 2):
                    if hrv_increase:
                        current_step = 1
                        rationale = "7 day HRV average increased and yesterday's workout was not completed."
                    else:
                        current_step = 2
                        rationale = "7 day HRV average decreased and yesterday's workout was not completed."
                    app.server.logger.debug(
                        'No workout detected for previous day however still within thresholds. Maintaining last step = {}'.format(
                            current_step))
                else:
                    app.server.logger.debug(
                        'No exceptions detected. Following the normal workout plan workflow.')
                    rationale = '7 day HRV average is within the tresholds. Following the normal workout plan workflow.'
                    # Workout workflow logic when no exceptions
                    if last_step == 0:
                        current_step = 1
                    elif last_step == 1:
                        current_step = 2 if hrv_increase else 6
                    elif last_step == 2:
                        current_step = 3
                    elif last_step == 3:
                        current_step = 1 if hrv_increase else 4
                    elif last_step == 4:
                        current_step = 6 if hrv_increase else 5
                    elif last_step == 5:
                        current_step = 6
                    elif last_step == 6:
                        current_step = 1 if hrv_increase else 4

                df.at[i, 'completed'] = 1 if current_step == 4 or current_step == 5 else df.at[i, 'completed']
                df.at[i, 'hrv_workout_step'] = current_step
                last_step = current_step

                # Map descriptions and alternate every HIIT and Mod
                df.at[i, 'hrv_workout_step_desc'] = \
                    {0: 'Low', 1: 'High', 2: next_hiit_mod, 3: 'Low', 4: 'Rest', 5: 'Rest', 6: 'Low'}[
                        df.at[i, 'hrv_workout_step']]
                if df.at[i, 'hrv_workout_step'] == 2 and df.at[i, 'completed'] == 1:
                    next_hiit_mod = 'HIIT' if next_hiit_mod == 'Mod' else 'Mod'

                df.at[i, 'rationale'] = rationale

            df['athlete_id'] = athlete_id

            df.reset_index(inplace=True)
            # Insert into db
            df = df[['athlete_id', 'date', 'hrv_workout_step', 'hrv_workout_step_desc', 'completed', 'rationale']]
            df['date'] = df['date'].dt.date
            df.to_sql('hrv_workout_step_log', engine, if_exists='append', index=False)

            if peloton_credentials_supplied and len(
                    config.get('peloton', 'workout_types').replace(' ', '').split(',')) > 0:
                set_peloton_workout_recommendations(
                    fitness_disciplines=config.get('peloton', 'workout_types').replace(' ', '').split(','))

    engine.dispose()
    session.close()
