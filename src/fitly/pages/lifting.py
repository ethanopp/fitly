import pandas as pd
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from ..app import app
from dash.dependencies import Input, Output, State
from ..api.sqlalchemy_declarative import db_connect, fitbod, fitbod_muscles
import configparser
import math
from datetime import datetime, timedelta, date
import dash_bootstrap_components as dbc
import operator


def get_layout(**kwargs):
    return html.Div([
        html.Div(className='row', children=[
            html.Div(className='col-lg-12 text-center mt-2 mb-2', children=[
                html.Div(id='lifting-date-buttons', children=[
                    dbc.Button('All Time', id='all-button', color='primary'),
                    dbc.Button('Year to Date', id='ytd-button', color='primary'),
                    dbc.Button('Last 6 Weeks', id='l6w-button', color='primary'),
                ]),
            ]),
        ]),
        html.Div(id='lifting-header', className='row', children=[
            html.Div(className='col-lg-6 offset-md-3 align-self-center text-center mt-2 mb-2', children=[

                dcc.Dropdown(id='muscle-options', className='nospace bg-light',
                             style={'backgroundColor': 'rgba(0,0,0,0)'},
                             options=[
                                 {'label': 'Abs', 'value': 'Abs'},
                                 {'label': 'Back', 'value': 'Back'},
                                 {'label': 'Biceps', 'value': 'Biceps'},
                                 {'label': 'Chest', 'value': 'Chest'},
                                 {'label': 'Hamstrings', 'value': 'Hamstrings'},
                                 {'label': 'Lower Back', 'value': 'Lower Back'},
                                 {'label': 'Quadriceps', 'value': 'Quadriceps'},
                                 {'label': 'Shoulders', 'value': 'Shoulders'},
                                 {'label': 'Triceps', 'value': 'Triceps'}
                             ],
                             value=['Abs', 'Back', 'Biceps', 'Chest', 'Hamstrings', 'Lower Back', 'Quadriceps',
                                    'Shoulders', 'Triceps'],
                             multi=True,
                             placeholder='Select Muscle(s)...'
                             )
            ]),
        ]),

        html.Div(className='row', children=[
            html.Div(id='exercise-containers', className='col-lg-12')

        ])
    ])


config = configparser.ConfigParser()
config.read('./config.ini')

white = config.get('oura', 'white')
teal = config.get('oura', 'teal')
light_blue = config.get('oura', 'light_blue')
dark_blue = config.get('oura', 'dark_blue')
orange = config.get('oura', 'orange')
ftp_color = 'rgb(100, 217, 236)'


