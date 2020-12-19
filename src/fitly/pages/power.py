import pandas as pd
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
import dash_daq as daq
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from ..api.sqlalchemy_declarative import stravaSummary, stravaSamples, stravaBestSamples, athlete, withings
from ..api.database import engine
from ..app import app
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from ..utils import config, stryd_credentials_supplied
from sqlalchemy import func, or_
import math
from ..api.strydAPI import get_training_distribution

# pre_style = {"backgroundColor": "#ddd", "fontSize": 20, "padding": "10px", "margin": "10px"}
hidden_style = {"display": "none"}
hidden_inputs = html.Div(id="hidden-inputs", style=hidden_style, children=[])

transition = int(config.get('dashboard', 'transition'))

white = config.get('oura', 'white')
teal = config.get('oura', 'teal')
light_blue = config.get('oura', 'light_blue')
dark_blue = config.get('oura', 'dark_blue')
orange = config.get('oura', 'orange')
ftp_color = 'rgb(100, 217, 236)'


def create_power_curve_kpis(interval, all, L90D, l6w, last, pr):
    return \
        html.Div(className='row align-items-center text-center', children=[
            ### Interval KPI ###
            html.Div(className='col-auto', children=[
                html.H4(id='power-curve-title', className='mb-0',
                        children='Power Curve {}'.format(timedelta(seconds=interval))),
            ]),
            dbc.Tooltip(
                '''A high power output for short periods of time (10 seconds) can contribute to improved performance across your entire Power Duration Curve. To improve musle power, focus on VO2 Max Intervals, Hill / Track Repeats and Supplemental Training.
                
                Fatigue resistance directly reflects your ability to run at close to maximal effort for your goal race distance. To improve fatigue fesistance, focus on Long Runs, High Volume Easy Runs, and Aerobic Threshold Tempo Runs.
                
                Building up your endurance with longer runs helps improve your body's ability to sustain efforts for long durations. To improve endurance, focus on Aerobic Threshold Tempo Runs, Race Specific Training and Long Runs.''',
                target="power-curve-title"),

            ### All KPI ###
            html.Div(id='all-kpi', className='col-lg-12 mb-0', children=[
                html.H5('All Time {}'.format(all),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': white, 'backgroundColor': dark_blue, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### L90D KPI ###
            html.Div(id='L90D-kpi', className='col-lg-12 mb-0', children=[
                html.H5('L90D {}'.format(L90D if pr == '' else pr),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': 'rgb(46,46,46)', 'backgroundColor': white if pr == '' else orange,
                               'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### L6W KPI ###
            html.Div(id='l6w-kpi', className='col-lg-12 mb-0', children=[
                html.H5('L6W {}'.format(l6w),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': white, 'backgroundColor': light_blue, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### Last KPI ###
            html.Div(id='last-kpi', className='col-lg-12 mb-0', children=[
                html.H5('L30D {}'.format(last),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': 'rgb(46,46,46)', 'backgroundColor': teal, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),

        ]),


def get_workout_title(activity_id=None):
    min_non_warmup_workout_time = app.session.query(athlete).filter(
        athlete.athlete_id == 1).first().min_non_warmup_workout_time
    activity_id = app.session.query(stravaSummary.activity_id).filter(stravaSummary.type.ilike('%ride%'),
                                                                      stravaSummary.elapsed_time > min_non_warmup_workout_time).order_by(
        stravaSummary.start_date_utc.desc()).first()[0] if not activity_id else activity_id
    df_samples = pd.read_sql(
        sql=app.session.query(stravaSamples).filter(stravaSamples.activity_id == activity_id).statement,
        con=engine,
        index_col=['timestamp_local'])

    app.session.remove()

    return [html.H6(datetime.strftime(df_samples['date'][0], "%A %b %d, %Y"), style={'height': '50%'}),
            html.H6(df_samples['act_name'][0], style={'height': '50%'})]


def power_profiles(interval, activity_type='ride', power_unit='mmp', group='M'):
    activity_type = '%' + activity_type + '%'

    # Filter on interval passed
    df_best_samples = pd.read_sql(
        sql=app.session.query(stravaBestSamples).filter(stravaBestSamples.type.ilike(activity_type),
                                                        stravaBestSamples.interval == interval).statement, con=engine,
        index_col=['timestamp_local'])

    app.session.remove()
    if len(df_best_samples) < 1:
        return {}

    # Create columns for x-axis
    df_best_samples['power_profile_dategroup'] = df_best_samples.index.to_period(group).to_timestamp()

    df = df_best_samples[['activity_id', power_unit, 'power_profile_dategroup', 'interval']]
    df = df.loc[df.groupby('power_profile_dategroup')[power_unit].idxmax()]

    figure = {
        'data': [
            go.Bar(
                x=df['power_profile_dategroup'],
                y=df[power_unit],
                customdata=[
                    '{}_{}_{}'.format(df.loc[x]['activity_id'], df.loc[x]['interval'].astype('int'),
                                      interval) for x in df.index],
                # add fields to text so data can go through clickData
                text=[
                    '{:.2f} W/kg'.format(x) if power_unit == 'watts_per_kg' else '{:.0f} W'.format(
                        x)
                    for x in
                    df[power_unit]],
                hoverinfo='x+text',
                marker=dict(
                    color=[orange if x == df[power_unit].max() else light_blue for x in
                           df[power_unit]],
                )
            )
        ],
        'layout': go.Layout(
            # transition=dict(duration=transition),
            font=dict(
                size=10,
                color=white
            ),
            height=400,
            xaxis=dict(
                showticklabels=True,
                tickformat="%b '%y"
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgb(73, 73, 73)',
            ),
            margin={'l': 25, 'b': 25, 't': 5, 'r': 20},

        )
    }

    return figure


def stryd_training_distributions():
    current_ftp_w = app.session.query(stravaSummary).filter(stravaSummary.type.ilike('run')).order_by(
        stravaSummary.start_date_utc.desc()).first().ftp

    # Data points for Power Curve Training Disribution
    TD_df_L90D = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.type.ilike('run'),
                                                      stravaBestSamples.timestamp_local >= (
                                                              datetime.now() - timedelta(days=90))
                                                      ).statement, con=engine)

    app.session.remove()

    ### STRYD TRAINING DISTRIBUTION USES CURRENT WEIGHT WHEN CALCULATING W/KG ###
    ### TRAINING DIST BARS WILL DO THE SAME TO BETTER ALIGN WITH PERCENTILES ###
    ### ACTUAL DATA SHOWN IN POWER CURVE WILL BE BASED ON FTP AT THE TIME OF RECORDING FOR BETTER ACCURACY ###

    # Make room on canvas for training dist bars
    td = get_training_distribution()
    data = [
        # Fitness
        go.Bar(
            xaxis='x', yaxis='y', customdata=['ignore'], x=[100],
            y=['Fitness'],
            # width=.5,
            marker=dict(color=light_blue),
            showlegend=False,
            text=[
                'Fitness: <b>{:.2f}</b> W/kg<br>Stryd Avg: <b>{:.2f}</b> W/kg<br>Percentile: <b>{:.0%}'.format(
                    td["attr"]["fitness"],  # Use value directly from stryd api call
                    td["percentile"]["median_fitness"],
                    td["percentile"]["fitness"])
            ],
            hoverinfo='text',
            orientation='h'),

        # Muscle Power
        go.Bar(
            xaxis='x', yaxis='y', customdata=['ignore'], x=[100],
            y=['Muscle Power'],
            # width=.5,
            marker=dict(color=light_blue),
            showlegend=False,
            text=[
                'Max 10 Sec Power: <b>{:.2f} </b>W/kg<br>Stryd Avg: <b>{:.2f}</b> W/kg<br>Percentile: <b>{:.0%}'.format(
                    td["attr"]["muscle_power"],  # Use value directly from stryd api call
                    td["percentile"]["median_muscle_power"],
                    td["percentile"]["muscle_power"]),
            ],
            hoverinfo='text',
            orientation='h'),

        # Fatigue Resistance
        go.Bar(
            xaxis='x', yaxis='y', customdata=['ignore'], x=[100],
            y=['Fatigue'],
            # width=.5,
            marker=dict(color=light_blue),
            showlegend=False,
            text=[
                'Longest 100% CP: <b>{}</b> <br>Stryd Avg: <b>{}</b><br>Percentile: <b>{:.0%}'.format(
                    timedelta(seconds=int(td["attr"]["fatigue_resistance"])),  # Use value directly from stryd api call
                    timedelta(seconds=int(td["percentile"]["median_fatigue_resistance"])),
                    td["percentile"]["fatigue_resistance"]),
            ],
            hoverinfo='text',
            orientation='h'),
        # Endurance
        go.Bar(
            xaxis='x', yaxis='y', customdata=['ignore'], x=[100],
            y=['Endurance'],
            # width=.5,
            marker=dict(color=light_blue),
            showlegend=False,
            text=[
                'Longest 50% CP: <b>{}</b> <br>Stryd Avg: <b>{}</b><br>Percentile: <b>{:.0%}'.format(
                    timedelta(seconds=int(td["attr"]["endurance"])),  # Use value directly from stryd api call
                    timedelta(seconds=int(td["percentile"]["median_endurance"])),
                    td["percentile"]["endurance"])
            ],
            hoverinfo='text',
            orientation='h'),
    ]

    shapes = [
        # Training distribution charts lines
        (dict(type='line', xref='x', yref='y', x0=50, x1=50, y0=0.05, y1=.35,
              line=dict(color=white, width=1, dash="dot", ), ),
         dict(type='line', xref='x', yref='y', x0=td['percentile']['fitness'] * 100,
              x1=td['percentile']['fitness'] * 100, y0=0, y1=.4,
              line=dict(color=white, width=2, ), )
         ),

        (dict(type='line', xref='x', yref='y', x0=50, x1=50, y0=0.05, y1=.35,
              line=dict(color=white, width=1, dash="dot", ), ),
         dict(type='line', xref='x', yref='y', x0=td['percentile']['muscle_power'] * 100,
              x1=td['percentile']['muscle_power'] * 100, y0=0, y1=.4,
              line=dict(color=white, width=2, ), )),

        (dict(type='line', xref='x', yref='y', x0=50, x1=50, y0=0.05, y1=.35,
              line=dict(color=white, width=1, dash="dot", ), ),
         dict(type='line', xref='x', yref='y', x0=td['percentile']['fatigue_resistance'] * 100,
              x1=td['percentile']['fatigue_resistance'] * 100, y0=0, y1=.4,
              line=dict(color=white, width=2, ), )),

        (dict(type='line', xref='x', yref='y', x0=50, x1=50, y0=0.05, y1=.35,
              line=dict(color=white, width=1, dash="dot", ), ),

         dict(type='line', xref='x', yref='y', x0=td['percentile']['endurance'] * 100,
              x1=td['percentile']['endurance'] * 100, y0=0, y1=.4,
              line=dict(color=white, width=2)
              ))
    ]
    annotations = [
        go.layout.Annotation(
            font={'size': 12, 'color': white}, x=50, y=.7, xref="x", yref="y",
            text='Fitness: {:.0f} W'.format(current_ftp_w),
            showarrow=False,
        ),

        go.layout.Annotation(
            font={'size': 12, 'color': white}, x=50, y=.7, xref="x", yref="y",
            text='Muscle Power: {:.0f} W'.format(TD_df_L90D.loc[10]['mmp']),
            showarrow=False,
        ),

        go.layout.Annotation(
            font={'size': 12, 'color': white}, x=50, y=.7, xref="x", yref="y",
            text='Fatigue Resistance: {}'.format(timedelta(seconds=int(td["attr"]["fatigue_resistance"]))),

            showarrow=False,
        ),
        go.layout.Annotation(
            font={'size': 12, 'color': white}, x=50, y=.7, xref="x", yref="y",
            text='Endurance: {}'.format(timedelta(seconds=int(td["attr"]["endurance"]))),
            showarrow=False,
        ),

    ]
    layouts = []
    for i in range(4):
        layouts.append(
            go.Layout(
                font=dict(size=10, color=white),
                shapes=[shapes[i][0], shapes[i][1]],
                annotations=[annotations[i]],
                height=100,
                xaxis=dict(showgrid=False, showline=False, zeroline=False, showticklabels=False, range=[0, 100]),
                margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
                showlegend=False,
                autosize=True,
                hovermode='x',
                yaxis=dict(showgrid=False, showline=False, zeroline=False, showticklabels=False, range=[0, 1]),
            )
        )

    graphs = []
    for i in range(4):
        graphs.append(
            html.Div(className='col-lg-12', style={'paddingRight': 0, 'paddingLeft': 0}, children=[
                dcc.Graph(
                    config={
                        'displayModeBar': False
                    },
                    style={'height': '100%'},
                    figure={
                        'data': [data[i]],
                        'layout': layouts[i]}
                )
            ])
        )

    return graphs


def power_curve(activity_type='ride', power_unit='mmp', last_id=None, height=400, time_comparison=None,
                intensity='all'):
    # TODO: Add power curve model once sweatpy has been finished
    # https://sweatpy.gssns.io/features/Power%20duration%20modelling/#comparison-of-power-duration-models
    activity_type = '%' + activity_type + '%'

    max_interval = app.session.query(
        func.max(stravaBestSamples.interval).label('interval')).filter(
        stravaBestSamples.type.ilike(activity_type)).first()[0]

    act_dict = pd.read_sql(
        sql=app.session.query(stravaBestSamples.activity_id, stravaBestSamples.act_name).distinct().statement,
        con=engine,
        index_col='activity_id').to_dict()

    # Data points for Power Curve Training Disribution
    # Join in weight at the time of workout for calculating FTP_W/kg at point in time (of workout)
    TD_df_L90D = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
            stravaSummary.weight
        ).join(stravaSummary, stravaBestSamples.activity_id == stravaSummary.activity_id, isouter=True).group_by(
            stravaBestSamples.interval).filter(stravaBestSamples.type.ilike(activity_type),
                                               stravaBestSamples.timestamp_local >= (
                                                       datetime.now() - timedelta(days=90))
                                               ).statement, con=engine, index_col='interval')

    # Don't show TD date when plotting a small chart ( <400 height)
    td_data_exists = len(TD_df_L90D) > 0 and height >= 400
    # If training distribution data exists
    if td_data_exists:
        TD_df_L90D['act_name'] = TD_df_L90D['activity_id'].map(act_dict['act_name'])
        TD_df_L90D['ftp_wkg'] = TD_df_L90D['ftp'] / (TD_df_L90D['weight'] * 0.453592)

        ### Calculations for L90D workouts based on todays weights for stryd comparisons ###
        # Stryd uses "Current FTP" and "Current Weight" across all workouts for last 90 days for their power curve
        # To align with their percentiles, we use these metrics (pulled from api)

        # For our actual power curve chart, we will use ftp as of when the workout was done for a more accurate chart
        fatigue_df = TD_df_L90D.loc[TD_df_L90D[
            TD_df_L90D[power_unit] > TD_df_L90D['ftp_wkg' if power_unit == 'watts_per_kg' else 'ftp']].index.max()]
        fatigue_ftp = fatigue_df.ftp_wkg if power_unit == 'watts_per_kg' else fatigue_df.ftp
        endurance_df = TD_df_L90D.loc[TD_df_L90D[TD_df_L90D[power_unit] > (
                TD_df_L90D['ftp_wkg' if power_unit == 'watts_per_kg' else 'ftp'] / 2)].index.max()]
        endurance_ftp = endurance_df.ftp_wkg / 2 if power_unit == 'watts_per_kg' else endurance_df.ftp / 2

        # Muscle power is just best 10 second power
        muscle_power = TD_df_L90D.loc[10][power_unit]

        TD_df_at = pd.read_sql(
            sql=app.session.query(
                func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
                stravaBestSamples.interval, stravaBestSamples.time_interval,
                stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
            ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.type.ilike(activity_type),
                                                          or_(stravaBestSamples.interval == 10,
                                                              stravaBestSamples.interval == int(fatigue_df.name),
                                                              stravaBestSamples.interval == int(endurance_df.name)),
                                                          ).statement, con=engine, index_col='interval')

        muscle_power_best = True if TD_df_at.loc[10][power_unit] == muscle_power else False
        endurance_best = True if TD_df_at.loc[endurance_df.name][power_unit] == endurance_df[power_unit] else False
        fatigue_best = True if TD_df_at.loc[fatigue_df.name][power_unit] == fatigue_df[power_unit] else False

    # 1 second intervals from 0-60 seconds
    interval_lengths = [i for i in range(1, 61)]
    # 5 second intervals from 1:15 - 20:00 mins
    interval_lengths += [i for i in range(65, 1201, 5)]
    # 30 second intervals for everything after 20 mins
    interval_lengths += [i for i in range(1230, (int(math.floor(max_interval / 10.0)) * 10) + 1, 30)]

    all_best_interval_df = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'),
            stravaBestSamples.activity_id, stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type)).statement,
        con=engine, index_col='interval')
    all_best_interval_df['act_name'] = all_best_interval_df['activity_id'].map(act_dict['act_name'])

    L90D_best_interval_df = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type),
                                                      stravaBestSamples.timestamp_local >= (
                                                              datetime.now() - timedelta(days=90))
                                                      ).statement, con=engine, index_col='interval')

    L90D_best_interval_df['act_name'] = L90D_best_interval_df['activity_id'].map(act_dict['act_name'])

    L6W_best_interval_df = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type),
                                                      stravaBestSamples.timestamp_local >= (
                                                              datetime.now() - timedelta(days=42))
                                                      ).statement, con=engine, index_col='interval')
    L6W_best_interval_df['act_name'] = L6W_best_interval_df['activity_id'].map(act_dict['act_name'])

    L30D_best_interval_df = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type),
                                                      stravaBestSamples.timestamp_local >= (
                                                              datetime.now() - timedelta(days=30))
                                                      ).statement, con=engine, index_col='interval')
    L30D_best_interval_df['act_name'] = L30D_best_interval_df['activity_id'].map(act_dict['act_name'])

    if last_id:
        recent_best_interval_df = pd.read_sql(
            sql=app.session.query(
                func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id,
                stravaBestSamples.interval, stravaBestSamples.time_interval,
                stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
            ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.activity_id == last_id,
                                                          stravaBestSamples.interval.in_(interval_lengths),
                                                          ).statement, con=engine, index_col='interval')
        recent_best_interval_df['act_name'] = recent_best_interval_df['activity_id'].map(act_dict['act_name'])

    if time_comparison:
        if intensity == 'all':
            time_comparison_best_interval_df = pd.read_sql(
                sql=app.session.query(
                    func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
                    stravaBestSamples.interval, stravaBestSamples.time_interval,
                    stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
                ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                              stravaBestSamples.type.ilike(activity_type),
                                                              stravaBestSamples.timestamp_local >= (
                                                                      datetime.now() - timedelta(days=time_comparison))
                                                              ).statement, con=engine, index_col='interval')
            time_comparison_best_interval_df['act_name'] = time_comparison_best_interval_df['activity_id'].map(
                act_dict['act_name'])
        else:
            # Join in intensity data from strava summary

            pd.read_sql(
                sql=app.session.query(stravaSummary.activity_id, stravaSummary.workout_intensity).statement,
                con=engine)

            time_comparison_best_interval_df = pd.read_sql(
                sql=app.session.query(
                    func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
                    stravaBestSamples.interval, stravaBestSamples.time_interval,
                    stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
                ).join(stravaSummary, stravaBestSamples.activity_id == stravaSummary.activity_id,
                       isouter=True).group_by(stravaBestSamples.interval).filter(
                    stravaSummary.workout_intensity == intensity,
                    stravaBestSamples.interval.in_(interval_lengths),
                    stravaBestSamples.type.ilike(activity_type),
                    stravaBestSamples.timestamp_local >= (
                            datetime.now() - timedelta(days=time_comparison))
                ).statement, con=engine, index_col='interval')
            time_comparison_best_interval_df['act_name'] = time_comparison_best_interval_df['activity_id'].map(
                act_dict['act_name'])

            all_best_interval_df = pd.read_sql(
                sql=app.session.query(
                    func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
                    stravaBestSamples.interval, stravaBestSamples.time_interval,
                    stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
                ).join(stravaSummary, stravaBestSamples.activity_id == stravaSummary.activity_id,
                       isouter=True).group_by(stravaBestSamples.interval).filter(
                    stravaSummary.workout_intensity == intensity,
                    stravaBestSamples.interval.in_(interval_lengths),
                    stravaBestSamples.type.ilike(activity_type)
                ).statement, con=engine, index_col='interval')
            all_best_interval_df['act_name'] = all_best_interval_df['activity_id'].map(
                act_dict['act_name'])

    app.session.remove()

    if len(all_best_interval_df) < 1:
        return {}

    ## Initial hoverdata if showing KPIs in header
    # hoverData = {'points': [
    #     {'x': 60,
    #      'y': ((all_best_interval_df.loc[60]['watts_per_kg']) if len(all_best_interval_df) > 0 else 0),
    #      'customdata': 'x_x_at'},
    #     {'y': ((L90D_best_interval_df.loc[60]['watts_per_kg']) if len(
    #         L90D_best_interval_df) > 0 else 0), 'customdata': 'x_x_L90D'},
    #     {'y': ((L6W_best_interval_df.loc[60]['watts_per_kg']) if len(
    #         L6W_best_interval_df) > 0 else 0), 'customdata': 'x_x_l6w'},
    #     {'y': ((L30D_best_interval_df.loc[60]['watts_per_kg']) if len(
    #         L30D_best_interval_df) > 0 else 0), 'customdata': 'x_x_w'}
    # ]} if power_unit == 'watts_per_kg' else {'points': [
    #     {'x': 60,
    #      'y': (round(all_best_interval_df.loc[60]['mmp']) if len(all_best_interval_df) > 0 else 0),
    #      'customdata': 'x_x_at'},
    #     {'y': (round(L90D_best_interval_df.loc[60]['mmp']) if len(
    #         L90D_best_interval_df) > 0 else 0), 'customdata': 'x_x_L90D'},
    #     {'y': (round(L6W_best_interval_df.loc[60]['mmp']) if len(
    #         L6W_best_interval_df) > 0 else 0), 'customdata': 'x_x_l6w'},
    #     {'y': (round(L30D_best_interval_df.loc[60]['mmp']) if len(
    #         L30D_best_interval_df) > 0 else 0), 'customdata': 'x_x_w'}
    # ]}

    # On Main chart, we only want to show 1 line with all different colors, so loop through each df and remove points where not max
    # Replace all_time with l90D
    if not time_comparison:
        for i in all_best_interval_df.index:
            if i in L90D_best_interval_df.index:
                if L90D_best_interval_df.at[i, power_unit] >= all_best_interval_df.at[i, power_unit]:
                    all_best_interval_df.at[i, power_unit] = None
                else:
                    L90D_best_interval_df.at[i, power_unit] = None
        # Replace L90D with L6W
        for i in L90D_best_interval_df.index:
            if i in L6W_best_interval_df.index:
                if L6W_best_interval_df.at[i, power_unit] >= L90D_best_interval_df.at[i, power_unit]:
                    L90D_best_interval_df.at[i, power_unit] = None
                else:
                    L6W_best_interval_df.at[i, power_unit] = None
        # Replace L6W with L30D
        for i in L6W_best_interval_df.index:
            if i in L30D_best_interval_df.index:
                if L30D_best_interval_df.at[i, power_unit] >= L6W_best_interval_df.at[i, power_unit]:
                    L6W_best_interval_df.at[i, power_unit] = None
                else:
                    L30D_best_interval_df.at[i, power_unit] = None

    tooltip = '''<b>{}</b><br>{}<br>{}<br>{:.2f} W/kg''' if power_unit == 'watts_per_kg' else '''<b>{}</b><br>{}<br>{}<br>{:.0f} W'''
    data = [
        go.Scatter(
            name='All',
            x=all_best_interval_df.index,
            y=all_best_interval_df[power_unit],
            mode='lines',
            text=[
                tooltip.format(
                    timedelta(seconds=i),
                    all_best_interval_df.loc[i]['act_name'],
                    all_best_interval_df.loc[i].date,
                    all_best_interval_df.loc[i][power_unit])
                for i in all_best_interval_df.index],

            customdata=[
                '{}_{}_at'.format(all_best_interval_df.loc[x]['activity_id'], int(x))
                for x in all_best_interval_df.index],  # add fields to text so data can go through clickData
            hoverinfo='text',
            line={'shape': 'spline', 'color': 'rgba(220,220,220,.5)'}
        )
    ]
    if not time_comparison:
        data.extend([
            go.Scatter(
                name='L90D',
                x=L90D_best_interval_df.index,
                y=L90D_best_interval_df[power_unit],
                mode='lines',
                # text=['{:.0f}'.format(L90D_best_interval_df.loc[i]['mmp']) for i in
                #       L90D_best_interval_df.index],
                text=[
                    tooltip.format(
                        timedelta(seconds=i),
                        L90D_best_interval_df.loc[i]['act_name'],
                        L90D_best_interval_df.loc[i].date,
                        L90D_best_interval_df.loc[i][power_unit])
                    for i in L90D_best_interval_df.index],
                customdata=[
                    '{}_{}_L90D'.format(L90D_best_interval_df.loc[x]['activity_id'], int(x))
                    for x in L90D_best_interval_df.index],
                hoverinfo='text',
                line={'shape': 'spline', 'color': white},
            ),
            go.Scatter(
                name='L6W',
                x=L6W_best_interval_df.index,
                y=L6W_best_interval_df[power_unit],
                mode='lines',
                # text=['{:.0f}'.format(L90D_best_interval_df.loc[i]['mmp']) for i in
                #       L90D_best_interval_df.index],
                text=[
                    tooltip.format(
                        timedelta(seconds=i),
                        L6W_best_interval_df.loc[i]['act_name'],
                        L6W_best_interval_df.loc[i].date,
                        L6W_best_interval_df.loc[i][power_unit])
                    for i in L6W_best_interval_df.index],
                customdata=[
                    '{}_{}_l6w'.format(L6W_best_interval_df.loc[x]['activity_id'], int(x))
                    for x in L6W_best_interval_df.index],
                hoverinfo='text',
                line={'shape': 'spline', 'color': light_blue},
            ),
            go.Scatter(
                name='L30D',
                x=L30D_best_interval_df.index,
                y=L30D_best_interval_df[power_unit],
                mode='lines',
                # text=['{:.0f}'.format(L90D_best_interval_df.loc[i]['mmp']) for i in
                #       L90D_best_interval_df.index],
                text=[
                    tooltip.format(
                        timedelta(seconds=i),
                        L30D_best_interval_df.loc[i]['act_name'],
                        L30D_best_interval_df.loc[i].date,
                        L30D_best_interval_df.loc[i][power_unit])
                    for i in L30D_best_interval_df.index],
                customdata=[
                    '{}_{}_w'.format(L30D_best_interval_df.loc[x]['activity_id'], int(x))
                    for x in L30D_best_interval_df.index],
                hoverinfo='text',
                line={'shape': 'spline', 'color': teal},
            )
        ])
    else:
        data.append(
            go.Scatter(
                name={99999: 'All', int(datetime.now().strftime('%j')): 'YTD', 90: 'L90D', 42: 'L6W', 30: 'L30D'}[
                    time_comparison],
                x=time_comparison_best_interval_df.index,
                y=time_comparison_best_interval_df[power_unit],
                mode='lines',
                # text=['{:.0f}'.format(L90D_best_interval_df.loc[i]['mmp']) for i in
                #       L90D_best_interval_df.index],
                text=[
                    tooltip.format(
                        timedelta(seconds=i),
                        time_comparison_best_interval_df.loc[i]['act_name'],
                        time_comparison_best_interval_df.loc[i].date,
                        time_comparison_best_interval_df.loc[i][power_unit])
                    for i in time_comparison_best_interval_df.index],
                customdata=[
                    '{}_{}_w'.format(time_comparison_best_interval_df.loc[x]['activity_id'], int(x))
                    for x in time_comparison_best_interval_df.index],
                hoverinfo='text',
                line={'shape': 'spline', 'color': teal},
            )
        )
    if last_id:
        data.append(
            go.Scatter(
                name='Workout',
                x=recent_best_interval_df.index,
                y=recent_best_interval_df[power_unit],
                mode='lines',
                text=[
                    tooltip.format(
                        timedelta(seconds=i),
                        recent_best_interval_df.loc[i]['act_name'],
                        recent_best_interval_df.loc[i].date,
                        recent_best_interval_df.loc[i][power_unit])
                    for i in recent_best_interval_df.index],
                customdata=[
                    '{}_{}_w'.format(recent_best_interval_df.loc[x]['activity_id'], int(x))
                    for x in recent_best_interval_df.index],
                hoverinfo='text',
                line={'shape': 'spline', 'color': orange},
            )
        )
    annotations = [
        # Muscle Power
        go.layout.Annotation(
            font={'size': 10, 'color': orange if muscle_power_best else white},
            x=1,
            y=muscle_power,
            xref="x",
            yref="y",
            text='''Max 10 Sec Power (L90D): <b>{:.2f}</b> W/kg'''.format(
                muscle_power) if power_unit == 'watts_per_kg' else '''Max 10 Sec Power (L90D): <b>{:.0f}</b> W'''.format(
                muscle_power),
            showarrow=False,
            arrowhead=1,
            arrowcolor='Grey',
            bgcolor='rgba(81,89,95,.5)',
            ay=-10,
        ),
        # Fatigue Resistance
        go.layout.Annotation(
            font={'size': 10, 'color': orange if fatigue_best else white},
            x=.1,
            y=fatigue_ftp,
            xref="x",
            yref="y",
            text='''100% CP (L90D): <b>{:.2f}</b> W/kg'''.format(
                fatigue_ftp) if power_unit == 'watts_per_kg' else '''100% CP (L90D): <b>{:.0f}</b> W'''.format(
                fatigue_ftp),
            showarrow=True,
            arrowhead=1,
            arrowcolor='rgba(0,0,0,0)',
            bgcolor='rgba(81,89,95,.5)',
            ax=75,
            ay=-10,
        ),

        go.layout.Annotation(
            font={'size': 10, 'color': orange if endurance_best else white},
            x=.1,
            y=endurance_ftp,
            xref="x",
            yref="y",
            text='''50% CP (L90D): <b>{:.2f}</b> W/kg'''.format(
                endurance_ftp) if power_unit == 'watts_per_kg' else '''50% CP (L90D): <b>{:.0f}</b> W'''.format(
                endurance_ftp),
            showarrow=True,
            arrowhead=1,
            arrowcolor='rgba(0,0,0,0)',
            bgcolor='rgba(81,89,95,.5)',
            ax=75,
            ay=-10,
        ),
    ] if td_data_exists else []

    shapes = [
        # Power Curve Lines
        # Muscle Power
        dict(
            type='line', y0=0, y1=muscle_power, xref='x', yref='y', x0=10, x1=10,
            line=dict(
                color="Grey",
                width=1,
                dash="dot",
            ),
        ),
        # Fatigue Resistance
        dict(
            type='line', y0=fatigue_ftp, y1=fatigue_ftp, xref='x', yref='y', x0=.9,
            line=dict(
                color="Grey",
                width=1,
                dash="dot",
            ),
        ),
        # Endurance
        dict(
            type='line', y0=endurance_ftp, y1=endurance_ftp, xref='x', yref='y', x0=.9,
            line=dict(
                color="Grey",
                width=1,
                dash="dot",
            ),
        )
    ] if td_data_exists else []

    layout = go.Layout(
        # transition=dict(duration=transition),
        title='Power Curve' if height < 400 else '',
        font=dict(
            size=10,
            color=white
        ),
        height=height,
        shapes=shapes,
        annotations=annotations,
        xaxis=dict(
            showgrid=False,
            # tickformat="%H:%M:%S",
            # range=[best_interval_df.index.min(),best_interval_df.index.max()],
            # range=[np.log10(best_interval_df.index.min()), np.log10(best_interval_df.index.max())],
            type='log',
            tickangle=45 if height < 400 else 0,
            tickvals=[1, 2, 5, 10, 30, 60, 120, 5 * 60, 10 * 60, 20 * 60, 60 * 60, 60 * 120],
            ticktext=['1s', '2s', '5s', '10s', '30s', '1m', '2m', '5m', '10m', '20m', '1h', '2h'],
        ),

        yaxis=dict(
            showgrid=True,
            zeroline=False,
            # range=[best_interval_df['mmp'].min(), best_interval_df['mmp'].max()],
            gridcolor='rgb(73, 73, 73)'
        ),
        margin={'l': 40, 'b': 25, 't': 20 if height < 400 else 5, 'r': 0},
        legend=dict(x=.5, y=1, bgcolor='rgba(127, 127, 127, 0)', xanchor='center',
                    orientation='h', ) if height >= 400 else
        dict(x=.85, bgcolor='rgba(127, 127, 127, 0)', xanchor='center'),
        autosize=True,
        hovermode='x',
        # paper_bgcolor='rgb(66,66,66)',
        # plot_bgcolor='rgba(0,0,0,0)',

    )

    figure = {
        'data': data,
        'layout': layout
    }

    # if not last_id:
    #     # Pull CY for scatter bubbles
    #     cy_best_df_bubbles = df_best_samples[
    #         df_best_samples['timestamp_local'] >= datetime.strptime(str(datetime.now().year) + '-01-01', "%Y-%m-%d")]
    #     data.append(go.Scatter(
    #         name='CY bubbles',
    #         x=cy_best_df_bubbles.index,
    #         y=cy_best_df_bubbles[power_unit],
    #         mode='markers',
    #         customdata=['____' for x in cy_best_df_bubbles.index],
    #         hoverinfo='none',
    #         line={'color': 'rgba(56, 128, 139,.05)'},
    #         showlegend=False
    #     ))

    return figure  # , hoverData


