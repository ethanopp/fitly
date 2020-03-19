import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_daq as daq
from oura import OuraOAuth2Client
from ..api.ouraAPI import oura_connected, connect_oura_link, save_oura_token
from ..api.stravaApi import strava_connected, get_strava_client, connect_strava_link, save_strava_token
from ..api.withingsAPI import withings_connected, connect_withings_link, save_withings_token
from nokia import NokiaAuth, NokiaApi
from ..api.sqlalchemy_declarative import db_connect, stravaSummary, ouraSleepSummary, athlete, hrvWorkoutStepLog
from ..api.datapull import refresh_database
from sqlalchemy import delete
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime
import configparser
import operator
from ..api.fitlyAPI import hrv_training_workflow
from ..app import app
from flask import current_app as server
import re

config = configparser.ConfigParser()
config.read('./config.ini')

strava_auth_client = get_strava_client()
withings_auth_client = NokiaAuth(config.get('withings', 'client_id'), config.get('withings', 'client_secret'),
                                 callback_uri=config.get('withings', 'redirect_uri'))
oura_auth_client = OuraOAuth2Client(client_id=config.get('oura', 'client_id'),
                                    client_secret=config.get('oura', 'client_secret'))


def get_layout(**kwargs):
    return html.Div([
        html.Div(id='settings-layout'),
        html.Div(id='clear-log-dummy', style={'display': 'none'}),
        html.Div(id='token-dummy', style={'display': 'none'}),
        dbc.Modal(id="settings-modal", centered=True, autoFocus=True, fade=False, backdrop=True, size='sm',
                  is_open=True,
                  children=[
                      dbc.ModalHeader("Enter Admin Password"),
                      dbc.ModalBody(className='text-center', children=[
                          dcc.Input(id='settings-password', type='password', placeholder='Password', value='')]),
                      dbc.ModalFooter(html.Div([
                          dcc.Link(
                              dbc.Button("Close", id='close-button', n_clicks=0, className='mr-2', color='secondary',
                                         size='sm'),
                              href='/home'),
                          dbc.Button("Submit", id="submit-settings-button", n_clicks=0, color='primary', size='sm')
                      ])),
                  ])
    ])


def check_oura_connection():
    # If not connected, send to auth app page to start token request
    if not oura_connected():
        return html.A(className='text-center col-lg-12', children=[
            dbc.Button('Connect Oura', id='connect-oura-button', color='primary', className='text-center mb-2',
                       size='md')],
                      href=connect_oura_link(oura_auth_client))
    else:
        return html.H4('Oura Connected!', className='text-center col-lg-12',)


def check_strava_connection():
    # If not connected, send to auth app page to start token request
    if not strava_connected():
        return html.A(className='text-center col-lg-12', children=[
            dbc.Button('Connect Strava', id='connect-strava-button', color='primary', className='text-center mb-2',
                       size='md')],
                      href=connect_strava_link(get_strava_client()))
    else:
        return html.H4('Strava Connected!', className='text-center col-lg-12',)


def check_withings_connection():
    # If not connected, send to auth app page to start token request
    if not withings_connected():
        return html.A(className='text-center col-lg-12', children=[
            dbc.Button('Connect Withings', id='connect-withings-btton', color='primary', className='text-center mb-2',
                       size='md')],
                      href=connect_withings_link(
                          NokiaAuth(config.get('withings', 'client_id'), config.get('withings', 'client_secret'),
                                    callback_uri=config.get('withings', 'redirect_uri'))))
    else:
        return html.H4('Withings Connected!', className='text-center col-lg-12',)


