import pandas as pd
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from ..app import app
from dash.dependencies import Input, Output, State
from ..api.sqlalchemy_declarative import fitbod, fitbod_muscles
from ..api.database import engine
import math
from datetime import datetime, timedelta, date
from dateutil.relativedelta import *
import dash_bootstrap_components as dbc
from ..utils import config, nextcloud_credentials_supplied
from difflib import SequenceMatcher


def get_layout(**kwargs):
    muscles = sorted(pd.read_sql(sql=app.session.query(fitbod_muscles).statement, con=engine)['Muscle'].unique())
    muscles.append('Unmapped')
    muscle_options = [{'label': x, 'value': x} for x in muscles]
    app.session.remove()
    # Oura data required for home page
    if not nextcloud_credentials_supplied:
        return html.H1('Please provide nextcloud credentials in config', className='text-center')
    else:
        return html.Div([
            html.Div(className='row align-items-center text-center', children=[
                html.Div(className='col-lg-12 mt-2 mb-2', children=[
                    html.Div(id='lifting-date-buttons', children=[
                        dbc.Button('All Time', id='all-button', color='primary', size='sm',
                                   style={'marginRight': '1vw'}),
                        dbc.Button('Year to Date', id='ytd-button', color='primary', size='sm',
                                   style={'marginRight': '1vw'}),
                        dbc.Button('Last 6 Months', id='l6m-button', color='primary', size='sm',
                                   style={'marginRight': '1vw'}),
                        dbc.Button('Last 90 Days', id='l90d-button', color='primary', size='sm',
                                   style={'marginRight': '1vw'}),
                        dbc.Button('Last 6 Weeks', id='l6w-button', color='primary', size='sm',
                                   style={'marginRight': '1vw'}),
                    ]),
                ]),
            ]),
            html.Div(id='lifting-header', className='row align-items-center text-center', children=[
                html.Div(className='col-lg-6 offset-md-3 mt-2 mb-2', children=[

                    dcc.Dropdown(id='muscle-options', className='bg-light',
                                 style={'backgroundColor': 'rgba(0,0,0,0)'},
                                 options=muscle_options,
                                 value=muscles,
                                 multi=True,
                                 placeholder='Select Muscle(s)...'
                                 )
                ]),
            ]),

            html.Div(id='workout-charts', className='col-12', children=[
                dbc.Spinner(color='info', children=[
                    html.Div(className='row', children=[
                        html.Div(id='exercise-containers', className='col-lg-12')
                    ])
                ]),
            ])
        ])


white = config.get('oura', 'white')
teal = config.get('oura', 'teal')
light_blue = config.get('oura', 'light_blue')
dark_blue = config.get('oura', 'dark_blue')
orange = config.get('oura', 'orange')
ftp_color = 'rgb(100, 217, 236)'


def find_muscle(name, muscles):
    '''

    :param name: name of exercise
    :param muscles: dictionary of exercise/muscle mapping
    :return: mapped musle for exercise
    '''
    results = []

    for key, muscle in muscles.items():
        if key in name:
            return muscle

    for key, muscle in muscles.items():
        matcher = SequenceMatcher(None, key, name)
        ratio = matcher.ratio()
        if ratio >= 0.75:
            results.append((ratio, muscle))

    if not results:
        return 'Unmapped'
        app.server.logger.error(f'No matching muscles for: {name}')

    return sorted(results)[0][1]