def create_ftp_chart(activity_type='ride', power_unit='watts'):
    activity_type = '%' + activity_type + '%'

    df_ftp = pd.read_sql(
        sql=app.session.query(stravaSummary).filter(stravaSummary.type.ilike(activity_type),
                                                    stravaSummary.start_date_utc >= (
                                                            datetime.utcnow() - relativedelta(months=12))
                                                    ).statement, con=engine,
        index_col='start_day_local')[['activity_id', 'ftp', 'weight']]

    app.session.remove()

    if len(df_ftp) < 1:
        return None, {}

    df_ftp.set_index(pd.DatetimeIndex(df_ftp.index), inplace=True)

    # Get latest FTP of each month (instead of max in case ftp decreases)
    df_ftp = df_ftp.groupby(df_ftp.index.month).apply(pd.Series.tail, 1).reset_index(level=0,
                                                                                     drop=True).sort_index().resample(
        'M').max().ffill().interpolate()

    # Filter summary table on activities that have a different FTP from the previous activity
    # df_ftp['previous_ftp'] = df_ftp['ftp'].shift(1)
    # df_ftp = df_ftp[df_ftp['previous_ftp'] != df_ftp['ftp']]

    df_ftp['watts_per_kg'] = df_ftp['ftp'] / (df_ftp['weight'] / 2.20462)
    metric = 'ftp' if power_unit == 'ftp' else 'watts_per_kg'
    tooltip = '<b>{:.0f} W {}' if metric == 'ftp' else '<b>{:.2f} W/kg {}'
    title = 'Current FTP {:.0f} W (L12M)' if metric == 'ftp' else 'Current FTP {:.2f} W/kg (L12M)'

    df_ftp['ftp_%'] = ['{}{:.0f}%'.format('+' if x > 0 else '', x) if x != 0 else '' for x in
                       (((df_ftp[metric] - df_ftp[metric].shift(1)) / df_ftp[metric].shift(1)) * 100).fillna(0)]

    df_ftp_tooltip = [tooltip.format(x, y) for x, y in
                      zip(df_ftp[metric], df_ftp['ftp_%'])]

    df_ftp = df_ftp.reset_index()

    ftp_current = title.format(df_ftp.loc[df_ftp.index.max()][metric])

    figure = {
        'data': [
            go.Bar(
                name='FTP',
                x=df_ftp.index,
                y=df_ftp[metric],
                text=df_ftp['ftp_%'],
                textfont=dict(
                    size=10,
                ),
                textposition='none',
                marker=dict(
                    color=[orange if x == df_ftp[metric].max() else light_blue for x in
                           df_ftp[metric]],
                ),
                hovertext=df_ftp_tooltip,
                hoverinfo='text+x',
                opacity=0.7,
            ),

        ],
        'layout': go.Layout(
            font=dict(
                size=10,
                color=white
            ),
            height=400,
            transition=dict(duration=transition),
            xaxis=dict(
                showticklabels=True,
                tickvals=df_ftp.index,
                ticktext=df_ftp['start_day_local'].apply(lambda x: datetime.strftime(x, "%b")),
                showgrid=False
            ),
            yaxis=dict(
                showticklabels=True,
                showgrid=True,
                gridcolor='rgb(73, 73, 73)',
                # range=[df_ftp['ftp'].min() * .90, df_ftp['ftp'].max() * 1.25],
            ),
            showlegend=False,
            margin={'l': 25, 'b': 25, 't': 5, 'r': 20},
        )
    }

    return ftp_current, figure