def generate_cycle_power_zone_card():
    # TODO: Switch over to using Critical Power for everything once we get the critical power model working
    session, engine = db_connect()
    # Use last ftp test ride so power zones shows immideately here after workout is done (and you don't have to wait for 1 more since ftp doesnt take 'effect' until ride after ftp test)
    cftp = pd.read_sql(
        sql=session.query(stravaSummary.average_watts).filter(stravaSummary.type.like('ride'),
                                                              stravaSummary.name.like('%ftp test%')).statement,
        con=engine)
    cftp = round(int(cftp.loc[cftp.index.max()].fillna(0)['average_watts']) * .95) if len(cftp) > 0 else 0
    athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

    engine.dispose()
    session.close()

    cycle_power_zone_threshold_1 = athlete_info.cycle_power_zone_threshold_1
    cycle_power_zone_threshold_2 = athlete_info.cycle_power_zone_threshold_2
    cycle_power_zone_threshold_3 = athlete_info.cycle_power_zone_threshold_3
    cycle_power_zone_threshold_4 = athlete_info.cycle_power_zone_threshold_4
    cycle_power_zone_threshold_5 = athlete_info.cycle_power_zone_threshold_5
    cycle_power_zone_threshold_6 = athlete_info.cycle_power_zone_threshold_6

    return dbc.Card([
        dbc.CardHeader(html.H4('Cycling Power Zones')),
        dbc.CardBody(className='text-center', children=[

            html.H5('Cycling FTP: {}'.format(cftp)),
            html.H6('Zone 1: {:.0f}'.format((cftp * cycle_power_zone_threshold_1)),
                    className='col'),
            html.H6(
                'Zone 2: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_1) + 1,
                                                 cftp * cycle_power_zone_threshold_2),
                className='col'),
            html.H6(
                'Zone 3: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_2) + 1,
                                                 cftp * cycle_power_zone_threshold_3),
                className='col'),
            html.H6(
                'Zone 4: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_3) + 1,
                                                 cftp * cycle_power_zone_threshold_4),
                className='col'),
            html.H6(
                'Zone 5: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_4) + 1,
                                                 cftp * cycle_power_zone_threshold_5),
                className='col'),
            html.H6(
                'Zone 6: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_5) + 1,
                                                 cftp * cycle_power_zone_threshold_6),
                className='col'),
            html.H6('Zone 7: > {:.0f}'.format((cftp * cycle_power_zone_threshold_6) + 1),
                    className='col')
        ])

    ])

    # html.Div(className='col', children=[
    #     generate_goal(id='ftp-test-notification-threshold', title='FTP Retest Notification (weeks)',
    #                   value=athlete_info.ftp_test_notification_week_threshold),
    # ]),


def generate_run_power_zone_card():
    # TODO: Switch over to using Critical Power for everything once we get the critical power model working
    session, engine = db_connect()
    rftp = pd.read_sql(
        sql=session.query(stravaSummary.ftp).filter(stravaSummary.type.like('run')).statement, con=engine)
    rftp = int(rftp.loc[rftp.index.max()].fillna(0)['ftp']) if len(rftp) > 0 else 0
    athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

    engine.dispose()
    session.close()

    run_power_zone_threshold_1 = athlete_info.run_power_zone_threshold_1
    run_power_zone_threshold_2 = athlete_info.run_power_zone_threshold_2
    run_power_zone_threshold_3 = athlete_info.run_power_zone_threshold_3
    run_power_zone_threshold_4 = athlete_info.run_power_zone_threshold_4

    return dbc.Card([
        dbc.CardHeader(html.H4('Running Power Zones')),
        dbc.CardBody(className='text-center', children=[
            html.H5('Running FTP: {}'.format(rftp)),
            html.H6('Zone 1: {:.0f}'.format((rftp * run_power_zone_threshold_1)),
                    className='col'),
            html.H6(
                'Zone 2: {:.0f} - {:.0f}'.format((rftp * run_power_zone_threshold_1) + 1,
                                                 rftp * run_power_zone_threshold_2),
                className='col'),
            html.H6(
                'Zone 3: {:.0f} - {:.0f}'.format((rftp * run_power_zone_threshold_2) + 1,
                                                 rftp * run_power_zone_threshold_3),
                className='col'),
            html.H6(
                'Zone 4: {:.0f} - {:.0f}'.format((rftp * run_power_zone_threshold_3) + 1,
                                                 rftp * run_power_zone_threshold_4),
                className='col'),

            html.H6('Zone 5: > {:.0f}'.format((rftp * run_power_zone_threshold_4) + 1),
                    className='col')
        ])
    ])


