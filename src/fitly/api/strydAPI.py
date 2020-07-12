import requests
import datetime
import pandas as pd
from ..app import app
from ..utils import config

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
def get_stryd_df_summary():
    sessionID = auth_stryd_session()
    today = datetime.datetime.now() + datetime.timedelta(days=1) # Pass tomorrow's date to ensure no issues with timezones
    start = today - datetime.timedelta(days=9999)
    headers = {'Authorization': 'Bearer: {}'.format(sessionID)}
    url = "https://www.stryd.com/b/api/v1/activities/calendar?srtDate={start}&endDate={today}&sortBy=StartDate".format(
        start=start.strftime("%m-%d-%Y"), today=today.strftime("%m-%d-%Y"))
    jsonData = {'srtDate': start.strftime("%m-%d-%Y"), 'endDate': today.strftime("%m-%d-%Y"), 'sortBy': 'StartDate'}

    responseData = requests.get(url, headers=headers, params=jsonData)
    df = pd.DataFrame(responseData.json()['activities'])  # returns summary data for each workout
    df['timestamp'] = df['timestamp'].apply(datetime.datetime.fromtimestamp)
    df.set_index(pd.to_datetime(df['timestamp']), inplace=True)
    # Specify which columns from stryd we want to bring over
    df = df[['ftp', 'stress']]
    df.rename(columns={"ftp": "stryd_ftp", "stress": "RSS"}, inplace=True)
    return df


def get_training_distribution(race=1, gender=1, age=1):
    sessionID = auth_stryd_session()
    headers = {'Authorization': 'Bearer: {}'.format(sessionID)}
    url = f"https://www.stryd.com/b/api/v1/users/runner-attribute?race={race}&gender={gender}&age={age}"
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