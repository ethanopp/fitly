import sys
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, create_engine, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import configparser

config = configparser.ConfigParser()
config.read('./config.ini')

Base = declarative_base()

# db = "mysql+pymysql://{}:{}@{}/{}?host={}?port={}".format(config.get("database", 'user'),
#                                                           config.get("database", 'password'),
#                                                           config.get("database", 'host'),
#                                                           config.get("database", 'db_name'),
#                                                           config.get("database", 'host'),
#                                                           config.get("database", 'port')
#                                                           )

db = 'sqlite:///fitness.db'


def db_connect(db=db):
    try:
        # Engine needs to be set to exact location for automation to work
        engine = create_engine(db)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        session = Session()
        Session.remove()
        return session, engine
    except Exception as e:
        print('Error setting up DB: ', str(e))
        print('Quitting')
        sys.exit()


def db_insert(df, tableName):
    session, engine = db_connect()
    # Insert into DB
    df.to_sql(tableName, engine, if_exists='append', index=True)
    engine.dispose()
    session.close()


##### Athlete Table #####

class athlete(Base):
    __tablename__ = 'athlete'
    athlete_id = Column('athlete_id', Integer(), index=True, primary_key=True, autoincrement=True)
    name = Column('name', String(255))
    birthday = Column('birthday', Date())
    weight_lbs = Column('weight_lbs', Integer())
    resting_hr = Column('resting_hr', Integer())
    sex = Column('sex', String(1))
    min_non_warmup_workout_time = Column('min_non_warmup_workout_time',
                                         Integer())  # threshold in seconds for when we start counting workouts towards stress scores (don't want to include warm-ups)
    weekly_tss_goal = Column('weekly_tss_goal', Integer())
    rr_max_goal = Column('rr_max_goal', Integer())  # Max ramp rate threshold used for calculating injury risk
    rr_min_goal = Column('rr_min_goal', Integer())  # Min ramp rate threshold used for calculating injury risk
    weekly_workout_goal = Column('weekly_workout_goal', Integer())  # weekly workout minute goal
    weekly_yoga_goal = Column('weekly_yoga_goal', Integer())  # weekly yoga minute goal
    weekly_sleep_score_goal = Column('weekly_sleep_score_goal', Integer())  # Oura sleep scores >= 85 to achieve weekly
    weekly_readiness_score_goal = Column('weekly_readiness_score_goal',
                                         Integer())  # Oura readiness scores >= 85 to achieve weekly
    weekly_activity_score_goal = Column('weekly_activity_score_goal',
                                        Integer())  # Oura activity scores >= 85 to achieve weekly
    daily_sleep_hr_target = Column('daily_sleep_hr_target', Integer())  # Daily sleep hour target
    ftp_test_notification_week_threshold = Column('ftp_test_notification_week_threshold',
                                                  Integer())  # Num weeks to retest ftp
    cycle_power_zone_threshold_1 = Column('cycle_power_zone_threshold_1', Float())
    cycle_power_zone_threshold_2 = Column('cycle_power_zone_threshold_2', Float())
    cycle_power_zone_threshold_3 = Column('cycle_power_zone_threshold_3', Float())
    cycle_power_zone_threshold_4 = Column('cycle_power_zone_threshold_4', Float())
    cycle_power_zone_threshold_5 = Column('cycle_power_zone_threshold_5', Float())
    cycle_power_zone_threshold_6 = Column('cycle_power_zone_threshold_6', Float())
    run_power_zone_threshold_1 = Column('run_power_zone_threshold_1', Float())
    run_power_zone_threshold_2 = Column('run_power_zone_threshold_2', Float())
    run_power_zone_threshold_3 = Column('run_power_zone_threshold_3', Float())
    run_power_zone_threshold_4 = Column('run_power_zone_threshold_4', Float())
    hr_zone_threshold_1 = Column('hr_zone_threshold_1', Float())
    hr_zone_threshold_2 = Column('hr_zone_threshold_2', Float())
    hr_zone_threshold_3 = Column('hr_zone_threshold_3', Float())
    hr_zone_threshold_4 = Column('hr_zone_threshold_4', Float())


