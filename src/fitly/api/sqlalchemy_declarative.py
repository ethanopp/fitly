from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, BigInteger, PickleType
from .database import Base


##### Athlete Table #####

class athlete(Base):
    __tablename__ = 'athlete'
    athlete_id = Column('athlete_id', Integer(), index=True, primary_key=True, autoincrement=True)
    name = Column('name', String(255))
    birthday = Column('birthday', Date())
    weight_lbs = Column('weight_lbs', Integer())
    resting_hr = Column('resting_hr', Integer())
    run_ftp = Column('run_ftp', Integer())
    ride_ftp = Column('ride_ftp', Integer())
    sex = Column('sex', String(1))
    min_non_warmup_workout_time = Column('min_non_warmup_workout_time',
                                         Integer(),
                                         default=900)  # threshold in seconds for when we start counting workouts towards stress scores (don't want to include warm-ups)
    weekly_tss_goal = Column('weekly_tss_goal', Integer(), default=150)
    rr_max_goal = Column('rr_max_goal', Integer(),
                         default=8)  # Max ramp rate threshold used for calculating injury risk
    rr_min_goal = Column('rr_min_goal', Integer(),
                         default=5)  # Min ramp rate threshold used for calculating injury risk
    weekly_workout_goal = Column('weekly_workout_goal', Integer(), default=3)  # weekly workout minute goal
    weekly_sleep_score_goal = Column('weekly_sleep_score_goal', Integer(),
                                     default=3)  # Oura sleep scores >= 85 to achieve weekly
    weekly_readiness_score_goal = Column('weekly_readiness_score_goal',
                                         Integer(), default=3)  # Oura readiness scores >= 85 to achieve weekly
    weekly_activity_score_goal = Column('weekly_activity_score_goal',
                                        Integer(), default=3)  # Oura activity scores >= 85 to achieve weekly
    daily_sleep_hr_target = Column('daily_sleep_hr_target', Integer(), default=8)  # Daily sleep hour target
    ftp_test_notification_week_threshold = Column('ftp_test_notification_week_threshold',
                                                  Integer(), default=6)  # Num weeks to retest ftp
    cycle_power_zone_threshold_1 = Column('cycle_power_zone_threshold_1', Float(), default=.55)
    cycle_power_zone_threshold_2 = Column('cycle_power_zone_threshold_2', Float(), default=.75)
    cycle_power_zone_threshold_3 = Column('cycle_power_zone_threshold_3', Float(), default=.9)
    cycle_power_zone_threshold_4 = Column('cycle_power_zone_threshold_4', Float(), default=1.05)
    cycle_power_zone_threshold_5 = Column('cycle_power_zone_threshold_5', Float(), default=1.2)
    cycle_power_zone_threshold_6 = Column('cycle_power_zone_threshold_6', Float(), default=1.5)
    run_power_zone_threshold_1 = Column('run_power_zone_threshold_1', Float(), default=.8)
    run_power_zone_threshold_2 = Column('run_power_zone_threshold_2', Float(), default=.9)
    run_power_zone_threshold_3 = Column('run_power_zone_threshold_3', Float(), default=1)
    run_power_zone_threshold_4 = Column('run_power_zone_threshold_4', Float(), default=1.15)
    hr_zone_threshold_1 = Column('hr_zone_threshold_1', Float(), default=.6)
    hr_zone_threshold_2 = Column('hr_zone_threshold_2', Float(), default=.7)
    hr_zone_threshold_3 = Column('hr_zone_threshold_3', Float(), default=.8)
    hr_zone_threshold_4 = Column('hr_zone_threshold_4', Float(), default=.9)
    pmc_switch_settings = Column('pmc_switch_settings', String(9999),
                                 default='{"ride_status": true, "run_status": true, "all_status": true, "power_status": true, "hr_status": true, "atl_status": false}')
    recovery_metric = Column('recovery_metric', String(10), default='readiness')
    peloton_auto_bookmark_ids = Column('peloton_auto_bookmark_ids', String(9999), default='{}')
    use_run_power = Column('use_run_power', Boolean, default=True)
    use_cycle_power = Column('use_cycle_power', Boolean, default=True)
    spotify_playlists_switch = Column('spotify_playlists_switch', Boolean, default=False)
    spotify_use_rec_intensity = Column('spotify_use_rec_intensity', Boolean(), default=True)
    spotify_time_period = Column('spotify_time_period', String(20), default='all')
    spotify_num_playlists = Column('spotify_num_playlists', Integer(), default=3)


