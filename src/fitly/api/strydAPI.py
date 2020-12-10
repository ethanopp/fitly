import requests
import datetime
import pandas as pd
from ..app import app
from ..utils import config
from .sqlalchemy_declarative import strydSummary
from ..api.database import engine
from sqlalchemy import func


def auth_stryd_session():
    requestJSON = {"email": config.get('stryd', 'username'), "password": config.get('stryd', 'password')}
    responseData = requests.post("https://www.stryd.com/b/email/signin", json=requestJSON)
    if responseData.status_code != 200:
        app.server.logger.debug("Stryd could not authenticate")
        authenticated = False
        raise Exception("failed password authentication")
    else:
        app.server.logger.debug("Stryd authenticated")
        authenticated = True
        tempData = responseData.json()
        userID = tempData['id']
        sessionID = tempData['token']
    return sessionID


##############################
## get the list of workouts ##
##############################
def pull_stryd_data():
    sessionID = auth_stryd_session()
    today = datetime.datetime.now() + datetime.timedelta(
        days=1)  # Pass tomorrow's date to ensure no issues with timezones
    start = today - datetime.timedelta(days=9999)
    headers = {'Authorization': 'Bearer: {}'.format(sessionID)}
    url = "https://www.stryd.com/b/api/v1/activities/calendar?srtDate={start}&endDate={today}&sortBy=StartDate".format(
        start=start.strftime("%m-%d-%Y"), today=today.strftime("%m-%d-%Y"))
    jsonData = {'srtDate': start.strftime("%m-%d-%Y"), 'endDate': today.strftime("%m-%d-%Y"), 'sortBy': 'StartDate'}

    responseData = requests.get(url, headers=headers, params=jsonData)
    df = pd.DataFrame(responseData.json()['activities'])  # returns summary data for each workout
    df.rename(columns={
        "timestamp": "start_date_local",
        "ftp": "stryd_ftp",
        "stress": "rss"},
        inplace=True)

    df['start_date_local'] = df['start_date_local'].apply(datetime.datetime.fromtimestamp)
    df.set_index(pd.to_datetime(df['start_date_local']), inplace=True)

    # Specify which columns from stryd we want to bring over
    df = df[['stryd_ftp',
             'total_elevation_gain',
             'total_elevation_loss',
             'max_elevation',
             'min_elevation',
             'average_cadence',
             'max_cadence',
             'min_cadence',
             'average_stride_length',
             'max_stride_length',
             'min_stride_length',
             'average_ground_time',
             'max_ground_time',
             'min_ground_time',
             'average_oscillation',
             'max_oscillation',
             'min_oscillation',
             'average_leg_spring',
             'rss',
             'max_vertical_stiffness',
             'stryds',
             'elevation',
             'temperature',
             'humidity',
             'windBearing',
             'windSpeed',
             'windGust',
             'dewPoint']]

    # Filter df for only new records not yet in DB
    last_styrd_date = app.session.query(func.max(strydSummary.start_date_local))[0][0]
    if last_styrd_date:
        df = df[df.index > last_styrd_date]
    if len(df) > 0:
        app.server.logger.info('New stryd workouts found!')
        # Insert into db
        df.to_sql('stryd_summary', engine, if_exists='append', index=True)
        app.session.commit()
    app.session.remove()

    return df


def get_training_distribution(race=1, gender=1, age=1):
    sessionID = auth_stryd_session()
    headers = {'Authorization': 'Bearer: {}'.format(sessionID)}
    url = f"https://www.stryd.com/b/api/v1/users/runner-attribute?race={config.get('stryd', 'compare_against_race_event')}&gender={config.get('stryd', 'compare_against_gender')}&age={config.get('stryd', 'compare_against_age')}"
    responseData = requests.get(url, headers=headers)
    return responseData.json()

#     '''{'attr': {'age': 28,
#           'endurance': 1835,
#           'fatigue_resistance': 1272,
#           'fitness': 3.0895057604261837,
#           'gender': 'male',
#           'muscle_power': 5.38494805940594,
#           'race': '5k',
#           'timestamp': 1594587608,
#           'user_key': 'Eg8KBHVzZXIQgIDkup6d3Ak'},
#  'fatigue_resistance_threshold': 1,
#  'percentile': {'endurance': 0.05242718446601946,
#                 'fatigue_resistance': 0.4,
#                 'fitness': 0.1475728155339806,
#                 'median_endurance': 5361,
#                 'median_fatigue_resistance': 1445,
#                 'median_fitness': 3.9397466897464706,
#                 'median_muscle_power': 6.089743589743589,
#                 'muscle_power': 0.31456310679611654}}
# '''
