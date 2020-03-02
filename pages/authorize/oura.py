import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash_app import dash_app
import dash_core_components as dcc
from lib.ouraAPI import oura_connected, connect_oura_link
from oura import OuraOAuth2Client
from lib.ouraAPI import save_oura_token
import configparser
import re
import time

config = configparser.ConfigParser()
config.read('config.ini')

client_id = config.get('oura', 'client_id')
client_secret = config.get('oura', 'client_secret')

auth_client = OuraOAuth2Client(client_id=client_id, client_secret=client_secret)

layout = html.Div(id='oura-auth-canvas', children=[
    html.Div(id='oura-token-refresh', style={'display': 'none'}),
    dcc.Loading(html.Div(id='oura-auth-layout'))
])


def test_oura_connection():
    time.sleep(3)
    if not oura_connected():
        return html.Div(style={'textAlign': 'center'}, className='twelve columns', children=[
            html.A(html.Button('Connect'),
                   href=connect_oura_link(auth_client))
        ])
    else:
        return html.I('Oura Connected!')


def generate_oura_auth():
    return [
        html.Div(id='authorize-oura-container', className='twelve columns maincontainer',
                 children=[
                     html.H4('Oura Connection'),
                     html.Div(id='oura-auth', children=[test_oura_connection()]
                              ), ])]


# Callback for authorizing oura tokens
@dash_app.callback(Output('oura-token-refresh', 'children'),
                   [Input('url', 'search')],
                   [State('url', 'pathname')])
def update_tokens(token, pathname):
    if 'oura' in pathname:
        if token:
            auth_code = re.findall('=(?<=\=)(.*?)(?=\&)', token)[0]
            auth_client.fetch_access_token(auth_code)
            save_oura_token(auth_client.session.token)


# Main Dashboard Generation Callback
@dash_app.callback(
    Output('oura-auth-layout', 'children'),
    [Input('oura-auth-canvas', 'children')]
)
def settings_dashboard(dummy):
    return generate_oura_auth()