def generate_exercise_charts(timeframe, muscle_options):
    session, engine = db_connect()
    df = pd.read_sql(sql=session.query(fitbod).statement, con=engine)
    engine.dispose()
    session.close()
    # Merge 'muscle' into exercise table for mapping
    df_muscle = pd.read_sql(sql=session.query(fitbod_muscles).statement, con=engine)
    df = df.merge(df_muscle, how='left', left_on='Exercise', right_on='Exercise')

    # Filter on selected msucles
    df = df[df['Muscle'].isin(muscle_options)]

    if len(df) > 0:
        # Calculate Volume and aggregate to the daily (workout) level
        df['Volume'] = df['Reps'].replace(0, 1) * df['Weight'].replace(0, 1) * df['Duration'].replace(0, 1)
        # TODO: Change this to sum all volume at workout level instead of taking max of 1 set
        # df = df.loc[df.groupby(['date_UTC', 'Exercise'])['Volume'].agg(pd.Series.idxmax)].reset_index()
        df = df.groupby(['date_UTC', 'Exercise'])['Volume'].sum().reset_index()

        if timeframe == 'ytd':
            df = df[df['date_UTC'].dt.date >= date(datetime.today().year, 1, 1)]
        elif timeframe == 'l6w':
            df = df[df['date_UTC'].dt.date >= (datetime.now().date() - timedelta(days=42))]

        widgets = []
        for exercise in df['Exercise'].sort_values().unique():
            df_temp = df[df['Exercise'] == exercise]
            try:
                # Calculate overall start to end % change (1 number)
                percent_change = ((df_temp['Volume'].tail(1).values[0] - df_temp['Volume'].head(1).values[0]) / \
                                  df_temp['Volume'].head(1).values[0]) * 100
                backgroundColor = 'border-danger' if percent_change < 0 else 'border-success' if percent_change > 0 else ''
            except:
                backgroundColor = ''

            # Only plot exercise if at least 2 different dates with that exercise
            if len(df_temp['date_UTC'].unique()) > 1:
                # Sort by date ascending
                df_temp = df_temp.sort_values(by=['date_UTC'])
                # Calculate trend of each data point vs starting point
                df_temp['% Change'] = df_temp['Volume'].apply(
                    lambda x: ((x - df_temp['Volume'].head(1)) / df_temp['Volume'].head(1)) * 100)
                tooltip = ['Volume:<b>{:.0f} ({}{:.1f}%)'.format(x, '+' if y >= 0 else '', y) for (x, y) in
                           zip(df_temp['Volume'], df_temp['% Change'])]

                widgets.append([exercise, backgroundColor,
                                dcc.Graph(id=exercise + '-trend',
                                          style={'height': '100%'},
                                          config={'displayModeBar': False, },
                                          figure={
                                              'data': [
                                                  go.Scatter(
                                                      x=df_temp['date_UTC'],
                                                      y=df_temp['% Change'],
                                                      mode='lines+markers',
                                                      text=tooltip,
                                                      hoverinfo='x+text',
                                                      opacity=0.7,
                                                      line={'color': teal}
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
                                                      # range=[df.index.max() - timedelta(days=41),
                                                      #        df.index.max()],
                                                      # rangeselector=dict(
                                                      #     bgcolor='rgb(66, 66, 66)',
                                                      #     bordercolor='#d4d4d4',
                                                      #     borderwidth=.5,
                                                      #     buttons=buttons,
                                                      #     xanchor='center',
                                                      #     x=.5,
                                                      #     y=1,
                                                      # ),
                                                  ),
                                                  yaxis=dict(
                                                      showgrid=False,
                                                      showticklabels=False,
                                                      gridcolor='rgb(73, 73, 73)',
                                                      gridwidth=.5,
                                                      # tickformat='%',

                                                  ),
                                                  margin={'l': 0, 'b': 25, 't': 20, 'r': 0},
                                                  showlegend=False,
                                                  annotations=[
                                                      go.layout.Annotation(
                                                          font={'size': 14},
                                                          x=df_temp.loc[df_temp['date_UTC'].idxmax()]['date_UTC'],
                                                          y=df_temp.loc[df_temp['date_UTC'].idxmax()]['% Change'],
                                                          xref="x",
                                                          yref="y",
                                                          text="{:.1f}%".format(
                                                              df_temp.loc[df_temp['date_UTC'].idxmax()]['% Change']),
                                                          showarrow=True,
                                                          arrowhead=0,
                                                          arrowcolor=white,
                                                          ax=5,
                                                          ay=-20
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
                    dbc.CardBody(chart)
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
               Output('l6w-button', 'style')],
              [Input('muscle-options', 'value'),
               Input('all-button', 'n_clicks'),
               Input('ytd-button', 'n_clicks'),
               Input('l6w-button', 'n_clicks')],
              [State('all-button', 'n_clicks_timestamp'),
               State('ytd-button', 'n_clicks_timestamp'),
               State('l6w-button', 'n_clicks_timestamp')]
              )
def update_exercise_charts(muscle_options, all_n_clicks, ytd_n_clicks, l6w_n_clicks,
                           all_n_clicks_timestamp, ytd_n_clicks_timestamp, l6w_n_clicks_timestamp):
    latest = 'ytd'
    all_style, ytd_style, l6w_style = {'marginRight': '1vw'}, {'marginRight': '1vw'}, {'marginRight': '1vw'}
    all_n_clicks_timestamp = 0 if not all_n_clicks_timestamp else all_n_clicks_timestamp
    ytd_n_clicks_timestamp = 0 if not ytd_n_clicks_timestamp else ytd_n_clicks_timestamp
    l6w_n_clicks_timestamp = 0 if not l6w_n_clicks_timestamp else l6w_n_clicks_timestamp
    timestamps = {'all': all_n_clicks_timestamp, 'ytd': ytd_n_clicks_timestamp, 'l6w': l6w_n_clicks_timestamp}

    if all_n_clicks or ytd_n_clicks or l6w_n_clicks:
        latest = max(timestamps.items(), key=operator.itemgetter(1))[0]

    if latest == 'all':
        all_style = {'marginRight': '1vw', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
    elif latest == 'ytd':
        ytd_style = {'marginRight': '1vw', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
    elif latest == 'l6w':
        l6w_style = {'marginRight': '1vw', 'color': '#64D9EC', 'borderColor': '#64D9EC'}

    return generate_exercise_charts(timeframe=latest, muscle_options=muscle_options), all_style, ytd_style, l6w_style

# TODO: Set up sorting for charts