def zone_chart(activity_id=None, sport='run', metrics=['power_zone', 'hr_zone'], chart_id='zone-chart', days=90,
               height=400, intensity='all'):
    # If activity_id passed, filter only that workout, otherwise show distribution across last 6 weeks

    if activity_id:
        df_samples = pd.read_sql(
            sql=app.session.query(stravaSamples).filter(stravaSamples.activity_id == activity_id).statement,
            con=engine,
            index_col=['timestamp_local'])

    else:
        if intensity == 'all':
            df_samples = pd.read_sql(
                sql=app.session.query(stravaSamples).filter(stravaSamples.type.like(sport),
                                                            stravaSamples.timestamp_local >= (
                                                                    datetime.now() - timedelta(
                                                                days=days))).statement,
                con=engine,
                index_col=['timestamp_local'])
        else:
            # Join intensity from strava summary to samples and filter on intensity if passed as an argument
            df_samples = pd.read_sql(
                sql=app.session.query(stravaSamples).filter(stravaSamples.type.like(sport),
                                                            stravaSamples.timestamp_local >= (
                                                                    datetime.now() - timedelta(
                                                                days=days))).statement,
                con=engine,
                index_col=['timestamp_local'])
            df_samples = df_samples.merge(pd.read_sql(
                sql=app.session.query(stravaSummary.activity_id, stravaSummary.workout_intensity).statement,
                con=engine), how='left', left_on='activity_id', right_on='activity_id')

            df_samples = df_samples[df_samples['workout_intensity'] == intensity]

    app.session.remove()
    data = []
    for metric in metrics:
        zone_df = df_samples.groupby(metric).size().reset_index(name='counts')
        zone_df['seconds'] = zone_df['counts']
        zone_df['Percent of Total'] = (zone_df['seconds'] / zone_df['seconds'].sum())

        # zone_map = {1: 'Active Recovery', 2: 'Endurance', 3: 'Tempo', 4: 'Threshold', 5: 'VO2 Max',
        #             6: 'Anaerobic', 7: 'Neuromuscular'}

        zone_map = {1: 'Zone 1', 2: 'Zone 2', 3: 'Zone 3', 4: 'Zone 4', 5: 'Zone 5',
                    6: 'Zone 6', 7: 'Zone 7'}

        zone_df[metric] = zone_df[metric].map(zone_map)
        zone_df = zone_df.sort_values(by=metric, ascending=False)

        label = [
            'Time: ' + '<b>{}</b>'.format(timedelta(seconds=seconds)) + '<br>' + '% of Total: ' + '<b>{0:.0f}'.format(
                percentage * 100) + '%'
            for seconds, percentage in zip(list(zone_df['seconds']), list(zone_df['Percent of Total']))]

        per_low = zone_df[zone_df[metric].isin(
            ['Zone 1', 'Zone 2', 'Zone 3'] if sport == 'Ride' and metric == 'power_zone' else ['Zone 1', 'Zone 2'])][
            'Percent of Total'].sum()

        if metric == 'hr_zone':
            colors = [
                'rgb(174, 18, 58)',
                'rgb(204, 35, 60)',
                'rgb(227, 62, 67)',
                'rgb(242, 98, 80)',
                'rgb(248, 130, 107)',
                'rgb(252, 160, 142)',
                'rgb(255, 190, 178)'
            ]
        elif metric == 'power_zone':
            colors = [
                'rgb(44, 89, 113)',
                'rgb(49, 112, 151)',
                'rgb(53, 137, 169)',
                'rgb(69, 162, 185)',
                'rgb(110, 184, 197)',
                'rgb(147, 205, 207)',
                'rgb(188, 228, 216)'
            ]

        data.append(
            go.Bar(
                name='HR ({:.0f}% Low)'.format(per_low * 100) if metric == 'hr_zone' else 'Power ({:.0f}% Low)'.format(
                    per_low * 100),
                y=zone_df[metric],
                x=zone_df['Percent of Total'],
                orientation='h',
                text=['{0:.0f}'.format(percentage * 100) + '%' for percentage in list(zone_df['Percent of Total'])],
                hovertext=label,
                hoverinfo='text',
                textposition='auto',
                width=.4,
                marker={'color': colors},
            )
        )

    return dcc.Graph(
        id=chart_id, style={'height': '100%'},
        config={
            'displayModeBar': False
        },
        figure={
            'data': data,
            'layout': go.Layout(
                title='Time in Zones' if height < 400 else '',
                font=dict(
                    size=10,
                    color=white
                ),
                height=height,
                # annotations=[
                #     dict(
                #         text="Power Zones",
                #         font=dict(size=16),
                #         xref="paper",
                #         yref="paper",
                #         yanchor="bottom",
                #         xanchor="center",
                #         align="center",
                #         x=0.5,
                #         y=1,
                #         showarrow=False
                #     )],
                autosize=True,
                xaxis=dict(
                    hoverformat=".1%",
                    tickformat="%",
                    showgrid=False,
                    # zerolinecolor='rgb(238, 238, 238)',
                ),
                yaxis=dict(
                    autorange='reversed',
                    showgrid=False,
                    categoryarray=['Zone 5', 'Zone 4', 'Zone 3', 'Zone 2', 'Zone 1'] if sport == 'run' else [
                        'Zone 7', 'Zone 6', 'Zone 5', 'Zone 4', 'Zone 3', 'Zone 2', 'Zone 1'],
                ),
                showlegend=True,
                hovermode='closest',
                legend=dict(x=.5, y=1.1, bgcolor='rgba(127, 127, 127, 0)', xanchor='center',
                            orientation='h', ) if height >= 400 else
                dict(x=.85, bgcolor='rgba(127, 127, 127, 0)', xanchor='center'),
                margin={'l': 45, 'b': 0, 't': 20, 'r': 0},
                # margin={'l': 40, 'b': 0, 't': 20 if height < 400 else 5, 'r': 0},

            )
        }
    )


