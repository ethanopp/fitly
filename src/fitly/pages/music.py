import pandas as pd
import dash
import dash_daq as daq
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from ..app import app
from ..api.spotifyAPI import get_played_tracks
from ..api.database import engine
import plotly.graph_objs as go
from ..utils import config, nextcloud_credentials_supplied
from sklearn.preprocessing import MinMaxScaler

transition = int(config.get('dashboard', 'transition'))
default_icon_color = 'rgb(220, 220, 220)'
white = 'rgb(220, 220, 220)'
teal = 'rgb(100, 217, 236)'
light_blue = 'rgb(56, 128, 139)'
dark_blue = 'rgb(39, 77, 86)'
orange = 'rgb(217,100,43)'
grey = 'rgb(50,50,50)'


def create_radar_chart():
    df_tracks = get_played_tracks()

    df_tracks = df_tracks[['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'loudness',
                           'speechiness', 'tempo', 'valence']]

    # Scale all audio features from 0-1 so they can be compared on radar chart

    min_max_scaler = MinMaxScaler()
    df_tracks.loc[:] = min_max_scaler.fit_transform(df_tracks.loc[:])

    figure = {
        'data': [
            # TODO: create PoP dfs
            go.Scatterpolar(
                r=df_tracks[['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'loudness',
                             'speechiness', 'valence']].mean() * 100,
                theta=[x.title() for x in df_tracks.columns],
                text='r',
                fill='toself',
                name='P90D',
                line=dict(color=light_blue),
                fillcolor='rgba(56, 128, 139,.6)'

            ),
            go.Scatterpolar(
                r=df_tracks[['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'loudness',
                             'speechiness', 'valence']].mean() * 100,
                theta=[x.title() for x in df_tracks.columns],
                text='r',
                fill='toself',
                name='L90D',
                # color=teal,
                line=dict(color=teal),
                fillcolor='rgba(100, 217, 236,.6)'
            )
        ],
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
            margin={'l': 20, 'b': 20, 't': 20, 'r': 20},

        )
    }

    return figure


def get_layout(**kwargs):
    # test = dcc.Graph(
    #     id='radar-chart',
    #     config={'displayModeBar': False},
    #     style={'height': '100%'},
    #     figure=create_radar_chart()  # update with callback
    # )
    # import pprint
    # pprint.pprint(test)
    return html.Div([
        html.Div(className='row', id='music-filter-shelf',
                 children=[html.Div(className='col-12 align-items-center text-center mt-2 mb-2',
                                    style={'height': '1.375rem'}, children=[
                         dbc.DropdownMenu(children=
                         [
                             dbc.DropdownMenuItem("All Listening",
                                                  id="music-intensity-selector-all",
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem(divider=True),
                             dbc.DropdownMenuItem("All Workout Types", header=True),
                             dbc.DropdownMenuItem(divider=True),
                             dbc.DropdownMenuItem("All Intensities",
                                                  id="music-intensity-selector-workouts-all",
                                                  n_clicks_timestamp=1),
                             dbc.DropdownMenuItem("High Intensity",
                                                  id='music-intensity-selector-high-all',
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("Mod Intensity",
                                                  id="music-intensity-selector-mod-all",
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("Low Intensity",
                                                  id='music-intensity-selector-low-all',
                                                  n_clicks_timestamp=0),

                             dbc.DropdownMenuItem(divider=True),
                             dbc.DropdownMenuItem("Running", header=True),
                             dbc.DropdownMenuItem(divider=True),
                             dbc.DropdownMenuItem("All Intensities",
                                                  id="music-intensity-selector-workouts-run",
                                                  n_clicks_timestamp=1),
                             dbc.DropdownMenuItem("High Intensity",
                                                  id='music-intensity-selector-high-run',
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("Mod Intensity",
                                                  id="music-intensity-selector-mod-run",
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("Low Intensity",
                                                  id='music-intensity-selector-low-run',
                                                  n_clicks_timestamp=0),

                             dbc.DropdownMenuItem(divider=True),
                             dbc.DropdownMenuItem("Cycling", header=True),
                             dbc.DropdownMenuItem(divider=True),
                             dbc.DropdownMenuItem("All Intensities",
                                                  id="music-intensity-selector-workouts-ride",
                                                  n_clicks_timestamp=1),
                             dbc.DropdownMenuItem("High Intensity",
                                                  id='music-intensity-selector-high-ride',
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("Mod Intensity",
                                                  id="music-intensity-selector-mod-ride",
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("Low Intensity",
                                                  id='music-intensity-selector-low-ride',
                                                  n_clicks_timestamp=0),
                         ],
                             label="All Workouts",
                             bs_size='sm',
                             className="mb-0",
                             id='music-intensity-selector',
                             style={'display': 'inline-block', 'paddingRight': '2vw'},
                         ),

                         dbc.DropdownMenu(children=
                         [
                             dbc.DropdownMenuItem("All Dates",
                                                  id="music-time-selector-all",
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("YTD",
                                                  id='music-time-selector-ytd',
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("L90D",
                                                  id="music-time-selector-l90d",
                                                  n_clicks_timestamp=1),
                             dbc.DropdownMenuItem("L6W",
                                                  id='music-time-selector-l6w',
                                                  n_clicks_timestamp=0),
                             dbc.DropdownMenuItem("L30D",
                                                  id="music-time-selector-l30d",
                                                  n_clicks_timestamp=0),
                         ],
                             label="L90D",
                             bs_size='sm',
                             className="mb-0",
                             id='music-time-selector',
                             style={'display': 'inline-block', 'paddingLeft': '2vw'},
                         ),

                     ])
                           ]),

        html.Div(className='row', children=[
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
                                    figure=create_radar_chart()  # TODO: update with callback
                                )
                            ])
                        ]
                    )
                ])

            ])
        ])
    ])
