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
import operator


def get_layout(**kwargs):
    return html.Div(id='lifting-canvas', children=[
        html.Div(id='lifting-layout', children=[
            html.Div(id='lifting-header', style={'maxHeight': '15vh'}, className='twelve columns nospace', children=[
    
                html.Div(className='twelve columns', style={'backgroundColor': 'rgb(66, 66, 66)', 'paddingBottom': '1vh'}),
    
                dcc.Dropdown(id='muscle-options', className='nospace',
                             style={'backgroundColor': 'rgb(66, 66, 66)', 'border': '0px'},
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
                             ),
                html.Div(className='twelve columns', style={'backgroundColor': 'rgb(66, 66, 66)', 'paddingBottom': '1vh'}),
    
                html.Div(className='twelve columns nospace',
                         style={'display': 'inline-block', 'textAlign': 'left', 'verticalAlign': 'middle',
                                'paddingLeft': '.5vw', 'backgroundColor': 'rgb(66, 66, 66)'}, children=[
                        html.Div(id='lifting-date-buttons', children=[
                            html.Button('All', id='all-button', style={'marginRight': '1vw'}),
                            html.Button('YTD', id='ytd-button', style={'marginRight': '1vw'}),
                            html.Button('L6W', id='l6w-button'),
                        ]),
                    ]),
                html.Div(className='twelve columns', style={'backgroundColor': 'rgb(66, 66, 66)', 'paddingBottom': '1vh'}),
    
            ]),
    
            html.Div(className='twelve columns', style={'backgroundColor': 'rgb(48, 48, 48)', 'paddingBottom': '1vh'}),
            html.Div(className='twelve columns maincontainer nospace', style={'maxHeight': '75vh'},
                     children=[
    
                         dcc.Loading([
                             html.Div(className='twelve columns',
                                      style={'backgroundColor': 'rgb(66, 66, 66)', 'paddingBottom': '1vh'}),
                             html.Div(className='twelve columns', id='exercise-containers')
                         ])
    
                     ]
    
                     )
        ]),
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
    for exercise in df['Exercise'].unique():
        df_temp = df[df['Exercise'] == exercise]
        try:
            # Calculate overall start to end % change (1 number)
            percent_change = ((df_temp['Volume'].tail(1).values[0] - df_temp['Volume'].head(1).values[0]) / \
                              df_temp['Volume'].head(1).values[0]) * 100
            backgroundColor = 'rgb(100,66,66)' if percent_change < 0 else 'rgb(66,100,66)' if percent_change > 0 else 'rgb(66,66,66)'
        except:
            backgroundColor = 'rgb(66,66,66)'

        # Only plot exercise if at least 2 different dates with that exercise
        if len(df_temp['date_UTC'].unique()) > 1:
            # Sort by date ascending
            df_temp = df_temp.sort_values(by=['date_UTC'])
            # Calculate trend of each data point vs starting point
            df_temp['% Change'] = df_temp['Volume'].apply(
                lambda x: ((x - df_temp['Volume'].head(1)) / df_temp['Volume'].head(1)) * 100)
            tooltip = ['Volume:<b>{:.0f} ({}{:.1f}%)'.format(x, '+' if y >= 0 else '', y) for (x, y) in
                       zip(df_temp['Volume'], df_temp['% Change'])]

            widgets.append(
                html.Div(className='two columns maincontainer height-10', style={'backgroundColor': backgroundColor},
                         children=[
                             dcc.Graph(id=exercise + '-trend', className='twelve columns nospace',
                                       style={'height': '100%'},
                                       config={
                                           'displayModeBar': False,
                                           # 'showLink': True  # to edit in studio
                                       },
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
                                               # title = metricTitle[metric],
                                               plot_bgcolor=backgroundColor,  # plot bg color
                                               paper_bgcolor=backgroundColor,  # margin bg color
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
                                               title=exercise
                                           )
                                       })

                         ])
            )
    # Set up each div of 6 graphs to be placed in
    num_divs = math.ceil(len(widgets) / 6)
    div_layout = []
    for i in range(0, num_divs):
        children = []
        for widget in widgets[:6]:
            children.append(widget)
            widgets.remove(widget)

        div_layout.append(html.Div(className='twelve columns', children=children))
        div_layout.append(
            html.Div(className='twelve columns', style={'backgroundColor': 'rgb(66, 66, 66)', 'paddingBottom': '1vh'}))

    return div_layout


# Group power profiles
@app.callback([Output('exercise-containers', 'children'),
                    Output('all-button', 'style'),
                    Output('ytd-button', 'style'),
                    Output('l6w-button', 'style')],
                   [Input('lifting-canvas', 'children'),
                    Input('muscle-options', 'value'),
                    Input('all-button', 'n_clicks'),
                    Input('ytd-button', 'n_clicks'),
                    Input('l6w-button', 'n_clicks')],
                   [State('all-button', 'n_clicks_timestamp'),
                    State('ytd-button', 'n_clicks_timestamp'),
                    State('l6w-button', 'n_clicks_timestamp')]
                   )
def update_exercise_charts(dummy, muscle_options, all_n_clicks, ytd_n_clicks, l6w_n_clicks,
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