class hrvWorkoutStepLog(Base):
    __tablename__ = 'hrv_workout_step_log'
    id = Column('id', Integer(), index=True, primary_key=True, autoincrement=True)
    athlete_id = Column('athlete_id', Integer())
    date = Column('date', Date())
    hrv_workout_step = Column('hrv_workout_step', Integer())
    hrv_workout_step_desc = Column('hrv_workout_step_desc', String(20))
    completed = Column('completed', Boolean, default=False)
    rationale = Column('rationale', String(255))


class annotations(Base):
    __tablename__ = 'annotations'
    id = Column('id', Integer(), index=True, primary_key=True, autoincrement=True)
    athlete_id = Column('athlete_id', Integer())
    date = Column('date', Date())
    annotation = Column('annotation', String(255))


##### Strava Tables #####

class stravaSamples(Base):
    __tablename__ = 'strava_samples'
    timestamp_local = Column('timestamp_local', DateTime(), index=True, primary_key=True)
    time_interval = Column('time_interval', DateTime())
    activity_id = Column('activity_id', BigInteger())
    date = Column('date', Date())
    type = Column('type', String(255))
    act_name = Column('act_name', String(255))
    athlete_id = Column('athlete_id', BigInteger())
    distance = Column('distance', Float())
    velocity_smooth = Column('velocity_smooth', Float())
    temp = Column('temp', Float())
    altitude = Column('altitude', Float())
    latitude = Column('latitude', Float())
    longitude = Column('longitude', Float())
    heartrate = Column('heartrate', Integer())
    cadence = Column('cadence', Integer())
    watts = Column('watts', Integer())
    moving = Column('moving', Integer())
    grade_smooth = Column('grade_smooth', Float())
    ftp = Column('ftp', Float())
    time = Column('time', Integer())
    power_zone = Column('power_zone', Integer())
    hr_zone = Column('hr_zone', Integer())
    hr_lowest = Column('hr_lowest', Integer())


class stravaBestSamples(Base):
    __tablename__ = 'strava_best_samples'
    activity_id = Column('activity_id', BigInteger(), index=True, primary_key=True)
    interval = Column('interval', Integer, index=True, primary_key=True)
    mmp = Column('mmp', Float())
    watts_per_kg = Column('watts_per_kg', Float())
    timestamp_local = Column('timestamp_local', DateTime())
    time_interval = Column('time_interval', DateTime())
    type = Column('type', String(255))
    date = Column('date', Date())
    act_name = Column('act_name', String(255))
    athlete_id = Column('athlete_id', BigInteger())


class stravaSummary(Base):
    __tablename__ = 'strava_summary'
    start_date_utc = Column('start_date_utc', DateTime(), index=True, primary_key=True)
    activity_id = Column('activity_id', BigInteger())
    athlete_id = Column('athlete_id', BigInteger())
    name = Column('name', String(255))
    distance = Column('distance', Float())
    moving_time = Column('moving_time', BigInteger())
    elapsed_time = Column('elapsed_time', BigInteger())
    total_elevation_gain = Column('total_elevation_gain', Integer())
    type = Column('type', String(255))
    start_date_local = Column('start_date_local', DateTime())
    start_day_local = Column('start_day_local', Date())
    timezone = Column('timezone', String(255))
    start_lat = Column('start_lat', String(255))
    start_lon = Column('start_lon', String(255))
    end_lat = Column('end_lat', String(255))
    end_lon = Column('end_lon', String(255))
    location_city = Column('location_city', String(255))
    location_state = Column('location_state', String(255))
    location_country = Column('location_country', String(255))
    average_speed = Column('average_speed', Float())
    max_speed = Column('max_speed', Float())
    average_watts = Column('average_watts', Float())
    max_watts = Column('max_watts', Float())
    average_heartrate = Column('average_heartrate', Float())
    max_heartrate = Column('max_heartrate', Float())
    kilojoules = Column('kilojoules', Float())
    device_name = Column('device_name', String(255))
    calories = Column('calories', Float())
    description = Column('description', String(255))
    pr_count = Column('pr_count', Integer())
    achievement_count = Column('achievement_count', Integer())
    commute = Column('commute', Integer())
    trainer = Column('trainer', Integer())
    gear_id = Column('gear_id', String(255))
    ftp = Column('ftp', Float())
    weighted_average_power = Column('weighted_average_power', Float())
    relative_intensity = Column('relative_intensity', Float())
    efficiency_factor = Column('efficiency_factor', Float())
    tss = Column('tss', Float())
    hrss = Column('hrss', Float())
    variability_index = Column('variability_index', Float())
    trimp = Column('trimp', Float())
    low_intensity_seconds = Column('low_intensity_seconds', Integer())
    med_intensity_seconds = Column('med_intensity_seconds', Integer())
    high_intensity_seconds = Column('high_intensity_seconds', Integer())
    weight = Column('weight', Float())