@app.callback(
    [Output('power-curve-container', 'className'),
     Output('power-curve-chart', 'figure'),
     Output('stryd-distributions', 'children')],
    [Input('activity-type-toggle', 'value'),
     Input('power-unit-toggle', 'value')]
)
def update_power_curve(activity_type, power_unit):
    power_unit = 'watts_per_kg' if power_unit else 'mmp'
    activity_type = 'ride' if activity_type else 'run'

    if stryd_credentials_supplied and activity_type == 'run':
        classname = 'col-lg-9'
        stryd = stryd_training_distributions()
    else:
        classname = 'col-lg-12'
        stryd = []

    figure = power_curve(activity_type, power_unit)
    return classname, figure, stryd


# # Callbacks to figure out which is the latest chart that was clicked
# @app.callback(
#     Output('power-curve-chart-timestamp', 'children'),
#     [Input('power-curve-chart', 'clickData')])
# def power_curve_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @app.callback(
#     Output('power-profile-5-chart-timestamp', 'children'),
#     [Input('power-profile-5-chart', 'clickData')])
# def power_profile_5_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @app.callback(
#     Output('power-profile-60-chart-timestamp', 'children'),
#     [Input('power-profile-60-chart', 'clickData')])
# def power_profile_60_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @app.callback(
#     Output('power-profile-300-chart-timestamp', 'children'),
#     [Input('power-profile-300-chart', 'clickData')])
# def power_profile_300_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @app.callback(
#     Output('power-profile-1200-chart-timestamp', 'children'),
#     [Input('power-profile-1200-chart', 'clickData')])
# def power_profile_1200_chart_timestamp(dummy):
#     return datetime.utcnow()


