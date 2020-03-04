import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_daq as daq
from ..api.ouraAPI import oura_connected
from ..api.stravaApi import strava_connected
from ..api.withingsAPI import withings_connected
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

config = configparser.ConfigParser()
config.read('./config.ini')

def get_layout(**kwargs):
    return html.Div(id='settings-canvas', children=[
        html.Div(id='settings-layout'),
        html.Div(id='clear-log-dummy', style={'display': 'none'}),
        dbc.Modal(id="settings-modal", centered=True, autoFocus=True, fade=False, backdrop=True, size='sm', is_open=True,
                  children=[
                      dbc.ModalHeader("Enter Admin Password"),
                      dbc.ModalBody(dcc.Input(id='settings-password', type='password', placeholder='Password', value='')),
                      dbc.ModalFooter(html.Div([
                          dcc.Link(html.Button("Close", id='close-button', n_clicks=0, style={'marginRight': '1vw'}),
                                   href='/pages/home'),
                          html.Button("Submit", id="submit-settings-button", n_clicks=0, className="ml-auto")
                      ])),
                  ])
    ])


def check_oura_connection():
    # If not connected, send to auth app page to start token request
    if not oura_connected():
        return html.A(style={'textAlign': 'center'}, children=[
            html.Button('Connect Oura', style={'textAlign': 'center', 'marginBottom': '2%'})],
                      href='/pages/authorize/oura')
    else:
        return html.I('Oura Connected!')


def check_strava_connection():
    # If not connected, send to auth app page to start token request
    if not strava_connected():
        return html.A(style={'textAlign': 'center'}, children=[
            html.Button('Connect Strava', style={'textAlign': 'center', 'marginBottom': '2%'})],
                      href='/pages/authorize/strava')
    else:
        return html.I('Strava Connected!')


def check_withings_connection():
    # If not connected, send to auth app page to start token request
    if not withings_connected():
        return html.A(style={'textAlign': 'center'}, children=[
            html.Button('Connect Withings', style={'textAlign': 'center', 'marginBottom': '2%'})],
                      href='/pages/authorize/withings')
    else:
        return html.I('Withings Connected!')