##### Oura Tables #####
class ouraReadinessSummary(Base):
    __tablename__ = 'oura_readiness_summary'
    report_date = Column('report_date', Date(), index=True, primary_key=True)
    summary_date = Column('summary_date', Date())
    score = Column('score', Integer())
    period_id = Column('period_id', Integer())
    score_activity_balance = Column('score_activity_balance', Integer())
    score_previous_day = Column('score_previous_day', Integer())
    score_previous_night = Column('score_previous_night', Integer())
    score_recovery_index = Column('score_recovery_index', Integer())
    score_resting_hr = Column('score_resting_hr', Integer())
    score_sleep_balance = Column('score_sleep_balance', Integer())
    score_temperature = Column('score_temperature', Integer())
    score_hrv_balance = Column('score_hrv_balance', Integer())


class ouraActivitySummary(Base):
    __tablename__ = 'oura_activity_summary'
    summary_date = Column('summary_date', Date(), index=True, primary_key=True)
    average_met = Column('average_met', Float())
    cal_active = Column('cal_active', Integer())
    cal_total = Column('cal_total', Integer())
    class_5min = Column('class_5min', String(300))
    daily_movement = Column('daily_movement', Integer())
    day_end_local = Column('day_end_local', DateTime())
    day_start_local = Column('day_start_local', DateTime())
    high = Column('high', Integer())
    inactive = Column('inactive', Integer())
    inactivity_alerts = Column('inactivity_alerts', Integer())
    low = Column('low', Integer())
    medium = Column('medium', Integer())
    met_min_high = Column('met_min_high', Integer())
    met_min_inactive = Column('met_min_inactive', Integer())
    met_min_low = Column('met_min_low', Integer())
    met_min_medium = Column('met_min_medium', Integer())
    non_wear = Column('non_wear', Integer())
    rest = Column('rest', Integer())
    score = Column('score', Integer())
    score_meet_daily_targets = Column('score_meet_daily_targets', Integer())
    score_move_every_hour = Column('score_move_every_hour', Integer())
    score_recovery_time = Column('score_recovery_time', Integer())
    score_stay_active = Column('score_stay_active', Integer())
    score_training_frequency = Column('score_training_frequency', Integer())
    score_training_volume = Column('score_training_volume', Integer())
    steps = Column('steps', Integer())
    target_calories = Column('target_calories', Integer())
    timezone = Column('timezone', Integer())
    target_km = Column('target_km', Float())
    target_miles = Column('target_miles', Float())
    to_target_km = Column('to_target_km', Float())
    to_target_miles = Column('to_target_miles', Float())
    total = Column('total', Integer())


class ouraActivitySamples(Base):
    __tablename__ = 'oura_activity_samples'
    timestamp_local = Column('timestamp_local', DateTime(), index=True, primary_key=True)
    summary_date = Column('summary_date', Date())
    met_1min = Column('met_1min', Float())
    class_5min = Column('class_5min', Integer())
    class_5min_desc = Column('class_5min_desc', String(10))