def generate_exercise_charts(timeframe, muscle_options, sort_ascending=True):
    df = pd.read_sql(sql=app.session.query(fitbod).statement, con=engine)

    # Merge 'muscle' into exercise table for mapping
    muscle_dict = \
        pd.read_sql(sql=app.session.query(fitbod_muscles).statement, con=engine).set_index('Exercise').to_dict()[
            'Muscle']

    df['Muscle'] = df['Exercise'].apply(lambda x: find_muscle(x, muscle_dict))

    app.session.remove()

    # Filter on selected msucles
    df = df[df['Muscle'].isin(muscle_options)]

    # Filter on selected date range
    if timeframe == 'ytd':
        # df = df[df['date_UTC'].dt.date >= date(datetime.today().year, 1, 1)]
        daterange = [date(datetime.today().year, 1, 1), datetime.today().date()]
    elif timeframe == 'l6w':
        # df = df[df['date_UTC'].dt.date >= (datetime.now().date() - timedelta(days=42))]
        daterange = [datetime.now().date() - timedelta(days=42), datetime.today().date()]
    elif timeframe == 'l6m':
        # df = df[df['date_UTC'].dt.date >= (datetime.now().date() - timedelta(months=6))]
        daterange = [datetime.now().date() - relativedelta(months=6), datetime.today().date()]
    elif timeframe == 'l90d':
        daterange = [datetime.now().date() - relativedelta(days=90), datetime.today().date()]
    else:
        # Dummy start date for 'All'
        daterange = [date(1980, 1, 1)]

    if len(df) > 0:
        # Calculate 1RM for exercise that have both weight and reps
        df_1rm = df[(df['Weight']) > 0 & (df['Reps'] > 0)]
        # Calculate Brzycki 1RM based off last 6 weeks of workouts
        df_1rm['1RM'] = (df_1rm['Weight'] * (36 / (37 - df_1rm['Reps'])))
        df_1rm['1RM_Type'] = '1RM (lbs)'

        # Show total Reps for exercises with no weight (where 1RM can't be calculated)
        df_reps = df[(df['Weight'] == 0) & (df['Reps'] != 0) & (df['Duration'] == 0)]
        df_reps['1RM'] = df_reps['Reps']
        df_reps['1RM_Type'] = 'Reps'
        # Remove exercises which have sets both with and without weight to avoid skewing % increases
        df_reps = df_reps[~df_reps['Exercise'].isin(df_1rm['Exercise'].unique())]

        # Show total volume (duration * weight) for time-based exercises (don't have reps so 1RM can't be calculated)
        df_duration = df[(df['Weight'] == 0) & (df['Reps'] == 0) & (df['Duration'] != 0)]
        df_duration['1RM'] = df_duration['Duration'] * df['Weight'].replace(0, 1)
        df_duration['1RM_Type'] = 'Volume'

        # Consolidate dfs
        df = pd.concat([df_1rm, df_reps, df_duration], ignore_index=True)
        # Get max from each set
        df = df.groupby(['date_UTC', 'Exercise', '1RM_Type'])['1RM'].max().reset_index()

        # Sort by % change
        for exercise in df['Exercise'].sort_values().unique():
            df_temp = df[(df['Exercise'] == exercise) & (df['date_UTC'].dt.date >= daterange[0])]
            try:
                percent_change = ((df_temp['1RM'].tail(1).values[0] -
                                   df_temp['1RM'].head(1).values[0]) /
                                  df_temp['1RM'].head(1).values[0]) * 100
            except:
                percent_change = 0
            df.at[df['Exercise'] == exercise, '% Change'] = percent_change

        # Change sort of 'no change' so they show up at bottom
        df.at[df['% Change'] == 0, '% Change'] = 9123456789
        # Sort exercises by areas which have least improvement on a % basis
        df = df.sort_values(by='% Change', ascending=sort_ascending)
        # Change back so correct % Change shows
        df.at[df['% Change'] == 9123456789, '% Change'] = 0

        widgets = []
        for exercise in df['Exercise'].unique():
            df_temp = df[df['Exercise'] == exercise]
            # Only plot exercise if at least 2 different dates with that exercise
            if len(df_temp['date_UTC'].unique()) > 1:
                try:
                    backgroundColor = 'border-danger' if df_temp['% Change'].values[0] < 0 else 'border-success' if \
                        df_temp['% Change'].values[0] > 0 else ''
                except:
                    backgroundColor = ''

                # Sort by date ascending
                df_temp = df_temp.sort_values(by=['date_UTC'])
                tooltip = [df_temp['1RM_Type'].iloc[0] + ':<b>{:.0f}'.format(x) for x in df_temp['1RM']]

                widgets.append([exercise, backgroundColor,
                                dcc.Graph(id=exercise + '-trend',
                                          style={'height': '100%'},
                                          config={'displayModeBar': False, },
                                          figure={
                                              'data': [
                                                  go.Scatter(
                                                      x=df_temp['date_UTC'],
                                                      # y=df_temp['% Change'],
                                                      y=df_temp['1RM'],
                                                      mode='lines+markers',
                                                      text=tooltip,
                                                      hoverinfo='x+text',
                                                      opacity=0.7,
                                                      line={'color': teal},
                                                      line_shape='spline'
                                                  ),
                                              ],
                                              'layout': go.Layout(
                                                  height=150,
                                                  font=dict(
                                                      color='rgb(220,220,220)',
                                                      size=10,
                                                  ),

                                                  # hoverlabel={'font': {'size': 10}},
                                                  xaxis=dict(
                                                      showline=True,
                                                      color='rgb(220,220,220)',
                                                      showgrid=False,
                                                      showticklabels=True,
                                                      tickformat='%b %d',
                                                      # Specify range to get rid of auto x-axis padding when using scatter markers
                                                      range=[df_temp['date_UTC'].min(),
                                                             df_temp[
                                                                 'date_UTC'].max()] if timeframe == 'all' else daterange,
                                                      rangeselector=dict(
                                                          buttons=list([
                                                              dict(step="all",
                                                                   label="All"),
                                                              dict(count=1,
                                                                   label="YTD",
                                                                   step="year",
                                                                   stepmode="todate"),
                                                              dict(count=6,
                                                                   label="L6M",
                                                                   step="month",
                                                                   stepmode="backward"),
                                                              dict(count=42,
                                                                   label="L6W",
                                                                   step="day",
                                                                   stepmode="backward"),
                                                          ]),
                                                          xanchor='center',
                                                          font=dict(
                                                              size=10,
                                                          ),
                                                          x=.5,
                                                          y=1,
                                                      ),
                                                      rangeslider=dict(
                                                          visible=True
                                                      ),
                                                  ),
                                                  yaxis=dict(
                                                      showgrid=False,
                                                      showticklabels=True,
                                                      gridcolor='rgb(73, 73, 73)',
                                                      gridwidth=.5,
                                                      # tickformat='%',

                                                  ),
                                                  margin={'l': 20, 'b': 0, 't': 20, 'r': 20},
                                                  showlegend=False,
                                                  annotations=[
                                                      go.layout.Annotation(
                                                          font={'size': 10},
                                                          bgcolor='rgba(92,89,96,1)',
                                                          x=df_temp.loc[df_temp['date_UTC'].idxmax()]['date_UTC'],
                                                          y=df_temp.loc[df_temp['date_UTC'].idxmax()]['1RM'],
                                                          text="{} {:.0f}%".format(timeframe.upper(),
                                                                                   df_temp.loc[
                                                                                       df_temp['date_UTC'].idxmax()][
                                                                                       '% Change']),
                                                          showarrow=True,
                                                          arrowhead=0,
                                                          arrowcolor=white,
                                                          ax=-20,
                                                          ay=-20,
                                                      )
                                                  ],
                                                  hovermode='x',
                                                  autosize=True,
                                                  # title=exercise
                                              )
                                          })
                                ])

        widgets = [
            html.Div(className='col-lg-2 mb-3', children=[
                dbc.Card(className=backgroundColor, children=[
                    dbc.CardHeader(exercise),
                    dbc.CardBody(
                        style={'padding': '.5rem'},
                        children=chart)
                ])]
                     ) for exercise, backgroundColor, chart in widgets]

        # Set up each div of 6 graphs to be placed in
        num_divs = math.ceil(len(widgets) / 6)
        div_layout = []
        for i in range(0, num_divs):
            children = []
            for widget in widgets[:6]:
                children.append(widget)
                widgets.remove(widget)

            div_layout.append(html.Div(className='row', children=children))
            # div_layout.append(
            #     html.Div(className='row'))

        return div_layout