def generate_hr_zone_card():
    session, engine = db_connect()
    rhr = pd.read_sql(
        sql=session.query(ouraSleepSummary.hr_lowest).statement,
        con=engine)
    rhr = int(rhr.loc[rhr.index.max()]['hr_lowest']) if len(rhr) > 0 else 0
    athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()
    birthday = athlete_info.birthday

    engine.dispose()
    session.close()

    age = relativedelta(datetime.today(), birthday).years
    max_hr = 220 - age
    hrr = max_hr - rhr

    hr_zone_threshold_1 = athlete_info.hr_zone_threshold_1
    hr_zone_threshold_2 = athlete_info.hr_zone_threshold_2
    hr_zone_threshold_3 = athlete_info.hr_zone_threshold_3
    hr_zone_threshold_4 = athlete_info.hr_zone_threshold_4

    z1 = round((hrr * hr_zone_threshold_1) + rhr)
    z2 = round((hrr * hr_zone_threshold_2) + rhr)
    z3 = round((hrr * hr_zone_threshold_3) + rhr)
    z4 = round((hrr * hr_zone_threshold_4) + rhr)

    return dbc.Card([
        dbc.CardHeader(html.H4('Heart Rate Zones')),
        dbc.CardBody(className='text-center', children=[

            html.H5('Based of Resting Heart Rate: {}'.format(rhr)),
            html.H6('Aerobic Z1: <= {:.0f}'.format(z1), className='col'),
            html.H6('Aerobic Z2 : {:.0f} - {:.0f}'.format(z1 + 1, z2),
                    className='col'),
            html.H6('Aerobic Z3: {:.0f} - {:.0f}'.format(z2 + 1, z3),
                    className='col'),
            html.H6('Anaerobic Z4: {:.0f} - {:.0f}'.format(z3 + 1, z4),
                    className='col'),
            html.H6('Anaerobic Z5: >= {:.0f}'.format(z4 + 1), className='col')

        ])
    ])


def generate_goal(id, title, value):
    return (
        html.Div(id=id, className='col', children=[
            html.H6(title, style={'display': 'inline-block'}),
            dcc.Input(id=id + '-input', className='goalinput ml-2', type='text', value=value),

            html.Button(id=id + '-input-submit', className='fa fa-upload ml-2',
                        style={'display': 'inline-block', 'border': '0px'}),

            html.I(id=id + '-input-status', className='fa fa-check ml-2',
                   style={'display': 'inline-block', 'color': 'rgba(0,0,0,0)',
                          'fontSize': '150%'})
        ])
    )


def goal_parameters():
    session, engine = db_connect()
    athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()
    engine.dispose()
    session.close()
    use_readiness = True if athlete_info.weekly_workout_goal == 99 and athlete_info.weekly_yoga_goal == 99 else False
    use_hrv = True if athlete_info.weekly_workout_goal == 100 and athlete_info.weekly_yoga_goal == 100 else False
    return dbc.Card([
        dbc.CardHeader(html.H4('Goals')),
        dbc.CardBody(className='text-center', children=[
            generate_goal(id='min-workout-time-goal', title='Min. Activity Minutes',
                          value=athlete_info.min_non_warmup_workout_time / 60),
            generate_goal(id='weekly-tss-goal', title='Weekly TSS Goal', value=athlete_info.weekly_tss_goal),
            generate_goal(id='rr-max-goal', title='High Ramp Rate Injury Threshold', value=athlete_info.rr_max_goal),
            generate_goal(id='rr-min-goal', title='Low Ramp Rate Injury Threshold', value=athlete_info.rr_min_goal),

            html.Div(className='col', children=[
                html.H6('Use weekly TSS for fitness goals',
                        style={'display': 'inline-block', 'paddingRight': '1%'}),
                daq.BooleanSwitch(
                    id='use-tss-for-goal-switch',
                    on=use_hrv,
                    style={'display': 'inline-block'}
                )
            ]),
            html.Div(className='col', children=[
                html.H6('Use readiness for workout / yoga goals',
                        style={'display': 'inline-block', 'paddingRight': '1%'}),
                daq.BooleanSwitch(
                    id='use-readiness-for-goal-switch',
                    on=use_readiness,
                    style={'display': 'inline-block'}
                )
            ]),
            generate_goal(id='weekly-workout-goal', title='Weekly Workout Goal',
                          value=athlete_info.weekly_workout_goal),
            generate_goal(id='weekly-yoga-goal', title='Weekly Yoga Goal', value=athlete_info.weekly_yoga_goal),

            generate_goal(id='daily-sleep-goal', title='Daily Sleep Goal (hrs)',
                          value=athlete_info.daily_sleep_hr_target),
            generate_goal(id='weekly-sleep-score-goal', title='Weekly Sleep Score Goal',
                          value=athlete_info.weekly_sleep_score_goal),
            generate_goal(id='weekly-readiness-score-goal', title='Weekly Readiness Score Goal',
                          value=athlete_info.weekly_readiness_score_goal),
            generate_goal(id='weekly-activity-score-goal', title='Weekly Activity Score Goal',
                          value=athlete_info.weekly_activity_score_goal)

        ])
    ])