class workoutStepLog(Base):
    __tablename__ = 'workout_step_log'
    id = Column('id', Integer(), index=True, primary_key=True, autoincrement=True)
    athlete_id = Column('athlete_id', Integer())
    date = Column('date', Date())
    workout_step = Column('workout_step', Integer())
    workout_step_desc = Column('workout_step_desc', String(20))
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
    timestamp_utc = Column('timestamp_utc', DateTime())
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
    ftp = Column('ftp', Float())
    watts_per_kg = Column('watts_per_kg', Float())
    timestamp_local = Column('timestamp_local', DateTime())
    timestamp_utc = Column('timestamp_utc', DateTime())
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
    calories = Column('calories', Float())
    device_name = Column('device_name', String(255))
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
    mod_intensity_seconds = Column('mod_intensity_seconds', Integer())
    high_intensity_seconds = Column('high_intensity_seconds', Integer())
    workout_intensity = Column('workout_intensity', String(4))
    weight = Column('weight', Float())


class strydSummary(Base):
    __tablename__ = 'stryd_summary'
    start_date_local = Column('start_date_local', DateTime(), index=True, primary_key=True)
    strava_activity_id = Column('strava_activity_id', BigInteger())
    stryd_ftp = Column('stryd_ftp', Float())
    total_elevation_gain = Column('total_elevation_gain', Float())
    total_elevation_loss = Column('total_elevation_loss', Float())
    max_elevation = Column('max_elevation', Float())
    min_elevation = Column('min_elevation', Float())
    average_cadence = Column('average_cadence', Integer())
    max_cadence = Column('max_cadence', Integer())
    min_cadence = Column('min_cadence', Integer())
    average_stride_length = Column('average_stride_length', Float())
    max_stride_length = Column('max_stride_length', Float())
    min_stride_length = Column('min_stride_length', Float())
    average_ground_time = Column('average_ground_time', Float())
    max_ground_time = Column('max_ground_time', Integer())
    min_ground_time = Column('min_ground_time', Integer())
    average_oscillation = Column('average_oscillation', Float())
    max_oscillation = Column('max_oscillation', Float())
    min_oscillation = Column('min_oscillation', Float())
    average_leg_spring = Column('average_leg_spring', Float())
    max_vertical_stiffness = Column('max_vertical_stiffness', Float())
    rss = Column('rss', Float())
    stryds = Column('stryds', Float())
    elevation = Column('elevation', Float())
    temperature = Column('temperature', Float())
    humidity = Column('humidity', Integer())
    windBearing = Column('windBearing', Integer())
    windSpeed = Column('windSpeed', Float())
    windGust = Column('windGust', Float())
    dewPoint = Column('dewPoint', Float())


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
    rest_mode_state = Column('rest_mode_state', Integer())


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
    rest_mode_state = Column('rest_mode_state', Integer())


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


