import pandas as pd
import dash
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from ..app import app
from ..api.spotifyAPI import get_played_tracks
import plotly.graph_objs as go
from ..utils import config
from sklearn.preprocessing import MinMaxScaler
import operator

transition = int(config.get('dashboard', 'transition'))
default_icon_color = 'rgb(220, 220, 220)'
white = 'rgb(220, 220, 220)'
teal = 'rgb(100, 217, 236)'
light_blue = 'rgb(56, 128, 139)'
dark_blue = 'rgb(39, 77, 86)'
orange = 'rgb(217,100,43)'
grey = 'rgb(50,50,50)'


def get_layout(**kwargs):
    return html.Div([
        html.Div(className='row', id='music-filter-shelf',
                 children=[html.Div(className='col-12 align-items-center text-center mt-2 mb-2', children=[
                     dbc.DropdownMenu(children=
                     [
                         dbc.DropdownMenuItem("All Listening",
                                              id="music-intensity-selector-none-none",
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem(divider=True),
                         dbc.DropdownMenuItem("All Workout Types", header=True),
                         dbc.DropdownMenuItem("All Intensities",
                                              id="music-intensity-selector-all-all",
                                              n_clicks_timestamp=1),
                         dbc.DropdownMenuItem("High Intensity",
                                              id='music-intensity-selector-all-high',
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("Mod Intensity",
                                              id="music-intensity-selector-all-mod",
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("Low Intensity",
                                              id='music-intensity-selector-all-low',
                                              n_clicks_timestamp=0),

                         dbc.DropdownMenuItem(divider=True),
                         dbc.DropdownMenuItem("Running", header=True),
                         dbc.DropdownMenuItem("All Intensities",
                                              id="music-intensity-selector-run-all",
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("High Intensity",
                                              id='music-intensity-selector-run-high',
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("Mod Intensity",
                                              id="music-intensity-selector-run-mod",
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("Low Intensity",
                                              id='music-intensity-selector-run-low',
                                              n_clicks_timestamp=0),

                         dbc.DropdownMenuItem(divider=True),
                         dbc.DropdownMenuItem("Cycling", header=True),
                         dbc.DropdownMenuItem("All Intensities",
                                              id="music-intensity-selector-ride-all",
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("High Intensity",
                                              id='music-intensity-selector-ride-high',
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("Mod Intensity",
                                              id="music-intensity-selector-ride-mod",
                                              n_clicks_timestamp=0),
                         dbc.DropdownMenuItem("Low Intensity",
                                              id='music-intensity-selector-ride-low',
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
                                )
                            ])
                        ]
                    )
                ])

            ])
        ])
    ])


def get_radar_chart(workout_intensity, sport, pop_time_period):
    df_tracks = get_played_tracks(workout_intensity=workout_intensity, sport=sport, pop_time_period=pop_time_period)

    df_tracks_cur = df_tracks[df_tracks['Period'] == 'Current'][
        ['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'loudness', 'speechiness', 'tempo',
         'valence']]
    df_tracks_prev = df_tracks[df_tracks['Period'] == 'Previous'][
        ['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'loudness', 'speechiness', 'tempo',
         'valence']]
    data = []

    if len(df_tracks_prev) > 0:
        df_tracks_prev.loc[:] = MinMaxScaler().fit_transform(df_tracks_prev.loc[:])
        data.append(
            go.Scatterpolar(
                r=df_tracks_prev[['acousticness', 'danceability', 'energy', 'instrumentalness', 'liveness', 'loudness',
                                  'speechiness', 'valence']].mean() * 100,
                theta=[x.title() for x in df_tracks_prev.columns],
                text='r',
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
                text='r',
                fill='toself',
                name='All Time' if pop_time_period == 'all' else pop_time_period.upper().replace('L', 'Last '),
                # color=teal,
                line=dict(color=teal),
                fillcolor='rgba(100, 217, 236,.6)'
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
            margin={'l': 20, 'b': 20, 't': 20, 'r': 20},

        )
    }

    return figure


# Create Radar Chart
# Zone and distribution callback for sport/date fitlers. Also update date label/card header with callback here
@app.callback(
    [Output('music-intensity-selector', 'label'),
     Output('music-time-selector', 'label'),
     Output('radar-chart', 'figure')],
    [Input('music-intensity-selector-none-none', 'n_clicks_timestamp'),
     Input('music-intensity-selector-all-all', 'n_clicks_timestamp'),
     Input('music-intensity-selector-all-high', 'n_clicks_timestamp'),
     Input('music-intensity-selector-all-mod', 'n_clicks_timestamp'),
     Input('music-intensity-selector-all-low', 'n_clicks_timestamp'),
     Input('music-intensity-selector-run-all', 'n_clicks_timestamp'),
     Input('music-intensity-selector-run-high', 'n_clicks_timestamp'),
     Input('music-intensity-selector-run-mod', 'n_clicks_timestamp'),
     Input('music-intensity-selector-run-low', 'n_clicks_timestamp'),
     Input('music-intensity-selector-ride-all', 'n_clicks_timestamp'),
     Input('music-intensity-selector-ride-high', 'n_clicks_timestamp'),
     Input('music-intensity-selector-ride-mod', 'n_clicks_timestamp'),
     Input('music-intensity-selector-ride-low', 'n_clicks_timestamp'),
     Input('music-time-selector-all', 'n_clicks_timestamp'),
     Input('music-time-selector-ytd', 'n_clicks_timestamp'),
     Input('music-time-selector-l90d', 'n_clicks_timestamp'),
     Input('music-time-selector-l6w', 'n_clicks_timestamp'),
     Input('music-time-selector-l30d', 'n_clicks_timestamp')],
    [State('music-intensity-selector-none-none', 'n_clicks_timestamp'),
     State('music-intensity-selector-all-all', 'n_clicks_timestamp'),
     State('music-intensity-selector-all-high', 'n_clicks_timestamp'),
     State('music-intensity-selector-all-mod', 'n_clicks_timestamp'),
     State('music-intensity-selector-all-low', 'n_clicks_timestamp'),
     State('music-intensity-selector-run-all', 'n_clicks_timestamp'),
     State('music-intensity-selector-run-high', 'n_clicks_timestamp'),
     State('music-intensity-selector-run-mod', 'n_clicks_timestamp'),
     State('music-intensity-selector-run-low', 'n_clicks_timestamp'),
     State('music-intensity-selector-ride-all', 'n_clicks_timestamp'),
     State('music-intensity-selector-ride-high', 'n_clicks_timestamp'),
     State('music-intensity-selector-ride-mod', 'n_clicks_timestamp'),
     State('music-intensity-selector-ride-low', 'n_clicks_timestamp'),
     State('music-time-selector-all', 'n_clicks_timestamp'),
     State('music-time-selector-ytd', 'n_clicks_timestamp'),
     State('music-time-selector-l90d', 'n_clicks_timestamp'),
     State('music-time-selector-l6w', 'n_clicks_timestamp'),
     State('music-time-selector-l30d', 'n_clicks_timestamp')]
)
def update_radar_chart(*args):
    ctx = dash.callback_context

    states = ctx.states
    # Create dict of just date buttons
    date_buttons = states.copy()
    [date_buttons.pop(x) for x in list(date_buttons.keys()) if 'music-time-selector' not in x]
    pop_time_period = max(date_buttons.items(), key=operator.itemgetter(1))[0].split('.')[0].replace(
        'music-intensity-selector-', '').split('-')[3]

    # Create dict of just intensity buttons
    intensity_buttons = states.copy()
    [intensity_buttons.pop(x) for x in list(intensity_buttons.keys()) if 'music-intensity-selector' not in x]
    workout_intensity_clicked = max(intensity_buttons.items(), key=operator.itemgetter(1))[0].split('.')[0].replace(
        'music-intensity-selector-', '').split('-')

    sport = workout_intensity_clicked[0] if workout_intensity_clicked[0] != 'none' else None
    workout_intensity = workout_intensity_clicked[1] if workout_intensity_clicked[1] != 'none' else None

    if not sport and not workout_intensity:
        workout_intensity_label = 'All Play History'
    else:
        workout_intensity_label = (sport.title() if sport else 'All') + ' ' + workout_intensity.title()

    workout_intensity_label = 'All Workouts' if workout_intensity_label == 'All All' else workout_intensity_label

    figure = get_radar_chart(workout_intensity=workout_intensity, sport=sport, pop_time_period=pop_time_period)
    return workout_intensity_label, pop_time_period.upper() if pop_time_period.title() != 'All' else 'All Time', figure