def get_logs():
    logs = ''
    for line in reversed(open("./log.log").readlines()):
        logs += line
    return html.Div(
        style={'textAlign': 'left', "whiteSpace": "pre-wrap", "width": '100%', 'overflow': 'auto', 'height': '100%'},
        children=[logs])


def generate_settings_dashboard():
    return html.Div([
        html.Div(id='settings-shelf-1', className='row mt-2',
                 children=[
                     html.Div(id='data sources', className='col-lg-3',
                              children=[
                                  dbc.Card(className='mb-2', children=[
                                      dbc.CardHeader(html.H4('App Connections')),
                                      dbc.CardBody(className='text-center', children=html.Div(id='api-connections'))
                                  ]),
                                  dbc.Card(className='mb-2', children=[
                                      dbc.CardHeader(html.H4('Database')),
                                      dbc.CardBody(className='text-center', children=[
                                          html.Div(className='col-12 mb-2', children=[
                                              dbc.Button('Refresh', color='primary', size='md',
                                                         id='refresh-db-button', n_clicks=0)]),
                                          html.Div(className='col-12', children=[
                                              dcc.DatePickerSingle(
                                                  id='truncate-date',
                                                  with_portal=True,
                                                  day_size=75,
                                                  style={'textAlign': 'center'},
                                                  className='mb-2',
                                                  month_format='MMM Do, YYYY',
                                                  placeholder='MMM Do, YYYY',
                                                  date=datetime.today().date()
                                              ),
                                              html.Div(className='col-12 mb-2', children=[
                                                  dbc.Button('Truncate After Date', color='primary', size='md',
                                                             id='truncate-date-db-button',
                                                             n_clicks=0)]),
                                          ]),
                                          html.Div(className='col-12 mb-2', children=[
                                              dbc.Button('Reset HRV Plan', id='truncate-hrv-button', size='md',
                                                         color='primary',
                                                         n_clicks=0)
                                          ]),
                                          html.Div(className='col-12 mb-2', children=[
                                              dbc.Button('Truncate All', id='truncate-db-button', size='md',
                                                         color='primary',
                                                         n_clicks=0)]),
                                          html.Div(className='col-12 mb-2', children=[dcc.Loading(children=[
                                              html.Div(id='truncate-refresh-status'),
                                              html.Div(id='refresh-status'),
                                              html.Div(id='truncate-hrv-status'),
                                          ])
                                          ]),
                                      ])
                                  ]),
                              ]),
                     html.Div(id='cycle-power-zones', className='col-lg-3', children=generate_cycle_power_zone_card()),
                     html.Div(id='run-power-zones', className='col-lg-3', children=generate_run_power_zone_card()),
                     html.Div(id='hr-zones', className='col-lg-3', children=generate_hr_zone_card()),
                 ]),

        html.Div(className='row', children=[
            html.Div(id='goal-container', className='col-lg-4',
                     children=[html.Div(id='goals', children=goal_parameters())]),

            html.Div(id='logs-container', className='col-lg-8',
                     children=[
                         dbc.Card(style={'height': '50vh'}, children=[
                             dbc.CardHeader(className='d-inline-block',
                                            children=[html.H4('Logs', className='d-inline-block mr-2'),
                                                      dbc.Button('Info', id='info-log-button', n_clicks=0,
                                                                 className='mr-2', color='primary', size='sm'),
                                                      dbc.Button('Error', id='error-log-button', n_clicks=0,
                                                                 className='mr-2', color='primary', size='sm'),
                                                      dbc.Button('Debug', id='debug-log-button', n_clicks=0,
                                                                 className='mr-2', color='primary', size='sm', ),
                                                      dbc.Button('Clear Logs', id='clear-log-button',
                                                                 color='primary', size='sm'),
                                                      ]),
                             dbc.CardBody(style={'overflowY': 'scroll'}, children=[
                                 html.Div(id='logs', className='col'),

                                 dcc.Interval(
                                     id='interval-component',
                                     interval=1 * 1000,
                                     # in milliseconds
                                     n_intervals=0
                                 )])
                         ])
                     ])
        ]),
    ])


