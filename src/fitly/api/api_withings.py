from withings_api import WithingsApi
from withings_api.common import get_measure_value, MeasureType, Credentials, CredentialsType
from ..api.sqlalchemy_declarative import apiTokens, withings
from ..api.database import engine
from sqlalchemy import func, delete
from datetime import datetime
import ast
import pandas as pd
import numpy as np
from ..app import app
from ..utils import config
import pickle
from typing import cast

client_id = config.get('withings', 'client_id')
client_secret = config.get('withings', 'client_secret')
redirect_uri = config.get('withings', 'redirect_uri')


def save_withings_token(credentials: CredentialsType) -> None:
    app.server.logger.debug('***** ATTEMPTING TO SAVE TOKENS *****')
    # Delete current tokens
    app.session.execute(delete(apiTokens).where(apiTokens.service == 'Withings'))
    # Insert new tokens
    app.session.add(apiTokens(date_utc=datetime.utcnow(), service='Withings', tokens=pickle.dumps(credentials)))
    app.session.commit()

    app.session.remove()
    app.server.logger.debug('***** SAVED TOKENS *****')


def load_credentials() -> CredentialsType:
    try:
        token_pickle = app.session.query(apiTokens.tokens).filter(apiTokens.service == 'Withings').first().tokens
        creds = cast(CredentialsType, pickle.loads(token_pickle))
        app.session.remove()
    except BaseException as e:
        app.server.logger.error(e)
        creds = None

    return creds


def withings_connected():
    try:
        client = WithingsApi(credentials=load_credentials(), refresh_cb=save_withings_token)
        measures = client.measure_get_meas()
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
        client = WithingsApi(load_credentials(), refresh_cb=save_withings_token)
        df = pd.DataFrame(columns=['date_utc', 'weight', 'fat_ratio', 'hydration'])
        meas_result = client.measure_get_meas(startdate=None, enddate=None, lastupdate=None)
        for x in meas_result.measuregrps:
            date = pd.to_datetime(str(x.date))
            weight = get_measure_value(x, with_measure_type=MeasureType.WEIGHT)
            fat_ratio = get_measure_value(x, with_measure_type=MeasureType.FAT_RATIO)
            hydration = get_measure_value(x, with_measure_type=MeasureType.HYDRATION)

            if weight and fat_ratio:
                df = df.append({'date_utc': date, 'weight': weight, 'fat_ratio': fat_ratio, 'hydration': hydration},
                               ignore_index=True)

        df = df.set_index(df['date_utc'].apply(lambda x: x.replace(tzinfo=None)))

        df = df[['weight', 'fat_ratio', 'hydration']]
        # Convert to lbs
        df['weight'] *= 2.20462

        # Filter to days later than what is already in db
        withings_max_date = app.session.query(func.max(withings.date_utc)).first()[0]
        withings_max_date = datetime.strptime('1991-08-30 00:00:00',
                                              '%Y-%m-%d %H:%M:%S') if not withings_max_date else withings_max_date

        app.session.remove()

        df = df[(df.index > withings_max_date) & (~np.isnan(df['weight'])) & (~np.isnan(df['fat_ratio']))]
        if len(df) > 0:
            app.server.logger.info('New withings measurements found!')
            df.to_sql('withings', engine, if_exists='append', index=True)
