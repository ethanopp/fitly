from flask import Flask
from dash import Dash

from .__version__ import __version__
from .utils import get_dash_args_from_flask_config
from sqlalchemy.orm import scoped_session
from .api.database import SessionLocal, engine
from .api.sqlalchemy_declarative import *
from datetime import datetime


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
    Base.metadata.create_all(bind=engine)

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
        dummy_athlete = athlete(name='New User')
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
        for exercise, muscle in [
            # Abs
            ('Crunch', 'Abs'),
            ('Russian Twist', 'Abs'),
            ('Leg Raise', 'Abs'),
            ('Flutter Kicks', 'Abs'),
            ('Sit-Up', 'Abs'),
            ('Side Bridge', 'Abs'),
            ('Scissor Kick', 'Abs'),
            ('Toe Touchers', 'Abs'),
            ('Pallof Press', 'Abs'),
            ('Cable Wood Chop', 'Abs'),
            ('Scissor Crossover Kick', 'Abs'),
            ('Plank', 'Abs'),
            ('Leg Pull-In', 'Abs'),
            ('Knee Raise', 'Abs'),
            ('Bird Dog', 'Abs'),
            ('Dead Bug', 'Abs'),
            ('Dip', 'Abs'),
            ('Abs', 'Abs'),

            # Arms
            ('Tricep', 'Triceps'),
            ('Bench Dips', 'Triceps'),
            ('Dumbbell Floor Press', 'Triceps'),
            ('Dumbbell Kickback', 'Triceps'),
            ('Skullcrusher', 'Triceps'),
            ('Skull Crusher', 'Triceps'),
            ('Tate', 'Triceps'),
            ('bell Curl', 'Biceps'),
            ('EZ-Bar Curl', 'Biceps'),
            ('Hammer Curl', 'Biceps'),
            ('Bicep', 'Biceps'),
            ('Preacher Curl', 'Biceps'),
            ('No Money', 'Biceps'),
            ('Concentration Curls', 'Biceps'),
            ('Zottman', 'Biceps'),
            ('bell Wrist Curl', 'Forearms'),

            # Chest
            ('Cable Crossover Fly', 'Chest'),
            ('Chest', 'Chest'),
            ('Bench Press', 'Chest'),
            ('Machine Fly', 'Chest'),
            ('Decline Fly', 'Chest'),
            ('Dumbbell Fly', 'Chest'),
            ('Push Up', 'Chest'),
            ('Pullover', 'Chest'),
            ('Floor Press', 'Chest'),
            ('Smith Machine Press', 'Chest'),
            ('Svend', 'Chest'),

            # Back
            ('Pulldown', 'Back'),
            ('Pull Down', 'Back'),
            ('Cable Row', 'Back'),
            ('Machine Row', 'Back'),
            ('Bent Over Row', 'Back'),
            ('bell Row', 'Back'),
            ('Pull Up', 'Back'),
            ('Pull-Up', 'Back'),
            ('Pullup', 'Back'),
            ('Chin Up', 'Back'),
            ('Renegade', 'Back'),
            ('Smith Machine Row', 'Back'),
            ('Shotgun Row', 'Back'),
            ('Landmine Row', 'Back'),
            ('Ball Slam', 'Back'),
            ('T-Bar', 'Back'),
            ('Back Extension', 'Lower Back'),
            ('Superman', 'Lower Back'),
            ('Leg Crossover', 'Lower Back'),
            ('Hyperextension', 'Lower Back'),

            ('Stiff-Legged Barbell Good Morning', 'Lower Back'),
            ('Hip', 'Glutes'),
            ('Step Up', 'Glutes'),
            ('Leg Lift', 'Glutes'),
            ('Glute', 'Glutes'),
            ('Rack Pulls', 'Glutes'),
            ('Pull Through', 'Glutes'),
            ('Leg Kickback', 'Glutes'),
            ('Balance Trainer Reverse Hyperextension', 'Glutes'),

            # Soulders
            ('Shoulder', 'Shoulders'),
            ('Lateral', 'Shoulders'),
            ('Face Pull', 'Shoulders'),
            ('Delt', 'Shoulders'),
            ('Elbows Out', 'Shoulders'),
            ('Back Fly', 'Shoulders'),
            ('One-Arm Upright Row', 'Shoulders'),
            ('Dumbbell Raise', 'Shoulders'),
            ('Plate Raise', 'Shoulders'),
            ('Arnold', 'Shoulders'),
            ('Iron Cross', 'Shoulders'),
            ('Push Press', 'Shoulders'),
            ('Landmine Press', 'Shoulders'),
            ('Overhead Press', 'Shoulders'),

            # Neck
            ('Upright Row', 'Traps'),
            ('Barbell Shrug', 'Traps'),
            ('Neck', 'Traps'),

            # Legs
            ('Leg Press', 'Quads'),
            ('Leg Extension', 'Quads'),
            ('Lunge', 'Quads'),
            ('Squat', 'Quads'),
            ('Tuck Jump', 'Quads'),
            ('Mountain Climber', 'Quads'),
            ('Burpee', 'Quads'),
            ('Power Clean', 'Quads'),
            ('Wall Sit', 'Quads'),
            ('bell Clean', 'Hamstrings'),
            ('Leg Curl', 'Hamstrings'),
            ('Deadlift', 'Hamstrings'),
            ('Dumbbell Snatch', 'Hamstrings'),
            ('Swing', 'Hamstrings'),
            ('Morning', 'Hamstrings'),
            ('Calf Raise', 'Calves'),
            ('Heel Press', 'Calves'),
            ('Thigh Abductor', 'Abductors'),
            ('Clam', 'Abductors'),
            ('Thigh Adductor', 'Adductors')
        ]:
            app.session.add(fitbod_muscles(exercise=exercise, muscle=muscle))
        app.session.commit()
    app.session.remove()