# Callback for updating ftp test notification threshold
@app.callback([Output('ftp-test-notification-threshold-input-submit', 'style'),
               Output('ftp-test-notification-threshold-input-status', 'style')],
              [Input('ftp-test-notification-threshold-input-submit', 'n_clicks')],
              [State('ftp-test-notification-threshold-input', 'value')])
def set_ftp_threshold(n_clicks, value):
    if n_clicks and n_clicks > 0:
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.ftp_test_notification_week_threshold:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.ftp_test_notification_week_threshold = value
                session.commit()
                success = True
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            app.server.logger.info('Updated ftp week threshold to {}'.format(value))
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating sleep goal
@app.callback([Output('daily-sleep-goal-input-submit', 'style'),
               Output('daily-sleep-goal-input-status', 'style')],
              [Input('daily-sleep-goal-input-submit', 'n_clicks')],
              [State('daily-sleep-goal-input', 'value')])
def sleep_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.daily_sleep_hr_target:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.daily_sleep_hr_target = value
                session.commit()
                success = True
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            app.server.logger.info('Updated daily sleep hour goal to {}'.format(value))
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating min weekly tss goal
@app.callback([Output('weekly-tss-goal-input-submit', 'style'),
               Output('weekly-tss-goal-input-status', 'style')],
              [Input('weekly-tss-goal-input-submit', 'n_clicks')],
              [State('weekly-tss-goal-input', 'value')])
def weekly_tss_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        value = int(value)
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.weekly_tss_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.weekly_tss_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated weekly TSS goal to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating max rr injury threshold
@app.callback([Output('rr-max-goal-input-submit', 'style'),
               Output('rr-max-goal-input-status', 'style')],
              [Input('rr-max-goal-input-submit', 'n_clicks')],
              [State('rr-max-goal-input', 'value')])
def rr_max_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        value = int(value)
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.rr_max_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.rr_max_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated Max Ramp Rate Injury treshold to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating min rr injury threshold
@app.callback([Output('rr-min-goal-input-submit', 'style'),
               Output('rr-min-goal-input-status', 'style')],
              [Input('rr-min-goal-input-submit', 'n_clicks')],
              [State('rr-min-goal-input', 'value')])
def rr_min_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        value = int(value)
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.rr_min_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.rr_min_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated Min Ramp Rate Injury treshold to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating min activity time goal
@app.callback([Output('min-workout-time-goal-input-submit', 'style'),
               Output('min-workout-time-goal-input-status', 'style')],
              [Input('min-workout-time-goal-input-submit', 'n_clicks')],
              [State('min-workout-time-goal-input', 'value')])