# class correlations(Base):
#     __tablename__ = 'correlations'
#     Metric = Column('Metric', String(), index=True, primary_key=True)
#
#     Average_METs_prev = Column('Average METs (prev)', Float())
#     Average_METs = Column('Average METs', Float())
#     Average_METs_next = Column('Average METs (next)', Float())
#
#     Activity_burn_prev = Column('Activity burn (prev)', Float())
#     Activity_burn = Column('Activity burn', Float())
#     Activity_burn_next = Column('Activity burn (next)', Float())
#
#     Total_burn_prev = Column('Total burn (prev)', Float())
#     Total_burn = Column('Total burn', Float())
#     Total_burn_next = Column('Total burn (next)', Float())
#
#     Walking_equivalent_prev = Column('Walking equivalent (prev)', Float())
#     Walking_equivalent = Column('Walking equivalent', Float())
#     Walking_equivalent_next = Column('Walking equivalent (next)', Float())
#
#     High_activity_time_prev = Column('High activity time (prev)', Float())
#     High_activity_time = Column('High activity time', Float())
#     High_activity_time_next = Column('High activity time (next)', Float())
#
#     Inactive_time_prev = Column('Inactive time (prev)', Float())
#     Inactive_time = Column('Inactive time', Float())
#     Inactive_time_next = Column('Inactive time (next)', Float())
#
#     Low_activity_time_prev = Column('Low activity time (prev)', Float())
#     Low_activity_time = Column('Low activity time', Float())
#     Low_activity_time_next = Column('Low activity time (next)', Float())
#
#     Med_activity_time_prev = Column('Med activity time (prev)', Float())
#     Med_activity_time = Column('Med activity time', Float())
#     Med_activity_time_next = Column('Med activity time (next)', Float())
#
#     Non_wear_time_prev = Column('Non-wear time (prev)', Float())
#     Non_wear_time = Column('Non-wear time', Float())
#     Non_wear_time_next = Column('Non-wear time (next)', Float())
#
#     Rest_time_prev = Column('Rest time (prev)', Float())
#     Rest_time = Column('Rest time', Float())
#     Rest_time_next = Column('Rest time (next)', Float())
#
#     Activity_score_prev = Column('Activity score (prev)', Float())
#     Activity_score = Column('Activity score', Float())
#     Activity_score_next = Column('Activity score (next)', Float())
#
#     Steps_prev = Column('Steps (prev)', Float())
#     Steps = Column('Steps', Float())
#     Steps_next = Column('Steps (next)', Float())
#
#     Total_activity_time_prev = Column('Total activity time (prev)', Float())
#     Total_activity_time = Column('Total activity time', Float())
#     Total_activity_time_next = Column('Total activity time (next)', Float())
#
#     Readiness_score_prev = Column('Readiness score (prev)', Float())
#     Readiness_score = Column('Readiness score', Float())
#     Readiness_score_next = Column('Readiness score (next)', Float())
#
#     Time_awake_in_bed_prev = Column('Time awake in bed (prev)', Float())
#     Time_awake_in_bed = Column('Time awake in bed', Float())
#     Time_awake_in_bed_next = Column('Time awake in bed (next)', Float())
#
#     Late_to_bedtime_prev = Column('Late to bedtime (prev)', Float())
#     Late_to_bedtime = Column('Late to bedtime', Float())
#     Late_to_bedtime_next = Column('Late to bedtime (next)', Float())
#
#     Respiratory_rate_prev = Column('Respiratory rate (prev)', Float())
#     Respiratory_rate = Column('Respiratory rate', Float())
#     Respiratory_rate_next = Column('Respiratory rate (next)', Float())
#
#     Deep_sleep_prev = Column('Deep sleep (prev)', Float())
#     Deep_sleep = Column('Deep sleep', Float())
#     Deep_sleep_next = Column('Deep sleep (next)', Float())
#
#     Time_in_bed_prev = Column('Time in bed (prev)', Float())
#     Time_in_bed = Column('Time in bed', Float())
#     Time_in_bed_next = Column('Time in bed (next)', Float())
#
#     Sleep_efficiency_prev = Column('Sleep efficiency (prev)', Float())
#     Sleep_efficiency = Column('Sleep efficiency', Float())
#     Sleep_efficiency_next = Column('Sleep efficiency (next)', Float())
#
#     Average_HR_prev = Column('Average HR (prev)', Float())
#     Average_HR = Column('Average HR', Float())
#     Average_HR_next = Column('Average HR (next)', Float())
#
#     Lowest_HR_prev = Column('Lowest HR (prev)', Float())
#     Lowest_HR = Column('Lowest HR', Float())
#     Lowest_HR_next = Column('Lowest HR (next)', Float())
#
#     Light_sleep_prev = Column('Light sleep (prev)', Float())
#     Light_sleep = Column('Light sleep', Float())
#     Light_sleep_next = Column('Light sleep (next)', Float())
#
#     Sleep_midpoint_prev = Column('Sleep midpoint (prev)', Float())
#     Sleep_midpoint = Column('Sleep midpoint', Float())
#     Sleep_midpoint_next = Column('Sleep midpoint (next)', Float())
#
#     Sleep_latency_prev = Column('Sleep latency (prev)', Float())
#     Sleep_latency = Column('Sleep latency', Float())
#     Sleep_latency_next = Column('Sleep latency (next)', Float())
#
#     REM_sleep_prev = Column('REM sleep (prev)', Float())
#     REM_sleep = Column('REM sleep', Float())
#     REM_sleep_next = Column('REM sleep (next)', Float())
#
#     Restlessness_prev = Column('Restlessness (prev)', Float())
#     Restlessness = Column('Restlessness', Float())
#     Restlessness_next = Column('Restlessness (next)', Float())
#
#     Average_HRV_prev = Column('Average HRV (prev)', Float())
#     Average_HRV = Column('Average HRV', Float())
#     Average_HRV_next = Column('Average HRV (next)', Float())
#
#     Sleep_score_prev = Column('Sleep score (prev)', Float())
#     Sleep_score = Column('Sleep score', Float())
#     Sleep_score_next = Column('Sleep score (next)', Float())
#
#     Temp_deviation_prev = Column('Temp. deviation (prev)', Float())
#     Temp_deviation = Column('Temp. deviation', Float())
#     Temp_deviation_next = Column('Temp. deviation (next)', Float())
#
#     Total_sleep_prev = Column('Total sleep (prev)', Float())
#     Total_sleep = Column('Total sleep', Float())
#     Total_sleep_next = Column('Total sleep (next)', Float())


