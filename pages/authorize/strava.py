import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash_app import dash_app
import dash_core_components as dcc
from lib.stravaApi import get_strava_client, save_strava_token, connect_strava_link, get_strava_client, strava_connected
import configparser
import re
import time
from stravalib.client import Client

config = configparser.ConfigParser()
config.read('config.ini')

client_id = config.get('strava', 'client_id')
client_secret = config.get('strava', 'client_secret')
auth_client = get_strava_client()

layout = html.Div(id='strava-auth-canvas', children=[
    html.Div(id='strava-token-refresh', style={'display': 'none'}),
    dcc.Loading(html.Div(id='strava-auth-layout'))
])


def generate_strava_auth():
    return [
        html.Div(id='authorize-strava-container', className='twelve columns maincontainer',
                 children=[
                     html.H4('Strava Connection'),
                     html.Div(id='strava-auth', children=[test_strava_connection()]
                              ), ])]


# Callback for authorizing strava tokens
@dash_app.callback(Output('strava-token-refresh', 'children'),
                   [Input('url', 'search')],
                   [State('url', 'pathname')])
def update_tokens(token, pathname):
    if 'strava' in pathname:
        if token:
            auth_code = re.findall('=(?<=code\=)(.*?)(?=\&)', token)[0]
            token_response = auth_client.exchange_code_for_token(client_id=client_id, client_secret=client_secret,
                                                                 code=auth_code)
            save_strava_token(token_response)


def test_strava_connection():
    time.sleep(3)
    if not strava_connected():
        return html.Div(style={'textAlign': 'center'}, className='twelve columns', children=[
            html.A(html.Button('Connect'),
                   href=connect_strava_link(auth_client))
        ])
    else:
        return html.I('Strava Connected!')


# Main Dashboard Generation Callback
@dash_app.callback(
    Output('strava-auth-layout', 'children'),
    [Input('strava-auth-canvas', 'children')]
)
def settings_dashboard(dummy):
    return generate_strava_auth()