def min_workout_time_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        value = int(value) * 60
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.min_non_warmup_workout_time:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.min_non_warmup_workout_time = value
                session.commit()
                success = True
                app.server.logger.info('Updated min time to consider an activity a workout to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating workout goal
@app.callback([Output('weekly-workout-goal-input-submit', 'style'),
               Output('weekly-workout-goal-input-status', 'style')],
              [Input('weekly-workout-goal-input-submit', 'n_clicks')],
              [State('weekly-workout-goal-input', 'value')])
def workout_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.weekly_workout_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.weekly_workout_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated weekly workout goal to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating yoga goal
@app.callback([Output('weekly-yoga-goal-input-submit', 'style'),
               Output('weekly-yoga-goal-input-status', 'style')],
              [Input('weekly-yoga-goal-input-submit', 'n_clicks')],
              [State('weekly-yoga-goal-input', 'value')])
def yoga_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.weekly_yoga_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.weekly_yoga_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated weekly yoga goal to {}'.format(value))
                app.server.logger.info('Updated weekly yoga goal to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating sleep score goal
@app.callback([Output('weekly-sleep-score-goal-input-submit', 'style'),
               Output('weekly-sleep-score-goal-input-status', 'style')],
              [Input('weekly-sleep-score-goal-input-submit', 'n_clicks')],
              [State('weekly-sleep-score-goal-input', 'value')])
def sleep_score_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.weekly_sleep_score_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.weekly_sleep_score_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated weekly sleep score goal to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating readiness score goal
@app.callback([Output('weekly-readiness-score-goal-input-submit', 'style'),
               Output('weekly-readiness-score-goal-input-status', 'style')],
              [Input('weekly-readiness-score-goal-input-submit', 'n_clicks')],
              [State('weekly-readiness-score-goal-input', 'value')])
def readiness_score_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.weekly_readiness_score_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.weekly_readiness_score_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated weekly readiness score goal to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback for updating activity score goal
@app.callback([Output('weekly-activity-score-goal-input-submit', 'style'),
               Output('weekly-activity-score-goal-input-status', 'style')],
              [Input('weekly-activity-score-goal-input-submit', 'n_clicks')],
              [State('weekly-activity-score-goal-input', 'value')])
def activity_score_goal_status(n_clicks, value):
    if n_clicks and n_clicks > 0:
        session, engine = db_connect()
        athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

        if value == athlete_info.weekly_activity_score_goal:
            engine.dispose()
            session.close()
            return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}
        else:
            # Update value in db
            try:
                athlete_info.weekly_activity_score_goal = value
                session.commit()
                success = True
                app.server.logger.info('Updated weekly activity score goal to {}'.format(value))
            except BaseException as e:
                success = False
                app.server.logger.error(e)
            engine.dispose()
            session.close()
            if success:
                return {'display': 'none'}, {'color': 'green', 'paddingLeft': '1vw', 'fontSize': '150%'}
            else:
                return {'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block', 'border': '0px'}, {
                    'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw', 'fontSize': '150%'}


# Callback to prevent both readiness/hrv goal settings to be enabled at the same time
@app.callback(
    Output('use-tss-for-goal-switch', 'disabled'),
    [Input('use-readiness-for-goal-switch', 'on')],
    [State('use-tss-for-goal-switch', 'on')]
)
def disable_hrv(readiness, hrv):
    if not readiness and not hrv:
        return False
    else:
        return readiness


@app.callback(
    Output('use-readiness-for-goal-switch', 'disabled'),
    [Input('use-tss-for-goal-switch', 'on')],
    [State('use-tss-for-goal-switch', 'on')]
)
def disable_readiness(hrv, readiness):
    if not readiness and not hrv:
        return False
    else:
        return hrv


# Callback for showing/hiding workout/yoga goal settings
@app.callback([
    Output('weekly-workout-goal', 'style'),
    Output('weekly-yoga-goal', 'style')],
    [Input('use-readiness-for-goal-switch', 'on'), Input('use-tss-for-goal-switch', 'on')],
    [State('use-readiness-for-goal-switch', 'on'), State('use-tss-for-goal-switch', 'on')]
)
def set_fitness_goals(readiness_dummy, hrv_dummy, readiness_switch, hrv_switch):
    session, engine = db_connect()
    athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

    if readiness_switch:
        style = {'display': 'none'}
        weekly_workout_goal, weekly_yoga_goal = 99, 99
    elif hrv_switch:
        style = {'display': 'none'}
        weekly_workout_goal, weekly_yoga_goal = 100, 100
    else:
        style = {'display': 'inline-block'}
        weekly_workout_goal, weekly_yoga_goal = 3, 3

    try:
        if athlete_info.weekly_yoga_goal != weekly_yoga_goal and athlete_info.weekly_workout_goal != weekly_workout_goal:
            app.server.logger.info('Updating weekly yoga goal to {}'.format(
                weekly_yoga_goal if weekly_yoga_goal != 99 or weekly_yoga_goal != 100 else 'readiness score based'))
            app.server.logger.info('Updating weekly workout goal to {}'.format(
                weekly_workout_goal if weekly_workout_goal != 99 or weekly_workout_goal != 100 else 'readiness score based'))
            athlete_info.weekly_yoga_goal = weekly_yoga_goal
            athlete_info.weekly_workout_goal = weekly_workout_goal
            session.commit()
    except BaseException as e:
        app.server.logger.error(e)
    engine.dispose()
    session.close()

    return style, style


# check API connections
from ..utils import get_url


@app.callback(Output('api-connections', 'children'),
              [Input('submit-settings-button', 'n_clicks')])
def update_api_connection_status(n_clicks):
    if n_clicks and n_clicks > 0:
        return html.Div(children=[
            html.Div(className='row ', children=[check_oura_connection()]),
            html.Div(className='row', children=[check_strava_connection()]),
            html.Div(className='row', children=[check_withings_connection()])
        ])


# Manual Refresh
@app.callback(Output('refresh-status', 'children'),
              [Input('refresh-db-button', 'n_clicks')])
def refresh(n_clicks):
    if n_clicks > 0:
        app.server.logger.info('Manually refreshing database tables...')
        refresh_database(process='manual')
        return html.H6('Refresh Complete')
    return ''


# Truncate hrv_workout_step_log (reset HRV Plan)
@app.callback(Output('truncate-hrv-status', 'children'),
              [Input('truncate-hrv-button', 'n_clicks')],
              [State('truncate-date', 'date')])
def reset_hrv_plan(n_clicks, hrv_date):
    if n_clicks > 0:
        app.server.logger.info('Resetting HRV workout plan workflow to step 0 on {}'.format(hrv_date))
        try:
            session, engine = db_connect()
            session.execute(delete(hrvWorkoutStepLog).where(hrvWorkoutStepLog.date > hrv_date))
            query = session.query(hrvWorkoutStepLog).filter(hrvWorkoutStepLog.date == hrv_date).first()
            query.hrv_workout_step = 0
            query.hrv_workout_step_desc = 'Low'
            query.rationale = 'You manually restarted the hrv workout plan workflow today'
            query.athlete_id = 1
            query.completed = 0
            session.commit()
            min_non_warmup_workout_time = session.query(athlete).filter(
                athlete.athlete_id == 1).first().min_non_warmup_workout_time
            hrv_training_workflow(min_non_warmup_workout_time)
            return html.H6('HRV Plan Reset!')
        except BaseException as e:
            session.rollback()
            app.server.logger.error('Error resetting hrv workout plan: {}'.format(e))
            return html.H6('Error Resetting HRV Plan')
        engine.dispose()
        session.close()
    return ''


# Truncate database
@app.callback(Output('truncate-refresh-status', 'children'),
              [Input('truncate-db-button', 'n_clicks'),
               Input('truncate-date-db-button', 'n_clicks')],
              [State('truncate-date', 'date')])
def truncate_and_refresh(n_clicks, n_clicks_date, truncateDate):
    if n_clicks > 0:
        app.server.logger.info('Manually truncating and refreshing database tables...')
        try:
            refresh_database(process='manual', truncate=True)
            return html.H6('Truncate and Load Complete')
        except:
            return html.H6('Error with Truncate and Load')
    elif n_clicks_date > 0:
        app.server.logger.info(
            'Manually truncating and refreshing database tables after {}...'.format(truncateDate))
        try:
            refresh_database(process='manual', truncateDate=truncateDate)
            return html.H6('Truncate and Load Complete')
        except:
            return html.H6('Error with Truncate and Load')
    return ''


# Refresh Logs Interval
@app.callback(Output('logs', 'children'),
              [Input('interval-component', 'n_intervals')])
def clear_logs(n):
    return get_logs()


# Clear Logs button
@app.callback(Output('clear-log-dummy', 'children'),
              [Input('clear-log-button', 'n_clicks')])
def clear_logs(n_clicks):
    if n_clicks and n_clicks > 0:
        open('./log.log', 'w').close()
        app.server.logger.debug('Logs manually cleared')
    return 'Logs last cleared at {}'.format(datetime.utcnow())


# Set log level
@app.callback([Output('info-log-button', 'style'),
               Output('error-log-button', 'style'),
               Output('debug-log-button', 'style')],
              [Input('info-log-button', 'n_clicks'),
               Input('error-log-button', 'n_clicks'),
               Input('debug-log-button', 'n_clicks')],
              [State('info-log-button', 'n_clicks_timestamp'),
               State('error-log-button', 'n_clicks_timestamp'),
               State('debug-log-button', 'n_clicks_timestamp')]
              )
def set_log_level(info_n_clicks, error_n_clicks, debug_n_clicks, info_n_clicks_timestamp,
                  error_n_clicks_timestamp,
                  debug_n_clicks_timestamp):
    config.read('./config.ini')
    info_style, error_style, debug_style = {'marginRight': '1%'}, {'marginRight': '1%'}, {'marginRight': '1%'}
    info_n_clicks_timestamp = 0 if not info_n_clicks_timestamp else info_n_clicks_timestamp
    error_n_clicks_timestamp = 0 if not error_n_clicks_timestamp else error_n_clicks_timestamp
    debug_n_clicks_timestamp = 0 if not debug_n_clicks_timestamp else debug_n_clicks_timestamp
    timestamps = {'INFO': info_n_clicks_timestamp, 'ERROR': error_n_clicks_timestamp, 'DEBUG': debug_n_clicks_timestamp}

    if info_n_clicks_timestamp != 0 or error_n_clicks_timestamp != 0 or debug_n_clicks_timestamp != 0:
        latest = max(timestamps.items(), key=operator.itemgetter(1))[0]
        config.set('logger', 'level', latest)
        with open('./config.ini', 'w') as configfile:
            config.write(configfile)

        # Set to info to show message in log, then switch to selected level
        app.server.logger.setLevel('INFO')
        app.server.logger.info('Log level set to {}'.format(latest))
        app.server.logger.setLevel(latest)

    current_log_level = config.get('logger', 'level')

    if current_log_level == 'INFO':
        info_style = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
    elif current_log_level == 'ERROR':
        error_style = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
    elif current_log_level == 'DEBUG':
        debug_style = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}

    return info_style, error_style, debug_style