# # Store last clicked data into div for consumption by action callbacks
# @app.callback(
#     Output('last-clicked', 'children'),
#     [Input('power-curve-chart-timestamp', 'children'),
#      Input('power-profile-5-chart-timestamp', 'children'),
#      Input('power-profile-60-chart-timestamp', 'children'),
#      Input('power-profile-300-chart-timestamp', 'children'),
#      Input('power-profile-1200-chart-timestamp', 'children')],
#     [State('power-curve-chart', 'clickData'),
#      State('power-profile-5-chart', 'clickData'),
#      State('power-profile-60-chart', 'clickData'),
#      State('power-profile-300-chart', 'clickData'),
#      State('power-profile-1200-chart', 'clickData')]
#
# )
# def update_last_clicked(power_curve_chart_timestamp, power_profile_5_chart_timestamp, power_profile_60_chart_timestamp,
#                         power_profile_300_chart_timestamp, power_profile_1200_chart_timestamp,
#                         power_curve_chart_clickData, power_profile_5_chart_clickData, power_profile_60_chart_clickData,
#                         power_profile_300_chart_clickData, power_profile_1200_chart_clickData):
#     timestamps = {'power': power_curve_chart_timestamp,
#                   '5': power_profile_5_chart_timestamp,
#                   '60': power_profile_60_chart_timestamp,
#                   '300': power_profile_300_chart_timestamp,
#                   '1200': power_profile_1200_chart_timestamp,
#                   }
#
#     if power_curve_chart_timestamp or power_profile_5_chart_timestamp or power_profile_60_chart_timestamp or power_profile_300_chart_timestamp or power_profile_1200_chart_timestamp:
#
#         latest = max(timestamps.items(), key=operator.itemgetter(1))[0]
#
#         if latest == 'power':
#             clickData = power_curve_chart_clickData
#         elif latest == '5':
#             clickData = power_profile_5_chart_clickData
#         elif latest == '60':
#             clickData = power_profile_60_chart_clickData
#         elif latest == '300':
#             clickData = power_profile_300_chart_clickData
#         elif latest == '1200':
#             clickData = power_profile_1200_chart_clickData
#
#         return json.dumps(clickData)


