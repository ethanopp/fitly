#! /usr/bin/env python
import owncloud
import os
from ..api.sqlalchemy_declarative import fitbod
from ..api.database import engine
from sqlalchemy import func
import pandas as pd
from ..app import app
from ..utils import config


def pull_fitbod_data():
    app.server.logger.debug('Logging into Nextcloud')
    oc = owncloud.Client(config.get('nextcloud', 'url'))
    # Login to NextCloud
    oc.login(config.get('nextcloud', 'username'), config.get('nextcloud', 'password'))
    # Get filename
    try:
        filepath = oc.list(config.get('nextcloud', 'fitbod_path'))[0].path
        app.server.logger.debug('Fitbod file found')
    except:
        app.server.logger.debug('No fitbod file found on nextcloud')
        filepath = None
    if filepath:
        filename = filepath.split('/')[-1]
        # Download file
        oc.get_file(filepath)
        # Convert file into df
        df = pd.read_csv(filename)

        # Remove non-lifting exercises
        df = df[df['Distance(m)'] == 0]

        df = df[
            (~df['Exercise'].str.contains('Running')) &
            (~df['Exercise'].str.contains('Cycling')) &
            (~df['Exercise'].str.contains('Hiking')) &
            (~df['Exercise'].str.contains('Rowing')) &
            (~df['Exercise'].str.contains('Elliptical')) &
            (~df['Exercise'].str.contains('Stair Stepper')) &
            (~df['Exercise'].str.contains('Foam')) &
            (~df['Exercise'].str.contains('Cat Cow')) &
            (~df['Exercise'].str.contains("Child's Pose")) &
            (~df['Exercise'].str.contains("Downward Dog")) &
            (~df['Exercise'].str.contains("Up Dog")) &
            (~df['Exercise'].str.contains("Stretch")) &
            (~df['Exercise'].str.contains("Butt Kick")) &
            (~df['Exercise'].str.contains("Chest Expansion")) &
            (~df['Exercise'].str.contains("Chin Drop")) &
            (~df['Exercise'].str.contains("Crab Pose")) &
            (~df['Exercise'].str.contains("Dead Hang")) &
            (~df['Exercise'].str.contains("Head Tilt")) &
            (~df['Exercise'].str.contains("Pigeon Pose")) &
            (~df['Exercise'].str.contains("Reach Behind and Open")) &
            (~df['Exercise'].str.contains("Seated Figure Four")) &
            (~df['Exercise'].str.contains("Seated Forward Bend")) &
            (~df['Exercise'].str.contains("Standing Forward Bend")) &
            (~df['Exercise'].str.contains("Shin Box Hip Flexor")) &
            (~df['Exercise'].str.contains("Shin Box Quad")) &
            (~df['Exercise'].str.contains("Single Leg Straight Forward Bend")) &
            (~df['Exercise'].str.contains("Standing Hip Circle")) &
            (~df['Exercise'].str.contains("Walkout")) &
            (~df['Exercise'].str.contains("Walkout to Push Up"))
            ]

        # Create lbs column
        df['Weight'] = df['Weight(kg)'] * 2.20462
        # Modify columns in df as needed
        df['Date_UTC'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        # Rename duration
        df = df.rename(columns={'Duration(s)': 'Duration'})
        # Remove unecessary columns
        df = df[['Date_UTC', 'Exercise', 'Reps', 'Weight', 'Duration', 'isWarmup', 'Note']]
        # Date currently is not unique to exercise set - only unique to workout so should not be used as index
        # Autogenerate index for now until (if?) fitbod updates their export to data to have a PK (timestamp)
        # df = df.set_index('Date_UTC')

        # DB Operations

        max_date = app.session.query(func.max(fitbod.date_utc)).first()[0]
        if max_date:
            max_date = pd.to_datetime(max_date)
            # Filter df to new workouts only for appending table
            df = df[df['Date_UTC'] > max_date]
        # Insert fitbod table into DB
        df.to_sql('fitbod', engine, if_exists='append', index=False)
        app.session.commit()

        app.session.remove()
        # Delete file in local folder
        os.remove(filename)
        # Empty the dir on nextcloud
        oc.delete(filepath)