class ouraSleepSummary(Base):
    __tablename__ = 'oura_sleep_summary'
    report_date = Column('report_date', Date(), index=True, primary_key=True)
    summary_date = Column('summary_date', Date())
    awake = Column('awake', Integer())
    bedtime_end_local = Column('bedtime_end_local', DateTime())
    bedtime_end_delta = Column('bedtime_end_delta', Integer())
    bedtime_start_local = Column('bedtime_start_local', DateTime())
    bedtime_start_delta = Column('bedtime_start_delta', Integer())
    breath_average = Column('breath_average', Float())
    deep = Column('deep', Integer())
    duration = Column('duration', Integer())
    efficiency = Column('efficiency', Integer())
    hr_average = Column('hr_average', Float())
    hr_lowest = Column('hr_lowest', Integer())
    hypnogram_5min = Column('hypnogram_5min', String(255))
    is_longest = Column('is_longest', Integer())
    light = Column('light', Integer())
    midpoint_at_delta = Column('midpoint_at_delta', Integer())
    midpoint_time = Column('midpoint_time', Integer())
    onset_latency = Column('onset_latency', Integer())
    period_id = Column('period_id', Integer())
    rem = Column('rem', Integer())
    restless = Column('restless', Integer())
    rmssd = Column('rmssd', Integer())
    score = Column('score', Integer())
    score_alignment = Column('score_alignment', Integer())
    score_deep = Column('score_deep', Integer())
    score_disturbances = Column('score_disturbances', Integer())
    score_efficiency = Column('score_efficiency', Integer())
    score_latency = Column('score_latency', Integer())
    score_rem = Column('score_rem', Integer())
    score_total = Column('score_total', Integer())
    temperature_delta = Column('temperature_delta', Float())
    temperature_deviation = Column('temperature_deviation', Float())
    temperature_trend_deviation = Column('temperature_trend_deviation', Float())
    timezone = Column('timezone', Integer())
    total = Column('total', Integer())


class ouraSleepSamples(Base):
    __tablename__ = 'oura_sleep_samples'
    timestamp_local = Column('timestamp_local', DateTime(), index=True, primary_key=True)
    summary_date = Column('summary_date', Date())
    report_date = Column('report_date', Date())
    rmssd_5min = Column('rmssd_5min', Integer())
    hr_5min = Column('hr_5min', Integer())
    hypnogram_5min = Column('hypnogram_5min', Integer())
    hypnogram_5min_desc = Column('hypnogram_5min_desc', String(8))


class apiTokens(Base):
    __tablename__ = 'api_tokens'
    date_utc = Column('date_utc', DateTime(), index=True, primary_key=True)
    service = Column('service', String(255))
    tokens = Column('tokens', String(255))


class dbRefreshStatus(Base):
    __tablename__ = 'db_refresh'
    timestamp_utc = Column('timestamp_utc', DateTime(), index=True, primary_key=True)
    process = Column('process', String(255))
    truncate = Column('truncate', Boolean(), default=False)
    oura_status = Column('oura_status', String(255))
    strava_status = Column('strava_status', String(255))
    withings_status = Column('withings_status', String(255))
    fitbod_status = Column('fitbod_status', String(255))


class withings(Base):
    __tablename__ = 'withings'
    date_utc = Column('date_utc', DateTime(), index=True, primary_key=True)
    weight = Column('weight', Float())
    fat_ratio = Column('fat_ratio', Float())
    hydration = Column('hydration', Float())


class fitbod(Base):
    __tablename__ = 'fitbod'
    id = Column('id', Integer(), index=True, primary_key=True, autoincrement=True)
    date_utc = Column('date_UTC', DateTime())
    exercise = Column('Exercise', String(255))
    reps = Column('Reps', Integer())
    weight = Column('Weight', Integer())
    duration = Column('Duration', Integer())
    iswarmup = Column('isWarmup', Boolean())
    note = Column('Note', String(255))
    one_rep_max = Column('one_rep_max', Float())
    weight_duration_max = Column('weight_duration_max', Float())


class fitbod_muscles(Base):
    __tablename__ = 'fitbod_muscles'
    exercise = Column('Exercise', String(255), index=True, primary_key=True)
    muscle = Column('Muscle', String(255))


