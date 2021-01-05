import pandas as pd
import dash
import dash_table
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from ..app import app
from ..api.spotifyAPI import get_played_tracks
from ..api.database import engine
from ..api.sqlalchemy_declarative import stravaSummary
import plotly.graph_objs as go
from ..utils import config
from sklearn.preprocessing import MinMaxScaler
import operator
import re
from ..utils import spotify_credentials_supplied
import os
import pytz
from tzlocal import get_localzone

transition = int(config.get('dashboard', 'transition'))
default_icon_color = 'rgb(220, 220, 220)'
white = 'rgb(220, 220, 220)'
teal = 'rgb(100, 217, 236)'
light_blue = 'rgb(56, 128, 139)'
dark_blue = 'rgb(39, 77, 86)'
orange = 'rgb(217,100,43)'
grey = 'rgb(50,50,50)'


def get_layout(**kwargs):
    if not spotify_credentials_supplied:
        return html.H1('Spotify not connected', className='text-center')
    else:
        # Get sports that have music listened during the last PoP Ytd
        sports = [x for x in get_played_tracks(pop_time_period='ytd')['workout_type'].unique() if x != '']
        sport_options = [{'label': 'All Sports', 'value': 'all'}]
        sport_options.extend([{'label': re.sub(r"(\w)([A-Z])", r"\1 \2", x), 'value': x} for x in sorted(sports)])

        return html.Div([
            html.Div(children=[
                html.Div(id='music-filter-shelf', className='row align-items-center text-center mt-2 mb-2',
                         children=[
                             html.Div(className='col-lg-4', children=[
                                 dcc.Dropdown(
                                     id='music-time-selector',
                                     options=[
                                         {'label': 'All History', 'value': 'all'},
                                         {'label': 'Year to Date', 'value': 'ytd'},
                                         {'label': 'Last 90 days', 'value': 'l90d'},
                                         {'label': 'Last 6 weeks', 'value': 'l6w'},
                                         {'label': 'Last 30 days', 'value': 'l30d'}],
                                     value='l90d',
                                     multi=False
                                 ),
                             ]),
                             html.Div(className='col-lg-4', children=[
                                 dcc.Dropdown(
                                     id='music-intensity-selector',
                                     placeholder="Workout Intensity",
                                     options=[
                                         {'label': 'All Listening', 'value': 'all'},
                                         {'label': 'High Intensity Workout', 'value': 'high'},
                                         {'label': 'Mod Intensity Workout', 'value': 'mod'},
                                         {'label': 'Low Intensity Workout', 'value': 'low'},
                                         {'label': 'Regular Listening', 'value': 'rest'}],
                                     value='all',
                                     multi=False
                                 ),
                             ]),
                             html.Div(className='col-lg-4', children=[
                                 dcc.Dropdown(
                                     id='music-sport-selector',
                                     options=sport_options,
                                     value='all',
                                     multi=False
                                 ),
                             ]),
                         ]),
            ]),

            html.Div(className='row mb-2', children=[
                html.Div(className='col-lg-6', children=[
                    dbc.Card(children=[
                        dbc.CardHeader(html.H4('Music Profile', className='mb-0')),
                        dbc.CardBody(
                            style={'padding': '.5rem'},
                            children=[
                                dbc.Spinner(color='info', children=[
                                    dcc.Graph(
                                        id='radar-chart',
                                        config={'displayModeBar': False},
                                        style={'height': '100%'},
                                    )
                                ])
                            ]
                        )
                    ])

                ]),
                html.Div(className='col-lg-6', children=[
                    html.H1('Placeholder')
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-lg-8', children=[
                    dbc.Card([
                        dbc.CardBody([
                            html.Div(className='col-lg-12', style={'overflow': 'hidden'},
                                     children=dash_table.DataTable(
                                         id='play-history-table',
                                         columns=[
                                             {'name': 'Played', 'id': 'played_at'},
                                             {'name': 'Track Name', 'id': 'track_name'},
                                             {'name': 'Artist Name', 'id': 'artist_name'},
                                             {'name': 'Album Name', 'id': 'album_name'},
                                         ],
                                         style_as_list_view=True,
                                         fixed_rows={'headers': True, 'data': 0},
                                         style_table={'height': '100%'},
                                         style_header={'backgroundColor': 'rgba(0,0,0,0)',
                                                       'borderBottom': '1px solid rgb(220, 220, 220)',
                                                       'borderTop': '0px',
                                                       # 'textAlign': 'left',
                                                       'fontWeight': 'bold',
                                                       'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                                                       # 'fontSize': '1.2rem'
                                                       },
                                         style_cell={
                                             'backgroundColor': 'rgba(0,0,0,0)',
                                             'color': 'rgb(220, 220, 220)',
                                             'borderBottom': '1px solid rgb(73, 73, 73)',
                                             'textAlign': 'center',
                                             # 'whiteSpace': 'no-wrap',
                                             # 'overflow': 'hidden',
                                             'textOverflow': 'ellipsis',
                                             'maxWidth': 175,
                                             'minWidth': 50,
                                             # 'padding': '0px',
                                             'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                                             # 'fontSize': '1.2rem'
                                         },
                                         style_cell_conditional=[
                                             {
                                                 'if': {'column_id': 'activity_id'},
                                                 'display': 'none'
                                             }
                                         ],
                                         filter_action="native",
                                         page_action="none",
                                         # page_current=0,
                                         # page_size=10,
                                     )

                                     ),
                        ]), ]),
                ]),

            ])
        ])