# ## Action for workout title ##
# @app.callback(
#     Output('workout-title', 'children'),
#     [Input('last-clicked', 'children')],
# )
# def update_workout_title(clickdata):
#     last_clickdata = json.loads(clickdata)
#     try:
#         activity_id, end_seconds, interval = last_clickdata['points'][0]['customdata'].split('_')
#         return get_workout_title(activity_id=activity_id)
#     except:
#         return get_workout_title()


# ## Action for workout Trends ##
# @app.callback(
#     Output('workout-trends', 'children'),
#     [Input('last-clicked', 'children')],
# )
# def update_workout_trends(last_clickdata):
#     last_clickdata = json.loads(last_clickdata)
#     try:
#         activity_id, end_seconds, interval = last_clickdata['points'][0]['customdata'].split('_')
#         return workout_details(activity_id=activity_id, start_seconds=(int(end_seconds) - int(interval)),
#                                end_seconds=int(end_seconds))
#     except:
#         return workout_details()


# ## Action for workout Trends ##
# @app.callback(
#     Output('power-zone', 'children'),
#     [Input('last-clicked', 'children')],
# )
# def update_power_zones(last_clickdata):
#     last_clickdata = json.loads(last_clickdata)
#     try:
#         activity_id, end_seconds, interval = last_clickdata['points'][0]['customdata'].split('_')
#         return zone_chart(activity_id=activity_id)
#     except:
#         return zone_chart()