session, engine = db_connect()
Base.metadata.create_all(engine)
athlete_exists = True if len(session.query(athlete).all()) > 0 else False
# If no athlete created in db, create one
if not athlete_exists:
    from datetime import datetime

    dummy_athlete = athlete(
        name='Athelte Name',
        birthday=datetime.now(),
        sex='M',
        weight_lbs=150,
        min_non_warmup_workout_time=900,
        weekly_tss_goal=150,
        rr_max_goal=8,
        rr_min_goal=5,
        weekly_workout_goal=100,
        weekly_yoga_goal=100,
        weekly_sleep_score_goal=3,
        weekly_readiness_score_goal=3,
        weekly_activity_score_goal=3,
        daily_sleep_hr_target=8,
        ftp_test_notification_week_threshold=6,
        cycle_power_zone_threshold_1=.55,
        cycle_power_zone_threshold_2=.75,
        cycle_power_zone_threshold_3=.9,
        cycle_power_zone_threshold_4=1.05,
        cycle_power_zone_threshold_5=1.2,
        cycle_power_zone_threshold_6=1.5,
        run_power_zone_threshold_1=0.8,
        run_power_zone_threshold_2=0.9,
        run_power_zone_threshold_3=1,
        run_power_zone_threshold_4=1.15,
        hr_zone_threshold_1=.6,
        hr_zone_threshold_2=.7,
        hr_zone_threshold_3=.8,
        hr_zone_threshold_4=.9)
    session.add(dummy_athlete)
    session.commit()

db_refresh_record = True if len(session.query(dbRefreshStatus).all()) > 0 else False
# Insert initial system load refresh record
if not db_refresh_record:
    from datetime import datetime

    dummy_db_refresh_record = dbRefreshStatus(
        timestamp_utc=datetime.utcnow(),
        process='system',
        oura_status='System Startup',
        strava_status='System Startup',
        withings_status='System Startup',
        fitbod_status='System Startup')
    session.add(dummy_db_refresh_record)
    session.commit()