# Auth Callback #
# Callback for authorizing withings tokens
@app.callback(Output('token-dummy', 'children'),
              [Input('submit-settings-button', 'n_clicks')],
              [State(server.config["LOCATION_COMPONENT_ID"], 'search')]
              )
def update_tokens(n_clicks, search):
    if 'oura' in search:
        if not oura_connected():
            search = search.replace('?oura', '')
            auth_code = re.findall('=(?<=code\=)(.*?)(?=\&)', search)[0]
            oura_auth_client.fetch_access_token(auth_code)
            save_oura_token(oura_auth_client.session.token)

    if 'strava' in search:
        if not strava_connected():
            search = search.replace('?strava', '')
            auth_code = re.findall('=(?<=code\=)(.*?)(?=\&)', search)[0]
            token_response = strava_auth_client.exchange_code_for_token(client_id=config.get('strava', 'client_id'),
                                                                        client_secret=config.get('strava',
                                                                                                 'client_secret'),
                                                                        code=auth_code)
        save_strava_token(token_response)

    if 'withings' in search:
        if not withings_connected():
            search = search.replace('?withings', '')
            auth_code = re.findall('=(?<=code\=)(.*?)(?=\&)', search)[0]
            creds = withings_auth_client.get_credentials(auth_code)
            save_withings_token(creds)

    return None


# Main Dashboard Generation Callback with password modal
@app.callback(
    [Output('settings-layout', 'children'),
     Output('settings-modal', 'is_open')],
    [Input('submit-settings-button', 'n_clicks')],
    [State('settings-password', 'value')]
)
def settings_dashboard(n_clicks, password):
    if n_clicks and n_clicks > 0:
        if password == config.get('settings', 'password'):
            return generate_settings_dashboard(), False
    else:
        return [], True