# Color icons
@app.callback(
    [Output('bicycle-icon', 'style'),
     Output('running-icon', 'style')],
    [Input('activity-type-toggle', 'value')]
)
def update_icon(value):
    if value:
        return {'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}, {
            'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle'}
    else:
        return {'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle'}, {
            'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}


@app.callback(
    [Output('bolt-icon', 'style'),
     Output('weight-icon', 'style')],
    [Input('power-unit-toggle', 'value')]
)
def update_icon(value):
    if value:
        return {'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle'}, {
            'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}
    else:
        return {'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}, {
            'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle'}


# FTP Chart
@app.callback(
    [Output('ftp-current', 'children'),
     Output('ftp-chart', 'figure')],
    [Input('activity-type-toggle', 'value'),
     Input('power-unit-toggle', 'value')]
)
def ftp_chart(activity_type, power_unit):
    power_unit = 'watts_per_kg' if power_unit else 'ftp'
    activity_type = 'ride' if activity_type else 'run'
    current, figure = create_ftp_chart(activity_type=activity_type, power_unit=power_unit)
    return current, figure


# Group power profiles
@app.callback([Output('power-profile-5-chart', 'figure'),
               Output('power-profile-60-chart', 'figure'),
               Output('power-profile-300-chart', 'figure'),
               Output('power-profile-1200-chart', 'figure'),
               Output('day-button', 'style'),
               Output('week-button', 'style'),
               Output('month-button', 'style'),
               Output('year-button', 'style'), ],
              [Input('activity-type-toggle', 'value'),
               Input('power-unit-toggle', 'value'),
               Input('day-button', 'n_clicks'),
               Input('week-button', 'n_clicks'),
               Input('month-button', 'n_clicks'),
               Input('year-button', 'n_clicks')]
              )
def update_power_profiles(activity_type, power_unit, day_n_clicks, week_n_clicks, month_n_clicks, year_n_clicks):
    latest_dict = {'day-button': 'D', 'week-button': 'W', 'month-button': 'M', 'year-button': 'Y'}
    style = {'Y': {'marginRight': '1%'}, 'M': {'marginRight': '1%'}, 'W': {'marginRight': '1%'},
             'D': {'marginRight': '1%'}}

    ctx = dash.callback_context
    if not ctx.triggered:
        latest = 'M'
    else:
        if ctx.triggered[0]['prop_id'].split('.')[0] != 'power-unit-toggle' and ctx.triggered[0]['prop_id'].split('.')[
            0] != 'activity-type-toggle':
            latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]
        else:
            latest = 'M'

    style[latest] = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}

    power_unit = 'watts_per_kg' if power_unit else 'mmp'
    activity_type = 'ride' if activity_type else 'run'

    return power_profiles(interval=5, group=latest, power_unit=power_unit, activity_type=activity_type), \
           power_profiles(interval=60, group=latest, power_unit=power_unit, activity_type=activity_type), \
           power_profiles(interval=300, group=latest, power_unit=power_unit, activity_type=activity_type), \
           power_profiles(interval=1200, group=latest, power_unit=power_unit, activity_type=activity_type), \
           style['D'], style['W'], style['M'], style['Y']


