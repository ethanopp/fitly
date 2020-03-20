from nokia import NokiaApi, NokiaCredentials
from ..api.sqlalchemy_declarative import db_connect, apiTokens, withings
from sqlalchemy import func, delete
from datetime import datetime
import ast
import configparser
import pandas as pd
import numpy as np
from ..app import app

config = configparser.ConfigParser()
config.read('./config/config.ini')

client_id = config.get('withings', 'client_id')
client_secret = config.get('withings', 'client_secret')
redirect_uri = config.get('withings', 'redirect_uri')


def current_token_dict():
    try:
        session, engine = db_connect()
        token_dict = session.query(apiTokens.tokens).filter(apiTokens.service == 'Withings').first()
        token_dict = ast.literal_eval(token_dict[0]) if token_dict else {}
        engine.dispose()
        session.close()
    except BaseException as e:
        app.server.logger.error(e)
        token_dict = {}

    return token_dict


# Function for auto saving withings token_dict to db
def save_withings_token(tokens):
    app.server.logger.debug('***** ATTEMPTING TO SAVE TOKENS *****')

    # Withings API returns the following, when refreshing use this
    try:
        token_dict = {
            'access_token': tokens['access_token'],
            'token_expiry': int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()) + int(
                tokens['expires_in']),
            'token_type': tokens['token_type'],
            'user_id': tokens['userid'],
            'refresh_token': tokens['refresh_token']
        }

    # NokiaCredentials is an object (not dict)... When running for the first time use this (no record in db)
    except:
        token_dict = {
            'access_token': tokens.access_token,
            'token_expiry': tokens.token_expiry,
            'token_type': tokens.token_type,
            'user_id': tokens.user_id,
            'refresh_token': tokens.refresh_token
        }

    session, engine = db_connect()
    # Delete current key
    session.execute(delete(apiTokens).where(apiTokens.service == 'Withings'))
    # Insert new key
    session.add(apiTokens(date_utc=datetime.utcnow(), service='Withings', tokens=str(token_dict)))
    session.commit()

    engine.dispose()
    session.close()
    app.server.logger.debug('***** SAVED TOKENS *****')


def nokia_creds(token_dict):
    '''
    :param token_dict:
    :return: Nokia Credentials Object
    '''
    return NokiaCredentials(client_id=client_id,
                            consumer_secret=client_secret,
                            access_token=token_dict['access_token'],
                            token_expiry=token_dict['token_expiry'],
                            token_type=token_dict['token_type'],
                            user_id=token_dict['user_id'],
                            refresh_token=token_dict['refresh_token'])


def withings_connected():
    token_dict = current_token_dict()
    try:
        if token_dict:
            creds = nokia_creds(token_dict)
            client = NokiaApi(credentials=creds, refresh_cb=save_withings_token)
            measures = client.get_measures(limit=1)
            app.server.logger.debug('Withings Connected')
            return True
    except BaseException as e:
        app.server.logger.error('Withings not connected')
        app.server.logger.error(e)
        return False


## Provide link for button on settings page
def connect_withings_link(auth_client):
    url = auth_client.get_authorize_url()
    return url


def pull_withings_data():
    # UTC dates will get sampled into daily
    if withings_connected():
        client = NokiaApi(nokia_creds(current_token_dict()), refresh_cb=save_withings_token)
        df = pd.DataFrame([measure.__dict__ for measure in client.get_measures()])
        df['date_utc'] = df['date'].apply(
            lambda x: datetime.strptime(str(x.format('YYYY-MM-DD HH:mm:ss')), '%Y-%m-%d %H:%M:%S'))
        df = df.drop(columns=['date'])
        df = df.set_index(df['date_utc'])
        df = df[['weight', 'fat_ratio', 'hydration']]
        # Convert to lbs
        df['weight'] *= 2.20462

        # Filter to days later than what is already in db
        session, engine = db_connect()
        withings_max_date = session.query(func.max(withings.date_utc)).first()[0]
        withings_max_date = datetime.strptime('1991-08-30 00:00:00',
                                              '%Y-%m-%d %H:%M:%S') if not withings_max_date else withings_max_date
        engine.dispose()
        session.close()

        df = df[(df.index > withings_max_date) & (~np.isnan(df['weight'])) & (~np.isnan(df['fat_ratio']))]
        if len(df) > 0:
            app.server.logger.info('New withings measurements found!')
            df.to_sql('withings', engine, if_exists='append', index=True)