# Group power profiles
@app.callback([Output('exercise-containers', 'children'),
               Output('all-button', 'style'),
               Output('ytd-button', 'style'),
               Output('l6m-button', 'style'),
               Output('l90d-button', 'style'),
               Output('l6w-button', 'style')],
              [Input('muscle-options', 'value'),
               Input('all-button', 'n_clicks'),
               Input('ytd-button', 'n_clicks'),
               Input('l6m-button', 'n_clicks'),
               Input('l90d-button', 'n_clicks'),
               Input('l6w-button', 'n_clicks')],
              [State('all-button', 'style'),
               State('ytd-button', 'style'),
               State('l6m-button', 'style'),
               State('l90d-button', 'style'),
               State('l6w-button', 'style')]
              )
def update_exercise_charts(muscle_options, all_n_clicks, ytd_n_clicks, l6m_n_clicks, l90d_n_clicks, l6w_n_clicks,
                           all_style, ytd_style,
                           l6m_style, l90d_style, l6w_style):
    latest_dict = {'all-button': 'all', 'ytd-button': 'ytd', 'l6m-button': 'l6m', 'l90d-button': 'l90d',
                   'l6w-button': 'l6w'}
    style = {'all': {'marginRight': '1vw'}, 'ytd': {'marginRight': '1vw'}, 'l6m': {'marginRight': '1vw'},
             'l90d': {'marginRight': '1vw'}, 'l6w': {'marginRight': '1vw'}}
    ctx = dash.callback_context
    if not ctx.triggered:
        latest = 'ytd'
    elif ctx.triggered[0]['prop_id'] == 'muscle-options.value':
        for key, value in {'all': all_style, 'ytd': ytd_style, 'l6m': l6m_style, 'l90d': l90d_style,
                           'l6w': l6w_style}.items():
            if value == {'marginRight': '1vw', 'color': '#64D9EC', 'borderColor': '#64D9EC'}:
                latest = key
    else:
        latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]

    style[latest] = {'marginRight': '1vw', 'color': '#64D9EC', 'borderColor': '#64D9EC'}

    return generate_exercise_charts(timeframe=latest, muscle_options=muscle_options), style['all'], style['ytd'], style[
        'l6m'], style['l90d'], style['l6w']