# If fitbod_muslces table not populated create
fitbod_muscles_table = True if len(session.query(fitbod_muscles).all()) > 0 else False
if not fitbod_muscles_table:
    for exercise, muscle in [('Air Squats', 'Quadriceps'),
                             ('Alternating Medicine Ball Push Up', 'Chest'),
                             ('Alternating Single Arm Kettlebell Swing', 'Shoulders'),
                             ('Arnold Dumbbell Press', 'Shoulders'),
                             ('Assisted Chin Up', 'Back'),
                             ('Back Extensions', 'Lower Back'),
                             ('Back Squat', 'Quadriceps'),
                             ('Barbell Bench Press', 'Chest'),
                             ('Barbell Curl', 'Biceps'),
                             ('Barbell Incline Bench Press', 'Chest'),
                             ('Bench Dip', 'Triceps'),
                             ('Bent Over Barbell Row', 'Back'),
                             ('Biceps Curl To Shoulder Press', 'Biceps'),
                             ('Bosu Ball Crunch', 'Abs'),
                             ('Bosu Ball Mountain Climber', 'Abs'),
                             ('Bosu Ball Push Up', 'Chest'),
                             ('Bosu Ball Squat', 'Quadriceps'),
                             ('Bulgarian Split Squat', 'Quadriceps'),
                             ('Burpee', 'Quadriceps'),
                             ('Cable Bicep Curl', 'Biceps'),
                             ('Cable Crossover Fly', 'Chest'),
                             ('Cable Crunch', 'Abs'),
                             ('Cable Face Pull', 'Back'),
                             ('Cable Lateral Raise', 'Shoulders'),
                             ('Cable Rope Tricep Extension', 'Triceps'),
                             ('Cable Row', 'Back'),
                             ('Cable Russian Twists', 'Abs'),
                             ('Cable Shoulder External Rotation', 'Shoulders'),
                             ('Cable Shoulder External Rotation at 90', 'Shoulders'),
                             ('Cable Tricep Pushdown', 'Triceps'),
                             ('Cable Upright Row', 'Shoulders'),
                             ('Cable Wood Chop', 'Abs'),
                             ('Chin Up', 'Back'),
                             ('Clean Deadlift', 'Hamstrings'),
                             ('Close-Grip Bench Press', 'Triceps'),
                             ('Concentration Curl', 'Biceps'),
                             ('Crunches', 'Abs'),
                             ('Curtsy Lunge', 'Hamstrings'),
                             ('Dead Bug', 'Abs'),
                             ('Deadlift', 'Lower Back'),
                             ('Decline Crunch', 'Abs'),
                             ('Decline Push Up', 'Chest'),
                             ('Diamond Push Up', 'Chest'),
                             ('Dip', 'Triceps'),
                             ('Dumbbell Bench Press', 'Chest'),
                             ('Dumbbell Bent Over Row', 'Back'),
                             ('Dumbbell Bicep Curl', 'Biceps'),
                             ('Dumbbell Clean', 'Hamstrings'),
                             ('Dumbbell Decline Bench Press', 'Chest'),
                             ('Dumbbell Decline Fly', 'Chest'),
                             ('Dumbbell Floor Press', 'Chest'),
                             ('Dumbbell Fly', 'Chest'),
                             ('Dumbbell Front Raise', 'Shoulders'),
                             ('Dumbbell Incline Bench Press', 'Chest'),
                             ('Dumbbell Incline Fly', 'Chest'),
                             ('Dumbbell Kickbacks', 'Triceps'),
                             ('Dumbbell Lunge', 'Quadriceps'),
                             ('Dumbbell No Money Curls', 'Biceps'),
                             ('Dumbbell Pullover', 'Back'),
                             ('Dumbbell Rear Delt Raise', 'Shoulders'),
                             ('Dumbbell Romanian Deadlift', 'Lower Back'),
                             ('Dumbbell Row', 'Back'),
                             ('Dumbbell Shoulder Press', 'Shoulders'),
                             ('Dumbbell Shoulder Raise', 'Shoulders'),
                             ('Dumbbell Skullcrusher', 'Triceps'),
                             ('Dumbbell Snatch', 'Hamstrings'),
                             ('Dumbbell Squat', 'Quadriceps'),
                             ('Dumbbell Squat To Shoulder Press', 'Quadriceps'),
                             ('Dumbbell Step Up', 'Quadriceps'),
                             ('Dumbbell Sumo Squat', 'Quadriceps'),
                             ('Dumbbell Tricep Extension', 'Triceps'),
                             ('Dumbbell Upright Row', 'Shoulders'),
                             ('EZ-Bar Curl', 'Biceps'),
                             ('Flutter Kicks', 'Abs'),
                             ('Front Plate Raise', 'Shoulders'),
                             ('Front Squat', 'Quadriceps'),
                             ('Good Morning', 'Hamstrings'),
                             ('Hack Squat', 'Quadriceps'),
                             ('Hammer Curls', 'Biceps'),
                             ('Hammerstrength Chest Press', 'Chest'),
                             ('Hammerstrength Incline Chest Press', 'Chest'),
                             ('Heel Press', ''),
                             ('Incline Barbell Skull Crusher', 'Triceps'),
                             ('Incline Dumbbell Curl', 'Biceps'),
                             ('Incline Dumbbell Row', 'Back'),
                             ('Incline Hammer Curl', 'Biceps'),
                             ('Incline Push Up', 'Chest'),
                             ('Incline Svend Press', 'Chest'),
                             ('Iron Cross', 'Shoulders'),
                             ('Jackknife Sit-Up', 'Abs'),
                             ('Jump Squat', 'Quadriceps'),
                             ('Kettlebell Front Squat', 'Quadriceps'),
                             ('Kettlebell Sumo Squat', 'Quadriceps'),
                             ('Kettlebell Swing', 'Hamstrings'),
                             ('Kettlebell Upright Row', 'Shoulders'),
                             ('Landmine Row', 'Back'),
                             ('Landmine Squat to Press', 'Quadriceps'),
                             ('Lat Pulldown', 'Back'),
                             ('Lateral Cable Tricep Extension', 'Triceps'),
                             ('Lateral Step Up', 'Hamstrings'),
                             ('Lateral Step Up with Knee Drive', 'Hamstrings'),
                             ('Leg Extension', 'Quadriceps'),
                             ('Leg Press', 'Quadriceps'),
                             ('Leg Pull-In', 'Abs'),
                             ('Leg Raise', 'Abs'),
                             ('Low Cable Chest Fly', 'Chest'),
                             ('Lunge', 'Hamstrings'),
                             ('Lunge Jump', 'Hamstrings'),
                             ('Lunge with Ankle Grab', 'Hamstrings'),
                             ('Machine Bench Press', 'Chest'),
                             ('Machine Fly', 'Chest'),
                             ('Machine Leg Press', 'Quadriceps'),
                             ('Machine Preacher Curl', 'Biceps'),
                             ('Machine Rear Delt Fly', 'Shoulders'),
                             ('Machine Tricep Extension', 'Triceps'),
                             ('Medicine Ball Push Up', 'Chest'),
                             ('Medicine Ball Slam', 'Triceps'),
                             ('Mixed Grip Pull Up', 'Back'),
                             ('Mountain Climber', 'Abs'),
                             ('Oblique Crunch', 'Abs'),
                             ('Palms-Down Dumbbell Wrist Curl', 'Forearms'),
                             ('Palms-Up Dumbbell Wrist Curl', 'Forearms'),
                             ('Pike Push Up', 'Chest'),
                             ('Plank', 'Abs'),
                             ('Preacher Curl', 'Biceps'),
                             ('Pull Up', 'Back'),
                             ('Pulse Lunge', 'Hamstrings'),
                             ('Push Press', 'Shoulders'),
                             ('Push Up', 'Chest'),
                             ('Push Up on Knees', 'Chest'),
                             ('Rack Pulls', 'Lower Back'),
                             ('Renegade Row', 'Back'),
                             ('Reverse Barbell Curl', 'Biceps'),
                             ('Reverse Crunch', 'Abs'),
                             ('Reverse Grip Pull Down', 'Back'),
                             ('Reverse Leg Crossover', 'Hamstrings'),
                             ('Reverse Lunge', 'Hamstrings'),
                             ('Romanian Deadlift', 'Hamstrings'),
                             ('Rotation Push Up', 'Chest'),
                             ('Russian Twist', 'Abs'),
                             ('Scissor Crossover Kick', 'Abs'),
                             ('Scissor Kick', 'Abs'),
                             ('Seated Dumbbell Curl', 'Biceps'),
                             ('Seated Dumbbell Rear Delt Raise', 'Shoulders'),
                             ('Seated Leg Curl', 'Hamstrings'),
                             ('Seated Tricep Press', 'Triceps'),
                             ('Shotgun Row', 'Back'),
                             ('Side Bridge', 'Abs'),
                             ('Side Laterals to Front Raise', 'Shoulders'),
                             ('Side Lunge', 'Quadriceps'),
                             ('Single Arm Cable Bicep Curl', 'Biceps'),
                             ('Single Arm Dumbbell Bench Press', 'Chest'),
                             ('Single Arm Dumbbell Tricep Extension', 'Triceps'),
                             ('Single Arm Landmine Press', 'Triceps'),
                             ('Single Arm Landmine Row', 'Back'),
                             ('Single Arm Lat Pulldown', 'Back'),
                             ('Single Arm Overhead Press', 'Shoulders'),
                             ('Single Arm Preacher Curl', 'Biceps'),
                             ('Single Leg Kettlebell Deadlift', 'Lower Back'),
                             ('Single Leg Romanian Deadlift', 'Lower Back'),
                             ('Sit Up', 'Abs'),
                             ('Skullcrusher', 'Triceps'),
                             ('Smith Machine Bent Over Row', 'Back'),
                             ('Smith Machine Squat', 'Quadriceps'),
                             ('Smith Machine Stiff-Legged Deadlift', 'Lower Back'),
                             ('Smith Machine Upright Row', 'Back'),
                             ('Squat with Rotation', 'Quadriceps'),
                             ('Standing Arnold Press', 'Shoulders'),
                             ('Stiff-Legged Barbell Good Morning', 'Hamstrings'),
                             ('Straight-Arm Pulldown', 'Back'),
                             ('Superman', 'Lower Back'),
                             ('Tate Press', 'Triceps'),
                             ('T-Bar Row', 'Back'),
                             ('Toe Touchers', 'Abs'),
                             ('Tricep Overhead Extension with Rope', 'Triceps'),
                             ('Tuck Jump', 'Abs'),
                             ('Underhand Rear Delt Raise', 'Shoulders'),
                             ('Upright Row', 'Back'),
                             ('V-Bar Pulldown', 'Back'),
                             ('Walking Lunge', 'Quadriceps'),
                             ('Wall Sit', 'Abs'),
                             ('Weighted Ball Hyperextension', 'Lower Back'),
                             ('Weighted Wall Sit', 'Abs'),
                             ('Wide Grip Lat Pulldown', 'Back'),
                             ('Zottman Curl', 'Biceps'),
                             ('Zottman Preacher Curl', 'Biceps')]:
        session.add(fitbod_muscles(exercise=exercise, muscle=muscle))
    session.commit()

engine.dispose()
session.close()