def pull_latest_power_zones():
    # TODO: Switch over to using Critical Power for everything once we get the critical power model working
    session, engine = db_connect()
    # cftp = pd.read_sql(
    #     sql=session.query(stravaSummary.ftp).filter(stravaSummary.type.like('ride')).statement, con=engine)
    # cftp = int(cftp.loc[cftp.index.max()].fillna(0)['ftp']) if len(cftp) > 0 else 0

    # Use last ftp test ride so power zones shows immideately here after workout is done (and you don't have to wait for 1 more since ftp doesnt take 'effect' until ride after ftp test)
    cftp = pd.read_sql(
        sql=session.query(stravaSummary.average_watts).filter(stravaSummary.type.like('ride'),
                                                              stravaSummary.name.like('%ftp test%')).statement,
        con=engine)
    cftp = round(int(cftp.loc[cftp.index.max()].fillna(0)['average_watts']) * .95) if len(cftp) > 0 else 0

    rftp = pd.read_sql(
        sql=session.query(stravaSummary.ftp).filter(stravaSummary.type.like('run')).statement, con=engine)
    rftp = int(rftp.loc[rftp.index.max()].fillna(0)['ftp']) if len(rftp) > 0 else 0
    athlete_info = session.query(athlete).filter(athlete.athlete_id == 1).first()

    engine.dispose()
    session.close()

    cycle_power_zone_threshold_1 = athlete_info.cycle_power_zone_threshold_1
    cycle_power_zone_threshold_2 = athlete_info.cycle_power_zone_threshold_2
    cycle_power_zone_threshold_3 = athlete_info.cycle_power_zone_threshold_3
    cycle_power_zone_threshold_4 = athlete_info.cycle_power_zone_threshold_4
    cycle_power_zone_threshold_5 = athlete_info.cycle_power_zone_threshold_5
    cycle_power_zone_threshold_6 = athlete_info.cycle_power_zone_threshold_6
    run_power_zone_threshold_1 = athlete_info.run_power_zone_threshold_1
    run_power_zone_threshold_2 = athlete_info.run_power_zone_threshold_2
    run_power_zone_threshold_3 = athlete_info.run_power_zone_threshold_3
    run_power_zone_threshold_4 = athlete_info.run_power_zone_threshold_4

    return [html.H4('Current Power Zones', className='nospace height-10'),
            html.Div(className='twelve columns nospace', children=[
                generate_goal(id='ftp-test-notification-threshold', title='FTP Retest Notification (weeks)',
                              value=athlete_info.ftp_test_notification_week_threshold),
            ]),

            html.Div(className='six columns nospace', children=[
                html.H5('Cycling FTP: {}'.format(cftp), className='twelve columns nospace'),
                html.H6('Zone 1: {:.0f}'.format((cftp * cycle_power_zone_threshold_1)),
                        className='twelve columns nospace'),
                html.H6(
                    'Zone 2: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_1) + 1,
                                                     cftp * cycle_power_zone_threshold_2),
                    className='twelve columns nospace'),
                html.H6(
                    'Zone 3: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_2) + 1,
                                                     cftp * cycle_power_zone_threshold_3),
                    className='twelve columns nospace'),
                html.H6(
                    'Zone 4: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_3) + 1,
                                                     cftp * cycle_power_zone_threshold_4),
                    className='twelve columns nospace'),
                html.H6(
                    'Zone 5: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_4) + 1,
                                                     cftp * cycle_power_zone_threshold_5),
                    className='twelve columns nospace'),
                html.H6(
                    'Zone 6: {:.0f} - {:.0f}'.format((cftp * cycle_power_zone_threshold_5) + 1,
                                                     cftp * cycle_power_zone_threshold_6),
                    className='twelve columns nospace'),
                html.H6('Zone 7: > {:.0f}'.format((cftp * cycle_power_zone_threshold_6) + 1),
                        className='twelve columns nospace')
            ]),

            html.Div(className='six columns nospace', children=[
                html.H5('Running FTP: {}'.format(rftp), className='twelve columns nospace'),
                html.H6('Zone 1: {:.0f}'.format((rftp * run_power_zone_threshold_1)),
                        className='twelve columns nospace'),
                html.H6(
                    'Zone 2: {:.0f} - {:.0f}'.format((rftp * run_power_zone_threshold_1) + 1,
                                                     rftp * run_power_zone_threshold_2),
                    className='twelve columns nospace'),
                html.H6(
                    'Zone 3: {:.0f} - {:.0f}'.format((rftp * run_power_zone_threshold_2) + 1,
                                                     rftp * run_power_zone_threshold_3),
                    className='twelve columns nospace'),
                html.H6(
                    'Zone 4: {:.0f} - {:.0f}'.format((rftp * run_power_zone_threshold_3) + 1,
                                                     rftp * run_power_zone_threshold_4),
                    className='twelve columns nospace'),

                html.H6('Zone 5: > {:.0f}'.format((rftp * run_power_zone_threshold_4) + 1),
                        className='twelve columns nospace')
            ])

            ]


def pull_latest_hr_zones():
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

    return [html.H4('Current Heart Rate Zones', className='nospace height-10'),
            html.Div(className='twelve columns nospace height-90', children=[
                html.H6('Based of Resting Heart Rate: {}'.format(rhr), className='nospace'),
                html.H6('Aerobic Z1: <= {:.0f}'.format(z1), className='twelve columns nospace'),
                html.H6('Aerobic Z2 : {:.0f} - {:.0f}'.format(z1 + 1, z2),
                        className='twelve columns nospace'),
                html.H6('Aerobic Z3: {:.0f} - {:.0f}'.format(z2 + 1, z3),
                        className='twelve columns nospace'),
                html.H6('Anaerobic Z4: {:.0f} - {:.0f}'.format(z3 + 1, z4),
                        className='twelve columns nospace'),
                html.H6('Anaerobic Z5: >= {:.0f}'.format(z4 + 1), className='twelve columns nospace')
            ])
            ]


