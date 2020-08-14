from flask import Flask
from dash import Dash

from .__version__ import __version__
from .utils import get_dash_args_from_flask_config
from sqlalchemy.orm import scoped_session
from .api.database import SessionLocal, engine
from .api.sqlalchemy_declarative import *
import datetime


def create_flask(config_object=f"{__package__}.settings"):
    """Create the Flask instance for this application"""
    server = Flask(__package__)

    # load default settings
    server.config.from_object(config_object)

    # load additional settings that will override the defaults in settings.py. eg
    # $ export FITLY_SETTINGS=/some/path/prod_settings.py
    server.config.from_envvar(
        "FITLY_SETTINGS", silent=True
    )

    return server


def create_dash(server):
    """Create the Dash instance for this application"""
    app = Dash(
        name=__package__,
        server=server,
        suppress_callback_exceptions=True,
        **get_dash_args_from_flask_config(server.config),
    )

    # Update the Flask config a default "TITLE" and then with any new Dash
    # configuration parameters that might have been updated so that we can
    # access Dash config easily from anywhere in the project with Flask's
    # 'current_app'
    server.config.setdefault("TITLE", "Dash")
    server.config.update({key.upper(): val for key, val in app.config.items()})

    app.title = server.config["TITLE"]

    app.session = scoped_session(SessionLocal)

    if "SERVE_LOCALLY" in server.config:
        app.scripts.config.serve_locally = server.config["SERVE_LOCALLY"]
        app.css.config.serve_locally = server.config["SERVE_LOCALLY"]

    return app


def db_startup(app):
    athlete_exists = True if len(app.session.query(athlete).all()) > 0 else False
    # If no athlete created in db, create one
    if not athlete_exists:
        dummy_athlete = athlete(
            min_non_warmup_workout_time=900,
            weekly_tss_goal=150,
            rr_max_goal=8,
            rr_min_goal=5,
            weekly_workout_goal=3,
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
        app.session.add(dummy_athlete)
        app.session.commit()

    db_refresh_record = True if len(app.session.query(dbRefreshStatus).all()) > 0 else False
    # Insert initial system load refresh record
    if not db_refresh_record:
        dummy_db_refresh_record = dbRefreshStatus(
            timestamp_utc=datetime.utcnow(),
            refresh_method='system',
            oura_status='System Startup',
            strava_status='System Startup',
            withings_status='System Startup',
            fitbod_status='System Startup')
        app.session.add(dummy_db_refresh_record)
        app.session.commit()

    # If fitbod_muslces table not populated create
    fitbod_muscles_table = True if len(app.session.query(fitbod_muscles).all()) > 0 else False
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
            app.session.add(fitbod_muscles(exercise=exercise, muscle=muscle))
        app.session.commit()
    app.session.remove()
