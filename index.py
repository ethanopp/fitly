from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
from dash_app import dash_app, app
import dash_bootstrap_components as dbc
from pages import performance, home, settings, power, lifting
from pages.authorize import oura, strava, withings
from datetime import datetime, timedelta
from lib.datapull import refresh_database, latest_refresh
import configparser
from lib.notifications import last_body_measurement_notification, last_ftp_test_notification
from lib.util import utc_to_local
from apscheduler.schedulers.background import BackgroundScheduler

config = configparser.ConfigParser()
config.read('./config.ini')

orange = config.get('oura', 'orange')


def get_notifications():
    notifications = []
    dash_app.server.logger.debug('Checking last_body_measurement_notification()')
    last_body_measurement = last_body_measurement_notification()
    if last_body_measurement and len(last_body_measurement) > 0:
        notifications.append(dbc.ModalBody(last_body_measurement))

    dash_app.server.logger.debug('Checking last_cftp_test_notifications()')
    last_cftp_test = last_ftp_test_notification(ftp_type='ride')
    if last_cftp_test and len(last_cftp_test) > 0:
        notifications.append(dbc.ModalBody(last_cftp_test))

    dash_app.server.logger.debug('Checking last_rftp_test_notifications()')
    last_rftp_test = last_ftp_test_notification(ftp_type='run')
    if last_rftp_test and len(last_rftp_test) > 0:
        notifications.append(dbc.ModalBody(last_rftp_test))

    return notifications


def title_nav_layout(current_page):
    default_icon_color = 'rgb(220, 220, 220)'
    selected = 'rgb(100, 217, 236)'
    pages = ['/', '/pages/home', '/pages/insights', '/pages/performance', '/pages/importer',
             '/pages/power', '/pages/settings', '/pages/achievements', '/pages/lifting']
    page_colors = {}
    for page in pages:
        page_colors[page] = default_icon_color
    page_colors[current_page] = selected

    home_color = selected if page_colors['/pages/home'] == selected or page_colors[
        '/'] == selected else default_icon_color

    # Generate notifications and pass length to badge if greater than 0
    notifications = get_notifications()

    notification_style = {'display': 'none'} if len(notifications) == 0 else {'color': orange, 'fontSize': '3rem',
                                                                              'paddingLeft': '1%', 'paddingRight': '0',
                                                                              'border': 0}

    return (html.Div(className='twelve columns', style={'backgroundColor': "rgb(48, 48, 48)"}, children=[
        dcc.Link(
            html.A('Fit.ly', style={'textAlign': 'center', 'fontSize': '6rem', 'textDecoration': 'none',
                                    'color': default_icon_color}),
            style={'textDecoration': 'none'},
            href='/'),
        dcc.Link(html.I(id='home-button', n_clicks=0, className='fa fa-home',
                        style={'color': home_color, 'fontSize': '3rem', 'paddingLeft': '1%'}),
                 href='/pages/home'),
        dbc.Tooltip('Home', target="home-button", className='tooltip'),
        dcc.Link(
            html.I(id='performance-button', n_clicks=0, className='icon fa fa-seedling',
                   style={'color': page_colors['/pages/performance'], 'fontSize': '3rem', 'paddingLeft': '1%'}),
            href='/pages/performance'),
        dbc.Tooltip('Performance Management', target="performance-button", className='tooltip'),
        dcc.Link(
            html.I(id='power-button', n_clicks=0, className='fa fa-bolt',
                   style={'color': page_colors['/pages/power'], 'fontSize': '3rem', 'paddingLeft': '1%'}),
            href='/pages/power'),
        dbc.Tooltip('Power Analysis', target="power-button", className='tooltip'),
        dcc.Link(
            html.I(id='lifting-button', n_clicks=0, className='fa fa-weight-hanging',
                   style={'color': page_colors['/pages/lifting'], 'fontSize': '3rem', 'paddingLeft': '1%'}),
            href='/pages/lifting'),
        dbc.Tooltip('Weight Training', target="lifting-button", className='tooltip'),

        dcc.Link(
            html.I(id='settings-button', n_clicks=0, className='fa fa-sliders-h',
                   style={'color': page_colors['/pages/settings'], 'fontSize': '3rem', 'paddingLeft': '1%'}),
            href='/pages/settings'),
        dbc.Tooltip('Settings', target="settings-button", className='tooltip'),

        ## Alerts
        html.Button(id='notification-button', n_clicks=0, className='fa fa-bell',
                    style=notification_style,
                    children=[dbc.Badge(id='notification-badge', color="light", className="ml-1",
                                        style={'fontSize': '1.5rem', 'verticalAlign': 'top'},
                                        children=[len(notifications)]),
                              ]),
        dbc.Tooltip('Notifications', target="notification-button", className='tooltip'),

    ]),
            html.Div(className='twelve columns', style={'backgroundColor': "rgb(48, 48, 48)"}, children=[
                # dcc.Loading(id='loading-last-refreshed-label',
                #             style={'backgroundColor': "rgb(48, 48, 48)"}, children=[
                html.Div(id='last-refreshed-label', style={'backgroundColor': "rgb(48, 48, 48)"}, children=[
                    'Last Refreshed: {}'.format(
                        datetime.strftime(utc_to_local(latest_refresh()), "%b %d, %Y %I:%M%p"))
                ])
                # ]),
            ]),

            dbc.Modal(id="notifications", centered=True, autoFocus=True, fade=False, backdrop=True, size='sm',
                      children=[
                          dbc.ModalHeader("Notifications"),
                          dbc.ModalBody(get_notifications()),
                          dbc.ModalFooter(
                              dbc.Button("Close", id="close-notification-button", className="ml-auto")
                          ),
                      ])
            )


