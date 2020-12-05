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
                html.H4(id='power-curve-title', className='mb-2',
                        children='Power Curve {}'.format(timedelta(seconds=interval))),
            ]),
            dbc.Tooltip(
                '''A high power output for short periods of time (10 seconds) can contribute to improved performance across your entire Power Duration Curve. To improve musle power, focus on VO2 Max Intervals, Hill / Track Repeats and Supplemental Training.
                
                Fatigue resistance directly reflects your ability to run at close to maximal effort for your goal race distance. To improve fatigue fesistance, focus on Long Runs, High Volume Easy Runs, and Aerobic Threshold Tempo Runs.
                
                Building up your endurance with longer runs helps improve your body's ability to sustain efforts for long durations. To improve endurance, focus on Aerobic Threshold Tempo Runs, Race Specific Training and Long Runs.''',
                target="power-curve-title"),

            ### All KPI ###
            html.Div(id='all-kpi', className='col-auto mb-2', children=[
                html.H5('All Time {}'.format(all),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': white, 'backgroundColor': dark_blue, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### L90D KPI ###
            html.Div(id='L90D-kpi', className='col-auto mb-2', children=[
                html.H5('L90D {}'.format(L90D if pr == '' else pr),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': white, 'backgroundColor': light_blue if pr == '' else orange,
                               'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### L6W KPI ###
            html.Div(id='l6w-kpi', className='col-auto mb-2', children=[
                html.H5('L6W {}'.format(l6w),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': 'rgb(46,46,46)', 'backgroundColor': white, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### Last KPI ###
            html.Div(id='last-kpi', className='col-auto mb-2', children=[
                html.H5('Workout {}'.format(last),
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
            transition=dict(duration=transition),
            font=dict(
                color='rgb(220,220,220)'
            ),
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


def power_curve(activity_type='ride', power_unit='mmp', last_id=None, showlegend=False, strydmetrics=True):
    # TODO: Add power cuvrve model once sweatpy has been finished
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
    TD_df_L90D = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.type.ilike(activity_type),
                                                      stravaBestSamples.timestamp_local >= (
                                                              datetime.now() - timedelta(days=90))
                                                      ).statement, con=engine)

    td_data_exists = len(TD_df_L90D) > 0
    # If training distribution data exists
    if td_data_exists:
        TD_df_L90D['act_name'] = TD_df_L90D['activity_id'].map(act_dict['act_name'])

        # Join in weight at the time of workout for calculating FTP_W/kg at point in time (of workout)
        TD_df_L90D = TD_df_L90D.merge(pd.read_sql(
            sql=app.session.query(stravaSummary.activity_id, stravaSummary.weight).filter(
                stravaSummary.activity_id.in_(TD_df_L90D['activity_id'].unique().tolist())).statement,
            con=engine),
            how='left', right_on='activity_id', left_on='activity_id')
        TD_df_L90D.set_index(TD_df_L90D['interval'], inplace=True)
        TD_df_L90D['ftp_wkg'] = TD_df_L90D['ftp'] / (TD_df_L90D['weight'] * 0.453592)

        ### Calculations for L90D workouts based on todays weights for stryd comparisons ###
        # Stryd uses "Current FTP" and "Current Weight" across all workouts for last 90 days
        # To align with their percentiles, we need to use "current" metrics to compare against any workout within last 90 days
        # Stryd also only computes based off of W, so need to hardcode percentils to W even when toggling W/kg in fitly
        current_weight_kg = app.session.query(withings).order_by(withings.date_utc.desc()).first().weight * 0.453592
        last_workout = TD_df_L90D[TD_df_L90D['date'] == TD_df_L90D['date'].max()]
        current_ftp_w = last_workout.ftp.values[0]
        endurance_df_mmp = TD_df_L90D.loc[TD_df_L90D[TD_df_L90D['mmp'] > (current_ftp_w / 2)].index.max()]
        fatigue_df_mmp = TD_df_L90D.loc[TD_df_L90D[TD_df_L90D['mmp'] > current_ftp_w].index.max()]

        # For actual power curve chart, we will use ftp as of when the workout was done for a more accurate chart or PRs
        workout_ftp = TD_df_L90D.ftp_wkg.values[0] if power_unit == 'watts_per_kg' else TD_df_L90D.ftp.values[0]
        endurance_df = TD_df_L90D.loc[TD_df_L90D[TD_df_L90D[power_unit] > (workout_ftp / 2)].index.max()]
        fatigue_df = TD_df_L90D.loc[TD_df_L90D[TD_df_L90D[power_unit] > workout_ftp].index.max()]

        # Muscle power is just best 10 second power (weight/ftp do not matter)
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
    interval_lengths += [i for i in range(75, 1201, 5)]
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

    # Pull max power from all intervals from latest workout

    if last_id is None:
        last_id = app.session.query(stravaSummary.activity_id).filter(stravaSummary.type.ilike(activity_type)).order_by(
            stravaSummary.start_date_utc.desc()).first()[0]

    recent_best_interval_df = pd.read_sql(
        sql=app.session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.activity_id == last_id,
                                                      stravaBestSamples.interval.in_(interval_lengths),
                                                      ).statement, con=engine, index_col='interval')
    recent_best_interval_df['act_name'] = recent_best_interval_df['activity_id'].map(act_dict['act_name'])

    first_workout_date = app.session.query(func.min(stravaSummary.start_date_utc)).first()[0]

    app.session.remove()

    if len(all_best_interval_df) < 1:
        return {}

    hoverData = {'points': [
        {'x': 60,
         'y': ((all_best_interval_df.loc[60]['watts_per_kg']) if len(all_best_interval_df) > 0 else 0),
         'customdata': 'x_x_at'},
        {'y': ((L90D_best_interval_df.loc[60]['watts_per_kg']) if len(
            L90D_best_interval_df) > 0 else 0), 'customdata': 'x_x_L90D'},
        {'y': ((L6W_best_interval_df.loc[60]['watts_per_kg']) if len(
            L6W_best_interval_df) > 0 else 0), 'customdata': 'x_x_l6w'},
        {'y': ((recent_best_interval_df.loc[60]['watts_per_kg']) if len(
            recent_best_interval_df) > 0 else 0), 'customdata': 'x_x_w'}
    ]} if power_unit == 'watts_per_kg' else {'points': [
        {'x': 60,
         'y': (round(all_best_interval_df.loc[60]['mmp']) if len(all_best_interval_df) > 0 else 0),
         'customdata': 'x_x_at'},
        {'y': (round(L90D_best_interval_df.loc[60]['mmp']) if len(
            L90D_best_interval_df) > 0 else 0), 'customdata': 'x_x_L90D'},
        {'y': (round(L6W_best_interval_df.loc[60]['mmp']) if len(
            L6W_best_interval_df) > 0 else 0), 'customdata': 'x_x_l6w'},
        {'y': (round(recent_best_interval_df.loc[60]['mmp']) if len(
            recent_best_interval_df) > 0 else 0), 'customdata': 'x_x_w'}
    ]}

    # Check if value L90D values are all time bests
    # Make 2nd line for L90D PR and highlight orange and remove points from L90D df to avoid duplicate tooltips
    pr_df = L90D_best_interval_df.copy()
    # If less than 90 days of data, everything is a PR
    if first_workout_date < (datetime.now() - timedelta(days=90)):
        for i in pr_df.index:
            if pr_df.at[i, power_unit] == all_best_interval_df.at[i, power_unit]:
                L90D_best_interval_df.at[i, power_unit] = None
            else:
                pr_df.at[i, power_unit] = None

    tooltip = '''{}<br>{}<br>{:.2f} W/kg''' if power_unit == 'watts_per_kg' else '''{}<br>{}<br>{:.0f} W'''

    data = [
        go.Scatter(
            name='All',
            x=all_best_interval_df.index,
            y=all_best_interval_df[power_unit],
            mode='lines',
            text=[
                tooltip.format(
                    all_best_interval_df.loc[i]['act_name'],
                    all_best_interval_df.loc[i].date,
                    all_best_interval_df.loc[i][power_unit])
                for i in all_best_interval_df.index],

            customdata=[
                '{}_{}_at'.format(all_best_interval_df.loc[x]['activity_id'], int(x))
                for x in all_best_interval_df.index],  # add fields to text so data can go through clickData
            hoverinfo='text',
            line={'shape': 'spline', 'color': dark_blue},
        ),
        go.Scatter(
            name='L90D',
            x=L90D_best_interval_df.index,
            y=L90D_best_interval_df[power_unit],
            mode='lines',
            # text=['{:.0f}'.format(L90D_best_interval_df.loc[i]['mmp']) for i in
            #       L90D_best_interval_df.index],
            text=[
                tooltip.format(
                    L90D_best_interval_df.loc[i]['act_name'],
                    L90D_best_interval_df.loc[i].date,
                    L90D_best_interval_df.loc[i][power_unit])
                for i in L90D_best_interval_df.index],
            customdata=[
                '{}_{}_L90D'.format(L90D_best_interval_df.loc[x]['activity_id'], int(x))
                for x in L90D_best_interval_df.index],
            hoverinfo='text',
            line={'shape': 'spline', 'color': light_blue},
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
                    L6W_best_interval_df.loc[i]['act_name'],
                    L6W_best_interval_df.loc[i].date,
                    L6W_best_interval_df.loc[i][power_unit])
                for i in L6W_best_interval_df.index],
            customdata=[
                '{}_{}_l6w'.format(L6W_best_interval_df.loc[x]['activity_id'], int(x))
                for x in L6W_best_interval_df.index],
            hoverinfo='text',
            line={'shape': 'spline', 'color': white},
        ),
        go.Scatter(
            name='Workout',
            x=recent_best_interval_df.index,
            y=recent_best_interval_df[power_unit],
            mode='lines',
            # text=['{:.0f}'.format(L90D_best_interval_df.loc[i]['mmp']) for i in
            #       L90D_best_interval_df.index],
            text=[
                tooltip.format(
                    recent_best_interval_df.loc[i]['act_name'],
                    recent_best_interval_df.loc[i].date,
                    recent_best_interval_df.loc[i][power_unit])
                for i in recent_best_interval_df.index],
            customdata=[
                '{}_{}_w'.format(recent_best_interval_df.loc[x]['activity_id'], int(x))
                for x in recent_best_interval_df.index],
            hoverinfo='text',
            line={'shape': 'spline', 'color': teal},
        ),
        go.Scatter(
            name='PR L90D',
            x=pr_df.index,
            y=pr_df[power_unit],
            mode='lines',
            # text=['{:.0f}'.format(L90D_best_interval_df.loc[i]['mmp']) for i in
            #       L90D_best_interval_df.index],
            text=[
                tooltip.format(
                    pr_df.loc[i]['act_name'],
                    pr_df.loc[i].date,
                    pr_df.loc[i][power_unit])
                for i in pr_df.index],
            customdata=[
                '{}_{}_pr'.format(pr_df.loc[x]['activity_id'], int(x))
                for x in pr_df.index],
            hoverinfo='text',
            line={'shape': 'spline', 'color': orange},
            connectgaps=False,

        )
    ]
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
            y=workout_ftp,
            xref="x",
            yref="y",
            text='''100% CP (L90D): <b>{:.2f}</b> W/kg'''.format(
                workout_ftp) if power_unit == 'watts_per_kg' else '''100% CP (L90D): <b>{:.0f}</b> W'''.format(
                workout_ftp),
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
            y=workout_ftp / 2,
            xref="x",
            yref="y",
            text='''50% CP (L90D): <b>{:.2f}</b> W/kg'''.format(
                workout_ftp / 2) if power_unit == 'watts_per_kg' else '''50% CP (L90D): <b>{:.0f}</b> W'''.format(
                workout_ftp / 2),
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
            type='line', y0=workout_ftp, y1=workout_ftp, xref='x', yref='y', x0=.9,
            line=dict(
                color="Grey",
                width=1,
                dash="dot",
            ),
        ),
        # Endurance
        dict(
            type='line', y0=workout_ftp / 2, y1=workout_ftp / 2, xref='x', yref='y', x0=.9,
            line=dict(
                color="Grey",
                width=1,
                dash="dot",
            ),
        )
    ] if td_data_exists else []

    if stryd_credentials_supplied and strydmetrics and td_data_exists:
        ### STRYD TRAINING DISTRIBUTION USES CURRENT WEIGHT WHEN CALCULATING W/KG ###
        ### TRAINING DIST BARS WILL DO THE SAME TO BETTER ALIGN WITH PERCENTILES ###
        ### ACTUAL DATA SHOWN IN POWER CURVE WILL BE BASED ON FTP AT THE TIME OF RECORDING FOR BETTER ACCURACY ###

        # Make room on canvas for training dist bars
        td = get_training_distribution()
        data.extend([
            # Fitness
            go.Bar(
                xaxis='x2', yaxis='y2', customdata=['ignore'], x=[100], y=[''], width=[2],
                marker=dict(color=light_blue),
                text='Fitness: <b>{:.2f}</b> W/kg<br>Stryd Avg: <b>{:.2f}</b> W/kg<br>Percentile: <b>{:.0%}'.format(
                    last_workout.ftp.values[0] / current_weight_kg, td["percentile"]["median_fitness"],
                    td["percentile"]["fitness"]),
                hoverinfo='text', orientation='h'),

            # Muscle Power
            go.Bar(
                xaxis='x3', yaxis='y2', customdata=['ignore'], x=[100], y=[''], width=[2],
                marker=dict(color=light_blue),
                text='Max 10 Sec Power: <b>{:.2f} </b>W/kg<br>Stryd Avg: <b>{:.2f}</b> W/kg<br>Percentile: <b>{:.0%}'.format(
                    TD_df_at.loc[10]['mmp'] / current_weight_kg, td["percentile"]["median_muscle_power"],
                    td["percentile"]["muscle_power"]),
                hoverinfo='text', orientation='h'),

            # Fatigue Resistance
            go.Bar(
                xaxis='x4', yaxis='y2', customdata=['ignore'], x=[100], y=[''], width=[2],
                marker=dict(color=light_blue),
                text='Longest 100% CP: <b>{:%H:%M:%S}</b> <br>Stryd Avg: <b>{}</b><br>Percentile: <b>{:.0%}'.format(
                    fatigue_df_mmp['time_interval'],
                    timedelta(seconds=int(td["percentile"]["median_fatigue_resistance"])),
                    td["percentile"]["fatigue_resistance"]),
                hoverinfo='text', orientation='h'),

            # Endurance
            go.Bar(
                xaxis='x5', yaxis='y2', customdata=['ignore'], x=[100], y=[''], width=[2],
                marker=dict(color=light_blue),
                text='Longest 50% CP: <b>{:%H:%M:%S}</b> <br>Stryd Avg: <b>{}</b><br>Percentile: <b>{:.0%}'.format(
                    endurance_df_mmp['time_interval'],
                    timedelta(seconds=int(td["percentile"]["median_endurance"])), td["percentile"]["endurance"]),
                hoverinfo='text', orientation='h'),
        ])

        shapes.extend([
            # Training distribution charts lines
            dict(type='line', xref='x2', yref='y2', x0=50, x1=50, y0=0, y1=.8,
                 line=dict(color=white, width=1, dash="dot", ), ),
            dict(type='line', xref='x2', yref='y2', x0=td['percentile']['fitness'] * 100,
                 x1=td['percentile']['fitness'] * 100, y0=-1, y1=1,
                 line=dict(color=white, width=2, ), ),

            dict(type='line', xref='x3', yref='y2', x0=50, x1=50, y0=0, y1=.8,
                 line=dict(color=white, width=1, dash="dot", ), ),
            dict(type='line', xref='x3', yref='y2', x0=td['percentile']['muscle_power'] * 100,
                 x1=td['percentile']['muscle_power'] * 100, y0=-1, y1=1,
                 line=dict(color=white, width=2, ), ),

            dict(type='line', xref='x4', yref='y2', x0=50, x1=50, y0=0, y1=.8,
                 line=dict(color=white, width=1, dash="dot", ), ),
            dict(type='line', xref='x4', yref='y2', x0=td['percentile']['fatigue_resistance'] * 100,
                 x1=td['percentile']['fatigue_resistance'] * 100, y0=-1, y1=1,
                 line=dict(color=white, width=2, ), ),

            dict(type='line', xref='x5', yref='y2', x0=50, x1=50, y0=0, y1=.8,
                 line=dict(color=white, width=1, dash="dot", ), ),

            dict(type='line', xref='x5', yref='y2', x0=td['percentile']['endurance'] * 100,
                 x1=td['percentile']['endurance'] * 100, y0=-1, y1=1,
                 line=dict(color=white, width=2)
                 )
        ])
        annotations.extend([
            go.layout.Annotation(
                font={'size': 12, 'color': white}, x=50, y=1.2, xref="x2", yref="y2",
                text='Fitness: {:.0f} W'.format(last_workout.ftp.values[0]),
                showarrow=False,
            ),

            go.layout.Annotation(
                font={'size': 12, 'color': white}, x=50, y=1.2, xref="x3", yref="y2",
                text='Muscle Power: {:.0f} W'.format(TD_df_at.loc[10]['mmp']),
                showarrow=False,
            ),

            go.layout.Annotation(
                font={'size': 12, 'color': white}, x=50, y=1.2, xref="x4", yref="y2",
                text='Fatigue Resistance: {:%H:%M:%S}'.format(fatigue_df_mmp['time_interval']),
                showarrow=False,
            ),
            go.layout.Annotation(
                font={'size': 12, 'color': white}, x=50, y=1.2, xref="x5", yref="y2",
                text='Endurance: {:%H:%M:%S}'.format(endurance_df_mmp['time_interval']),
                showarrow=False,
            ),

        ])

        layout = go.Layout(
            # transition=dict(duration=transition),
            font=dict(
                color='rgb(220,220,220)'
            ),
            shapes=shapes,
            annotations=annotations,
            xaxis=dict(
                showgrid=False,
                # tickformat="%H:%M:%S",
                # range=[best_interval_df.index.min(),best_interval_df.index.max()],
                # range=[np.log10(best_interval_df.index.min()), np.log10(best_interval_df.index.max())],
                type='log',
                # tickangle=0,
                tickvals=[1, 2, 5, 10, 30, 60, 120, 5 * 60, 10 * 60, 20 * 60, 60 * 60, 60 * 120],
                ticktext=['1s', '2s', '5s', '10s', '30s', '1m', '2m', '5m', '10m', '20m', '60m', '120m'],
            ),
            yaxis=dict(
                domain=[0, .9],
                showgrid=True,
                zeroline=False,
                # range=[best_interval_df['mmp'].min(), best_interval_df['mmp'].max()],
                gridcolor='rgb(73, 73, 73)'
            ),
            margin={'l': 40, 'b': 25, 't': 5, 'r': 40},
            showlegend=showlegend,
            legend={'x': .5, 'y': 1, 'xanchor': 'center', 'orientation': 'h',
                    'traceorder': 'normal', 'bgcolor': 'rgba(127, 127, 127, 0)'},
            autosize=True,
            hovermode='x',
            # TD Fitness
            xaxis2=dict(domain=[.01, .24], showgrid=False, zeroline=False, showticklabels=False, range=[0, 100], ),
            # Muscle Power
            xaxis3=dict(domain=[.26, .49], showgrid=False, zeroline=False, showticklabels=False, range=[0, 100], ),
            # Fatigue Resistance
            xaxis4=dict(domain=[.51, .74], showgrid=False, zeroline=False, showticklabels=False, range=[0, 100], ),
            # Endurance
            xaxis5=dict(domain=[.76, .99], showgrid=False, zeroline=False, showticklabels=False, range=[0, 100], ),

            yaxis2=dict(domain=[.9, 1], range=[-.2, 1.2], showgrid=False, showticklabels=False,
                        gridcolor='rgb(255, 255, 255)'),
        )
    else:
        layout = go.Layout(
            # transition=dict(duration=transition),
            font=dict(
                color='rgb(220,220,220)'
            ),
            shapes=shapes,
            annotations=annotations,
            xaxis=dict(
                showgrid=False,
                # tickformat="%H:%M:%S",
                # range=[best_interval_df.index.min(),best_interval_df.index.max()],
                # range=[np.log10(best_interval_df.index.min()), np.log10(best_interval_df.index.max())],
                type='log',

                tickvals=[1, 2, 5, 10, 30, 60, 120, 5 * 60, 10 * 60, 20 * 60, 60 * 60, 60 * 90],
                ticktext=['1s', '2s', '5s', '10s', '30s', '1m', '2m', '5m', '10m', '20m', '60m',
                          '90m'],
            ),

            yaxis=dict(
                showgrid=True,
                zeroline=False,
                # range=[best_interval_df['mmp'].min(), best_interval_df['mmp'].max()],
                gridcolor='rgb(73, 73, 73)'
            ),
            margin={'l': 40, 'b': 25, 't': 5, 'r': 40},
            showlegend=showlegend,
            legend={'x': .5, 'y': 1, 'xanchor': 'center', 'orientation': 'h',
                    'traceorder': 'normal', 'bgcolor': 'rgba(127, 127, 127, 0)'},
            autosize=True,
            hovermode='x',

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

    return figure, hoverData


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
                color='rgb(220,220,220)'
            ),
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


def zone_chart(activity_id=None, metric='power_zone', chart_id='power-zone-chart'):
    # If activity_id passed, filter only that workout, otherwise show distribution across last 6 weeks

    if activity_id:
        df_samples = pd.read_sql(
            sql=app.session.query(stravaSamples).filter(stravaSamples.activity_id == activity_id).statement,
            con=engine,
            index_col=['timestamp_local'])
    else:
        df_samples = pd.read_sql(
            sql=app.session.query(stravaSamples).filter(
                stravaSamples.timestamp_local >= (datetime.now() - timedelta(days=42))).statement,
            con=engine,
            index_col=['timestamp_local'])

    app.session.remove()

    pz_df = df_samples.groupby(metric).size().reset_index(name='counts')
    pz_df['seconds'] = pz_df['counts']
    pz_df['Percent of Total'] = (pz_df['seconds'] / pz_df['seconds'].sum())
    pz_df = pz_df.sort_index(ascending=False)

    # zone_map = {1: 'Active Recovery', 2: 'Endurance', 3: 'Tempo', 4: 'Threshold', 5: 'VO2 Max',
    #             6: 'Anaerobic', 7: 'Neuromuscular'}

    zone_map = {1: 'Zone 1', 2: 'Zone 2', 3: 'Zone 3', 4: 'Zone 4', 5: 'Zone 5',
                6: 'Zone 6', 7: 'Zone 7'}

    pz_df[metric] = pz_df[metric].map(zone_map)

    label = ['Time: ' + '{}'.format(timedelta(seconds=seconds)) + '<br>' + '% of Total: ' + '<b>{0:.0f}'.format(
        percentage * 100) + '%'
             for seconds, percentage in zip(list(pz_df['seconds']), list(pz_df['Percent of Total']))]

    return dcc.Graph(
        id=chart_id, style={'height': '100%'},
        config={
            'displayModeBar': False
        },
        figure={
            'data': [
                go.Bar(
                    y=pz_df[metric],
                    x=pz_df['Percent of Total'],
                    orientation='h',
                    text=label,
                    hoverinfo='none',
                    textposition='auto',
                    marker={'color': [
                        'rgb(250, 47, 76)',
                        'rgb(250, 82, 104)',
                        'rgb(250, 116, 133)',
                        'rgb(251, 150, 162)',
                        'rgb(255, 187, 194)',
                        'rgb(255, 221, 224)',
                        'rgb(232, 236, 240)'
                    ]},
                )
            ],
            'layout': go.Layout(
                font=dict(
                    color='rgb(220,220,220)'
                ),
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
                ),
                margin={'l': 45, 'b': 0, 't': 25, 'r': 0},

            )
        }
    )


@app.callback(
    [Output('power-curve-chart', 'figure'),
     Output('power-curve-chart', 'hoverData')],
    [Input('activity-type-toggle', 'value'),
     Input('power-unit-toggle', 'value')]
)
def update_power_curve(activity_type, power_unit):
    power_unit = 'watts_per_kg' if power_unit else 'mmp'
    activity_type = 'ride' if activity_type else 'run'
    figure, hoverData = power_curve(activity_type, power_unit, strydmetrics=False if activity_type == 'ride' else True)
    return figure, hoverData


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


@app.callback(
    Output('power-curve-kpis', 'children'),
    [Input('power-curve-chart', 'hoverData')],
    [State('power-unit-toggle', 'value')])
def update_fitness_kpis(hoverData, power_unit):
    interval, at, L90D, l6w, last, pr = 0, '', '', '', '', ''
    if hoverData is not None and hoverData['points'][0]['customdata'] != 'ignore':
        interval = hoverData['points'][0]['x']
        for x in hoverData['points']:
            if x['customdata'].split('_')[2] == 'at':
                at = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
            elif x['customdata'].split('_')[2] == 'L90D':
                L90D = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
            elif x['customdata'].split('_')[2] == 'l6w':
                l6w = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
            elif x['customdata'].split('_')[2] == 'pr':
                pr = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])
            elif x['customdata'].split('_')[2] == 'w':
                last = '{:.1f} W/kg'.format(x['y']) if power_unit else '{:.0f} W'.format(x['y'])

    return create_power_curve_kpis(interval, at, L90D, l6w, last, pr)


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
                                 dbc.CardHeader(id='power-curve-kpis'),
                                 dbc.CardBody(
                                     dcc.Graph(id='power-curve-chart', config={'displayModeBar': False},
                                               style={'height': '100%'}))
                             ]),
                         ]),
                         html.Div(className='col-lg-4', children=[
                             dbc.Card(children=[
                                 dbc.CardHeader(html.H4(id='ftp-current')),
                                 dbc.Tooltip(
                                     'Functional Threshold Power (FTP) is the highest average power you can sustain for 1 hour, measured in watts. FTP is used to determine training zones when using a power meter and to measure improvement.',
                                     target="ftp-current", ),
                                 dbc.CardBody(dcc.Graph(id='ftp-chart', config={'displayModeBar': False},
                                                        style={'height': '100%'}, ))
                             ]
                             ),

                         ]),
                     ]),
            html.Div(id='power-profile-header',
                     className='row align-items-center text-center mt-2 mb-2', children=[
                    html.Div(className='col', children=[
                        html.H6('Power Profiles by'),
                        html.Div(id='power-profile-buttons', className='col', children=[
                            dbc.Button('Day', id='day-button', color='primary', size='md'),
                            dbc.Button('Week', id='week-button', color='primary', size='md'),
                            dbc.Button('Month', id='month-button', color='primary', size='md'),
                            dbc.Button('Year', id='year-button', color='primary', size='md'),
                        ]),
                    ]),
                ]),

            html.Div(id='power-profiles', className='row', children=[
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-5', children=[
                        dbc.CardHeader(html.H4('5 Second Max Power')),
                        dbc.CardBody(dcc.Graph(
                            id='power-profile-5-chart',
                            config={'displayModeBar': False},
                            style={'height': '100%'},
                        )
                        )])]),
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-60', children=[
                        dbc.CardHeader(html.H4('1 Minute Max Power')),
                        dbc.CardBody(dcc.Graph(
                            id='power-profile-60-chart',
                            config={'displayModeBar': False},
                            style={'height': '100%'},
                        )
                        )])]),
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-300', children=[
                        dbc.CardHeader(html.H4('5 Minute Max Power')),
                        dbc.CardBody(dcc.Graph(
                            id='power-profile-300-chart',
                            config={'displayModeBar': False},
                            style={'height': '100%'},
                        )
                        )])]),
                html.Div(className='col-lg-3', children=[
                    dbc.Card(id='power-profile-1200', children=[
                        dbc.CardHeader(html.H4('20 Minute Max Power')),
                        dbc.CardBody(dcc.Graph(
                            id='power-profile-1200-chart',
                            config={'displayModeBar': False},
                            style={'height': '100%'},
                        )
                        )])]),
            ])
        ])