# TODO: Add graph for top artists/tracks
# TODO: Add chart for PR tracks


def get_radar_chart(workout_intensity, sport, pop_time_period):
    df_tracks = get_played_tracks(workout_intensity=workout_intensity, sport=sport, pop_time_period=pop_time_period)

    radar_features = ['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'loudness',
                      'speechiness', 'tempo', 'valence']
    df_tracks_cur = df_tracks[df_tracks['Period'] == 'Current'][radar_features]
    df_tracks_prev = df_tracks[df_tracks['Period'] == 'Previous'][radar_features]
    data = []

    if len(df_tracks_prev) > 0:
        df_tracks_prev.loc[:] = MinMaxScaler().fit_transform(df_tracks_prev.loc[:])
        data.append(
            go.Scatterpolar(
                r=df_tracks_prev.mean() * 100,
                theta=[x.title() for x in df_tracks_prev.columns],
                text=['{}: <b>{:.2f}%'.format(y, x) for x, y in
                      zip(df_tracks_prev.mean() * 100, [x.title() for x in df_tracks_prev.columns])],

                hoverinfo='text',
                fill='toself',
                name='Prev. ' + pop_time_period.upper(),
                line=dict(color=white),
                fillcolor='rgba(220,220,220,.6)'

            )
        )
    if len(df_tracks_cur) > 0:
        # Scale all audio features from 0-1 so they can be compared on radar chart
        df_tracks_cur.loc[:] = MinMaxScaler().fit_transform(df_tracks_cur.loc[:])
        data.append(
            go.Scatterpolar(
                r=df_tracks_cur.mean() * 100,
                theta=[x.title() for x in df_tracks_cur.columns],
                text=['{}: <b>{:.2f}%'.format(y, x) for x, y in
                      zip(df_tracks_cur.mean() * 100, [x.title() for x in df_tracks_cur.columns])],
                hoverinfo='text',
                fill='toself',
                name='All Time' if pop_time_period == 'all' else pop_time_period.upper().replace('L', 'Last '),
                # color=teal,
                line=dict(color=teal),
                fillcolor='rgba(100, 217, 236,.6)',
            )
        )
    figure = {
        'data': data,
        'layout': go.Layout(
            # transition=dict(duration=transition),
            font=dict(
                size=10,
                color=white
            ),

            height=400,
            polar=dict(
                bgcolor='rgba(0,0,0,0)',
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    showticklabels=False,
                    ticks='',
                    showline=False,

                )),
            showlegend=True,
            legend=dict(bgcolor='rgba(127, 127, 127, 0)'),
            margin={'l': 50, 'b': 25, 't': 25, 'r': 50},

        )
    }

    return figure


# Create Radar Chart
# Zone and distribution callback for sport/date fitlers. Also update date label/card header with callback here
@app.callback(
    Output('radar-chart', 'figure'),
    [Input('music-intensity-selector', 'value'),
     Input('music-time-selector', 'value'),
     Input('music-sport-selector', 'value')],
    [State('music-intensity-selector', 'value'),
     State('music-time-selector', 'value'),
     State('music-sport-selector', 'value'),
     ]
)
def update_radar_chart(*args):
    ctx = dash.callback_context
    pop_time_period = ctx.states['music-time-selector.value']
    workout_intensity = ctx.states['music-intensity-selector.value']
    sport = ctx.states['music-sport-selector.value']

    figure = get_radar_chart(workout_intensity=workout_intensity, sport=sport, pop_time_period=pop_time_period)
    return figure


@app.callback(
    Output('play-history-table', 'data'),
    [Input('music-intensity-selector', 'value'),
     Input('music-time-selector', 'value'),
     Input('music-sport-selector', 'value')],
    [State('music-intensity-selector', 'value'),
     State('music-time-selector', 'value'),
     State('music-sport-selector', 'value'),
     ]
)
def populate_history_table(*args):
    ctx = dash.callback_context
    tracks_df = get_played_tracks(workout_intensity=ctx.states['music-intensity-selector.value'],
                                  sport=ctx.states['music-sport-selector.value'],
                                  pop_time_period=ctx.states['music-time-selector.value'])

    tracks_df['played_at'] = tracks_df.index.tz_localize('UTC').tz_convert(get_localzone()).strftime(
        '%Y-%m-%d %I:%M %p')

    return tracks_df[['played_at', 'track_name', 'artist_name', 'album_name']].sort_index(ascending=False).to_dict(
        'records')