def generate_goal(id, title, value):
    return (
        html.Div(id=id, className='twelve columns', children=[
            html.H6(title, className='nospace', style={'display': 'inline-block'}),
            dcc.Input(id=id + '-input', className='goalinput', type='text', value=value),

            html.Button(id=id + '-input-submit', className='fa fa-upload',
                        style={'paddingLeft': '1vw', 'paddingRight': '0vw', 'display': 'inline-block',
                               'border': '0px'}),

            html.I(id=id + '-input-status', className='fa fa-check',
                   style={'display': 'inline-block', 'color': 'rgb(66,66,66)', 'paddingLeft': '1vw',
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
    return [
        html.H4('Workout Goals', className='twelve columns'),
        generate_goal(id='min-workout-time-goal', title='Min. Activity Minutes',
                      value=athlete_info.min_non_warmup_workout_time / 60),
        generate_goal(id='weekly-tss-goal', title='Weekly TSS Goal', value=athlete_info.weekly_tss_goal),
        generate_goal(id='rr-max-goal', title='High Ramp Rate Injury Threshold', value=athlete_info.rr_max_goal),
        generate_goal(id='rr-min-goal', title='Low Ramp Rate Injury Threshold', value=athlete_info.rr_min_goal),

        html.Div(className='twelve columns nospace', children=[
            html.H6('Use weekly TSS for fitness goals', className='nospace',
                    style={'display': 'inline-block', 'paddingRight': '1%'}),
            daq.BooleanSwitch(
                id='use-tss-for-goal-switch',
                on=use_hrv,
                style={'display': 'inline-block'}
            )
        ]),
        html.Div(className='twelve columns nospace', children=[
            html.H6('Use readiness for workout / yoga goals', className='nospace',
                    style={'display': 'inline-block', 'paddingRight': '1%'}),
            daq.BooleanSwitch(
                id='use-readiness-for-goal-switch',
                on=use_readiness,
                style={'display': 'inline-block'}
            )
        ]),
        generate_goal(id='weekly-workout-goal', title='Weekly Workout Goal', value=athlete_info.weekly_workout_goal),
        generate_goal(id='weekly-yoga-goal', title='Weekly Yoga Goal', value=athlete_info.weekly_yoga_goal),
        html.Hr(className='twelve columns nospace', style={'color': 'rgb(220,220,220'}),
        html.H4('Oura Goals', className='twelve columns'),
        generate_goal(id='daily-sleep-goal', title='Daily Sleep Goal (hrs)', value=athlete_info.daily_sleep_hr_target),
        generate_goal(id='weekly-sleep-score-goal', title='Weekly Sleep Score Goal',
                      value=athlete_info.weekly_sleep_score_goal),
        generate_goal(id='weekly-readiness-score-goal', title='Weekly Readiness Score Goal',
                      value=athlete_info.weekly_readiness_score_goal),
        generate_goal(id='weekly-activity-score-goal', title='Weekly Activity Score Goal',
                      value=athlete_info.weekly_activity_score_goal)
    ]


def get_logs():
    logs = ''
    for line in reversed(open("./log.log").readlines()):
        logs += line
    return html.Div(
        style={'textAlign': 'left', "whiteSpace": "pre-wrap", "width": '100%', 'overflow': 'auto', 'height': '100%'},
        children=[logs])


def generate_settings_dashboard():
    return html.Div(id='settings-dashboard', children=[
        html.Div(id='settings-shelf-1', className='twelve columns',
                 style={'backgroundColor': 'rgb(48, 48, 48)', "height": '35vh'},
                 children=[
                     html.Div(id='api connections', className='two columns maincontainer height-100',
                              children=[
                                  html.H4('App Connections', className='nospace height-10'),
                                  dcc.Loading(children=[html.Div(id='api-connections')]
                                              ),
                                  # html.Div(className='twelve columns',
                                  #          style={'paddingBottom': '3vh'}),

                                  html.H4('Database', className='twelve columns nospace height-10'),
                                  html.Div(id='database-settings', className='twelve columns nospace',
                                           style={'height': '60%'}, children=[
                                          html.Div(className='twelve columns', children=[
                                              html.Button('Refresh', id='refresh-db-button', n_clicks=0)]),
                                          html.Div(className='twelve columns', style={'paddingBottom': '1vh'}),
                                          html.Div(className='twelve columns', children=[
                                              dcc.DatePickerSingle(
                                                  id='truncate-date',
                                                  with_portal=True,
                                                  day_size=75,
                                                  style={'textAlign': 'center'},
                                                  className='twelve columns',
                                                  month_format='MMM Do, YYYY',
                                                  placeholder='MMM Do, YYYY',
                                                  date=datetime.today().date()
                                              ),
                                              html.Div(className='twelve columns', style={'paddingBottom': '1vh'}),
                                              html.Div(className='twelve columns', children=[
                                                  html.Button('Truncate After Date', id='truncate-date-db-button',
                                                              n_clicks=0)]),
                                              html.Div(className='twelve columns', style={'paddingBottom': '1vh'}),

                                          ]),
                                          html.Div(className='twelve columns', children=[
                                              html.Button('Reset HRV Plan', id='truncate-hrv-button', n_clicks=0)
                                          ]),
                                          html.Div(className='twelve columns', style={'paddingBottom': '1vh'}),
                                          html.Div(className='twelve columns', children=[
                                              html.Button('Truncate All', id='truncate-db-button', n_clicks=0)]),

                                          html.Div(className='twelve columns', children=[dcc.Loading(children=[
                                              html.Div(id='truncate-refresh-status'),
                                              html.Div(id='refresh-status'),
                                              html.Div(id='truncate-hrv-status'),
                                          ])
                                          ]),
                                      ])
                              ]),
                     html.Div(id='power-zones', className='five columns maincontainer height-100',
                              children=pull_latest_power_zones()),
                     html.Div(id='hr-zones', className='five columns maincontainer height-100',
                              children=pull_latest_hr_zones()),
                 ]),

        html.Div(className='twelve columns', style={'backgroundColor': 'rgb(48, 48, 48)', 'paddingBottom': '1vh'}),

        html.Div(id='settings-shelf-2', className='twelve columns',
                 style={'backgroundColor': 'rgb(48, 48, 48)', "height": '50vh'},
                 children=[
                     html.Div(id='goal-container', className='four columns maincontainer height-100',
                              children=[
                                  # html.H4('Goals', className='nospace height-10'),
                                  dcc.Loading(className='height-100',
                                              children=[html.Div(id='goals', children=goal_parameters())])
                              ]),
                     dcc.Interval(
                         id='interval-component',
                         interval=1 * 1000,  # in milliseconds
                         n_intervals=0
                     ),
                     html.Div(id='logs-container', className='eight columns maincontainer height-100',
                              children=[
                                  html.Div(id='logs-controls', className='twelve columns nospace',
                                           style={'height': '10%'}, children=[
                                          html.Button('Info', id='info-log-button', n_clicks=0,
                                                      style={'marginRight': '1vw'}),
                                          html.Button('Error', id='error-log-button', n_clicks=0,
                                                      style={'marginRight': '1vw'}),
                                          html.Button('Debug', id='debug-log-button', n_clicks=0,
                                                      style={'marginRight': '1vw'}),
                                          html.Button('Clear Logs', id='clear-log-button'),
                                      ]),

                                  html.Div(id='logs', className='twelve columns', style={'height': '90%'}),

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

@app.callback(Output('api-connections', 'children'),
                   [Input('url', 'pathname')])
def update_api_connection_status(pathname):
    if pathname == '/pages/settings':
        return html.Div(children=[
            html.Div(className='twelve columns', children=[check_oura_connection()]),
            html.Div(className='twelve columns', children=[check_strava_connection()]),
            html.Div(className='twelve columns', children=[check_withings_connection()])
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


# Main Dashboard Generation Callback with password modal
@app.callback(
    [Output('settings-layout', 'children'),
     Output('settings-modal', 'is_open')],
    [Input('settings-canvas', 'children'),
     Input('submit-settings-button', 'n_clicks')],
    [State('settings-password', 'value')]
)
def settings_dashboard(dummy, n_clicks, password):
    if n_clicks and n_clicks > 0:
        if password == config.get('settings', 'password'):
            return generate_settings_dashboard(), False
    else:
        return [], True
