import configparser
import requests
import datetime
import pandas as pd
from ..app import app

config = configparser.ConfigParser()
config.read('./config/config.ini')

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
    start = today - datetime.timedelta(days=180)
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