dash_app.layout = html.Div(id='app-layout', style={'backgroundColor': "rgb(48, 48, 48)"}, children=[
    dcc.Location(id='url', refresh=False),
    # Title
    html.Div(id='title', className='twelve columns',
             style={'backgroundColor': "rgb(48, 48, 48)", 'marginTop': '0%', 'marginBottom': '0%',
                    'display': 'inline-block',  # 'maxHeight': '15vh'
                    },
             children=[
                 html.Button(id='notification-button', style={'display': 'none'})
                 # Dummy button so notification callback does not error out on launch
             ]),
    html.Div(className='twelve columns',
             style={'backgroundColor': 'rgb(48, 48, 48)', 'paddingBottom': '1vh'}),
    html.Div(id='page-content'),
])


# Notification Display Toggle
@dash_app.callback(
    Output("notifications", "is_open"),
    [Input("notification-button", "n_clicks"), Input("close-notification-button", "n_clicks")],
    [State("notifications", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


# Load Navigation Bar
@dash_app.callback(Output('title', 'children'),
                   [Input('url', 'pathname')])
def display_nav_bar(pathname):
    return title_nav_layout(pathname)


# Page Layout Loading
# refresh-page div in title (which gets created on url change, so will always run when navigating)
@dash_app.callback(Output('page-content', 'children'),
                   [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/' or pathname == '/pages/home':
        dash_app.server.logger.debug('Loading home layout')
        layout = home.layout
    elif pathname == '/pages/performance':
        dash_app.server.logger.debug('Loading performance layout')
        layout = performance.layout
    elif pathname == '/pages/power':
        dash_app.server.logger.debug('Loading power layout')
        layout = power.layout
    elif pathname == '/pages/lifting':
        dash_app.server.logger.debug('Loading lifting layout')
        layout = lifting.layout
    elif pathname == '/pages/settings':
        dash_app.server.logger.debug('Loading settings layout')
        layout = settings.layout
    elif pathname == '/pages/authorize/oura':
        dash_app.server.logger.debug('Loading oura authorization layout')
        layout = oura.layout
    elif pathname == '/pages/authorize/strava':
        dash_app.server.logger.debug('Loading strava authorization layout')
        layout = strava.layout
    elif pathname == '/pages/authorize/withings':
        dash_app.server.logger.debug('Loading withings authorization layout')
        layout = withings.layout
    else:
        layout = '404'
    return layout


if config.get('cron', 'hourly_pull') == 'True':
    # Set cron job to pull data every hour
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=refresh_database, trigger="cron", hour='*')
        dash_app.server.logger.info('Starting cron jobs')
        scheduler.start()
    except BaseException as e:
        dash_app.server.logger.error('Error starting cron jobs: {}'.format(e))

if __name__ == '__main__':
    dash_app.run_server(host='0.0.0.0', debug=True, port=8050)
    # dash_app.run_server(host='0.0.0.0', debug=False, port=80, ssl_context=('/keys/cert.crt', '/keys/certkey'))
