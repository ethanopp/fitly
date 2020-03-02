from nokia import NokiaAuth
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash_app import dash_app
import dash_core_components as dcc
from lib.withingsAPI import withings_connected, connect_withings_link
from oura import OuraOAuth2Client
from lib.withingsAPI import save_withings_token
import configparser
import re
import time

from nokia import NokiaAuth, NokiaApi

config = configparser.ConfigParser()
config.read('config.ini')

client_id = config.get('withings', 'client_id')
client_secret = config.get('withings', 'client_secret')
redirect_uri = config.get('withings', 'redirect_uri')

auth_client = NokiaAuth(client_id, client_secret, callback_uri=redirect_uri)

layout = html.Div(id='withings-auth-canvas', children=[
    html.Div(id='withings-token-refresh', style={'display': 'none'}),
    dcc.Loading(html.Div(id='withings-auth-layout'))
])


def test_withings_connection():
    time.sleep(3)
    if not withings_connected():
        return html.Div(style={'textAlign': 'center'}, className='twelve columns', children=[
            html.A(html.Button('Connect'),
                   href=connect_withings_link(auth_client))
        ])
    else:
        return html.I('Withings Connected!')


def generate_withings_auth():
    return [
        html.Div(id='authorize-withings-container', className='twelve columns maincontainer',
                 children=[
                     html.H4('Withings Connection'),
                     html.Div(id='withings-auth', children=[test_withings_connection()]
                              ), ])]


# Callback for authorizing withings tokens
@dash_app.callback(Output('withings-token-refresh', 'children'),
                   [Input('url', 'search')],
                   [State('url', 'pathname')])
def update_tokens(token, pathname):
    if 'withings' in pathname:
        dash_app.server.logger.debug(
            '*******************************************************************************************************************')
        if token:
            auth_code = re.findall('=(?<=\=)(.*?)(?=\&)', token)[0]
            dash_app.server.logger.debug(
                'AUTH CODE = {}'.format(auth_code))

            creds = auth_client.get_credentials(auth_code)
            dash_app.server.logger.debug(
                'CREDS = {}'.format(creds))

            save_withings_token(creds)


# Main Dashboard Generation Callback
@dash_app.callback(
    Output('withings-auth-layout', 'children'),
    [Input('withings-auth-canvas', 'children')]
)
def settings_dashboard(dummy):
    return generate_withings_auth()