# # Main Dashboard Generation Callback
# @app.callback(
#     Output('power-layout', 'children'),
#     [Input('activity-type-toggle', 'value'),
#      Input('power-unit-toggle', 'value')],
# )
# def performance_dashboard(dummy, activity_type, power_unit):
#     return generate_power_dashboard()


# @app.callback(
#     Output('power-curve-kpis', 'children'),
#     [Input('power-curve-chart', 'hoverData')],
#     [State('power-unit-toggle', 'value')])
# def update_fitness_kpis(hoverData, power_unit):
#     interval, at, L90D, l6w, last, pr = 0, '', '', '', '', ''
#     if hoverData is not None and hoverData['points'][0]['customdata'] != 'ignore':
#         interval = hoverData['points'][0]['x']
#         for x in hoverData['points']:
#             if x['customdata'].split('_')[2] == 'at':
#                 at = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
#             elif x['customdata'].split('_')[2] == 'L90D':
#                 L90D = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
#             elif x['customdata'].split('_')[2] == 'l6w':
#                 l6w = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
#             elif x['customdata'].split('_')[2] == 'pr':
#                 pr = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
#             elif x['customdata'].split('_')[2] == 'w':
#                 last = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
#
#     return create_power_curve_kpis(interval, at, L90D, l6w, last, pr)


def get_layout(**kwargs):
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False
    app.session.remove()

    if not use_power:
        return html.H1('Power data currently disabled', className='text-center')
    else:
        return html.Div([

            html.Div(className='row align-items-start text-center', children=[
                html.Div(id='power-dashboard-header-container', className='col-12 mt-2 mb-2', children=[

                    html.I(id='running-icon', className='fa fa-running',
                           style={'fontSize': '2rem', 'display': 'inline-block'}),
                    daq.ToggleSwitch(id='activity-type-toggle', className='mr-2 ml-2',
                                     style={'display': 'inline-block'}),

                    html.I(id='bicycle-icon', className='fa fa-bicycle',
                           style={'fontSize': '2rem', 'display': 'inline-block', 'color': teal}),
                    dbc.Tooltip('Analyze cycling activities', target="bicycle-icon"),
                    dbc.Tooltip('Toggle activity type', target="activity-type-toggle"),
                    dbc.Tooltip('Analyze running activities', target="running-icon"),

                    html.I(style={'fontSize': '2rem', 'display': 'inline-block', 'paddingLeft': '1%',
                                  'paddingRight': '1%'}),

                    html.I(id='bolt-icon', className='fa fa-bolt',
                           style={'fontSize': '2rem', 'display': 'inline-block',
                                  'color': teal}),

                    daq.ToggleSwitch(id='power-unit-toggle', className='mr-2 ml-2', style={'display': 'inline-block'},
                                     value=False),

                    html.I(id='weight-icon', className='fa fa-weight',
                           style={'fontSize': '2rem', 'display': 'inline-block'}),

                    dbc.Tooltip('Show watts', target="bolt-icon"),
                    dbc.Tooltip('Toggle power unit', target="power-unit-toggle"),
                    dbc.Tooltip('Show watts/kg', target="weight-icon"),

                ]),
            ]),

            html.Div(id='power-curve-and-zone', className='row mt-2 mb-2',
                     children=[
                         html.Div(className='col-lg-8', children=[
                             dbc.Card(children=[
                                 dbc.CardHeader(id='power-curve-kpis',
                                                children=[html.H4('Power Duration Curve', className='mb-0')]),
                                 dbc.Spinner(color='info', children=[
                                     dbc.CardBody(
                                         html.Div(className='row', children=[
                                             html.Div(id='power-curve-container', className='col-lg-9', children=[
                                                 dcc.Graph(id='power-curve-chart', config={'displayModeBar': False},
                                                           style={'height': '100%'})
                                             ]),
                                             html.Div(id='stryd-distributions', className='col-lg-3',
                                                      style={'paddingLeft': 0}),
                                         ]),

                                     )
                                 ]),
                             ]),
                         ]),
                         html.Div(className='col-lg-4', children=[
                             dbc.Card(children=[
                                 dbc.CardHeader(html.H4(id='ftp-current', className='mb-0')),
                                 dbc.Tooltip(
                                     'Functional Threshold Power (FTP) is the highest average power you can sustain for 1 hour, measured in watts. FTP is used to determine training zones when using a power meter and to measure improvement.',
                                     target="ftp-current", ),
                                 dbc.Spinner(color='info', children=[
                                     dbc.CardBody(dcc.Graph(id='ftp-chart', config={'displayModeBar': False},
                                                            style={'height': '100%'}, ))
                                 ]),
                             ]
                             ),

                         ]),
                     ]),
            html.Div(id='power-profile-header',
                     className='row align-items-center text-center mt-2 mb-2', children=[
                    html.Div(className='col', children=[
                        html.H6('Power Profiles by'),
                        html.Div(id='power-profile-buttons', className='col', children=[
                            dbc.Button('Day', id='day-button', color='primary', size='sm'),
                            dbc.Button('Week', id='week-button', color='primary', size='sm'),
                            dbc.Button('Month', id='month-button', color='primary', size='sm'),
                            dbc.Button('Year', id='year-button', color='primary', size='sm'),
                        ]),
                    ]),
                ]),

            html.Div(id='power-profiles', className='row', children=[
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-5', children=[
                        dbc.CardHeader(html.H4('5 Second Max Power', className='mb-0')),
                        dbc.Spinner(color='info', children=[
                            dbc.CardBody(
                                dcc.Graph(
                                    id='power-profile-5-chart',
                                    config={'displayModeBar': False},
                                    style={'height': '100%'},
                                )
                            )
                        ]),
                    ]
                             )
                ]),
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-60', children=[
                        dbc.CardHeader(html.H4('1 Minute Max Power', className='mb-0')),
                        dbc.Spinner(color='info', children=[
                            dbc.CardBody(
                                dcc.Graph(
                                    id='power-profile-60-chart',
                                    config={'displayModeBar': False},
                                    style={'height': '100%'},
                                )
                            )
                        ]),
                    ]
                             )
                ]),
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-300', children=[
                        dbc.CardHeader(html.H4('5 Minute Max Power', className='mb-0')),
                        dbc.Spinner(color='info', children=[
                            dbc.CardBody(
                                dcc.Graph(
                                    id='power-profile-300-chart',
                                    config={'displayModeBar': False},
                                    style={'height': '100%'},
                                )
                            )
                        ]),
                    ]
                             )
                ]),
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-1200', children=[
                        dbc.CardHeader(html.H4('20 Minute Max Power', className='mb-0')),
                        dbc.Spinner(color='info', children=[
                            dbc.CardBody(
                                dcc.Graph(
                                    id='power-profile-1200-chart',
                                    config={'displayModeBar': False},
                                    style={'height': '100%'},
                                )
                            )
                        ]),
                    ]
                             )
                ]),
            ])
        ])