class spotifyPlayHistory(Base):
    __tablename__ = 'spotify_play_history'
    timestamp_utc = Column('timestamp_utc', DateTime(), index=True, primary_key=True)
    track_id = Column('track_id', String(255))
    track_name = Column('track_name', String(255))
    track_url = Column('track_url', String(255))
    explicit = Column('explicit', Boolean())
    artist_id = Column('artist_id', String(255))
    artist_name = Column('artist_name', String(255))
    album_id = Column('album_id', String(255))
    album_name = Column('album_name', String(255))
    analysis_url = Column('analysis_url', String(255))
    duration_ms = Column('duration_ms', Integer())
    acousticness = Column('acousticness', Float())
    danceability = Column('danceability', Float())
    energy = Column('energy', Float())
    instrumentalness = Column('instrumentalness', Float())
    key = Column('key', Integer())
    liveness = Column('liveness', Float())
    loudness = Column('loudness', Float())
    mode = Column('mode', Integer())
    speechiness = Column('speechiness', Float())
    tempo = Column('tempo', Float())
    time_signature = Column('time_signature', Integer())
    valence = Column('valence', Float())
    percentage_listened = Column('percentage_listened', Float())
    skipped = Column('skipped', Boolean())
    rewound = Column('rewound', Boolean())
    fast_forwarded = Column('fast_forwarded', Boolean())
    secs_playing = Column('secs_playing', Integer())
    secs_paused = Column('secs_paused', Integer())


class apiTokens(Base):
    __tablename__ = 'api_tokens'
    date_utc = Column('date_utc', DateTime(), index=True, primary_key=True)
    service = Column('service', String(255))
    tokens = Column('tokens', PickleType)


class dbRefreshStatus(Base):
    __tablename__ = 'db_refresh'
    timestamp_utc = Column('timestamp_utc', DateTime(), index=True, primary_key=True)
    refresh_method = Column('refresh_method', String(255))
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


class fitbod_muscles(Base):
    __tablename__ = 'fitbod_muscles'
    exercise = Column('Exercise', String(255), index=True, primary_key=True)
    muscle = Column('Muscle', String(255))
