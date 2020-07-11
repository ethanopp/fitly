import pandas as pd
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
import dash_daq as daq
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from ..api.sqlalchemy_declarative import db_connect, stravaSummary, stravaSamples, stravaBestSamples, athlete
from ..app import app
from datetime import datetime, timedelta
import operator
from ..utils import config
from sqlalchemy import func
import math

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
        html.Div(className='row', children=[
            ### Interval KPI ###
            html.Div(className='col-auto', children=[
                html.H4('Power Curve {}'.format(timedelta(seconds=interval))),

            ]),
            ### All KPI ###
            html.Div(id='all-kpi', className='col-auto', children=[
                html.H6('All Time {}'.format(all),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': white, 'backgroundColor': dark_blue, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### L90D KPI ###
            html.Div(id='L90D-kpi', className='col-auto', children=[
                html.H6('L90D {}'.format(L90D if pr == '' else pr),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': white, 'backgroundColor': light_blue if pr == '' else orange,
                               'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### L6W KPI ###
            html.Div(id='l6w-kpi', className='col-auto', children=[
                html.H6('L6W {}'.format(l6w),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': 'rgb(46,46,46)', 'backgroundColor': white, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),
            ### Last KPI ###
            html.Div(id='last-kpi', className='col-auto', children=[
                html.H6('Workout {}'.format(last),
                        style={'display': 'inline-block',  # 'fontWeight': 'bold',
                               'color': 'rgb(46,46,46)', 'backgroundColor': teal, 'marginTop': '0',
                               'marginBottom': '0',
                               'borderRadius': '.3rem'}),
            ]),

        ]),


def get_workout_title(activity_id=None):
    session, engine = db_connect()
    min_non_warmup_workout_time = session.query(athlete).filter(
        athlete.athlete_id == 1).first().min_non_warmup_workout_time
    activity_id = session.query(stravaSummary.activity_id).filter(stravaSummary.type.ilike('%ride%'),
                                                                  stravaSummary.elapsed_time > min_non_warmup_workout_time).order_by(
        stravaSummary.start_date_utc.desc()).first()[0] if not activity_id else activity_id
    df_samples = pd.read_sql(
        sql=session.query(stravaSamples).filter(stravaSamples.activity_id == activity_id).statement,
        con=engine,
        index_col=['timestamp_local'])
    engine.dispose()
    session.close()

    return [html.H6(datetime.strftime(df_samples['date'][0], "%A %b %d, %Y"), style={'height': '50%'}),
            html.H6(df_samples['act_name'][0], style={'height': '50%'})]


def power_profiles(interval, activity_type='ride', power_unit='mmp', group='month'):
    activity_type = '%' + activity_type + '%'
    session, engine = db_connect()
    # Filter on interval passed
    df_best_samples = pd.read_sql(
        sql=session.query(stravaBestSamples).filter(stravaBestSamples.type.ilike(activity_type),
                                                    stravaBestSamples.interval == interval).statement, con=engine,
        index_col=['timestamp_local'])
    engine.dispose()
    session.close()
    if len(df_best_samples) < 1:
        return {}

    pp_date_dict = {'day': 'D', 'week': 'W', 'month': 'M', 'year': 'Y'}
    # Create columns for x-axis
    df_best_samples['power_profile_dategroup'] = df_best_samples.index.to_period(pp_date_dict[group]).to_timestamp()

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
                    '{:.1f} W/kg'.format(x) if power_unit == 'watts_per_kg' else '{:.0f} W'.format(
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


def power_curve(activity_type='ride', power_unit='mmp', last_id=None, showlegend=False):
    activity_type = '%' + activity_type + '%'

    session, engine = db_connect()

    max_interval = session.query(
        func.max(stravaBestSamples.interval).label('interval')).filter(
        stravaBestSamples.type.ilike(activity_type)).first()[0]

    # 1 second intervals from 0-60 seconds
    interval_lengths = [i for i in range(1, 61)]
    # 15 second intervals from 1:15 - 5:00 mins
    interval_lengths += [i for i in range(75, 301, 15)]
    # 30 second intervals for 5:00 - 10:00
    interval_lengths += [i for i in range(330, 601, 30)]
    # 1 minute intervals for everything after 10 mins
    interval_lengths += [i for i in range(660, (int(math.floor(max_interval / 10.0)) * 10) + 1, 60)]

    act_dict = pd.read_sql(
        sql=session.query(stravaBestSamples.activity_id, stravaBestSamples.act_name).distinct().statement, con=engine,
        index_col='activity_id').to_dict()

    all_best_interval_df = pd.read_sql(
        sql=session.query(
            func.max(stravaBestSamples.mmp).label('mmp'),
            stravaBestSamples.activity_id, stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type)).statement,
        con=engine, index_col='interval')
    all_best_interval_df['act_name'] = all_best_interval_df['activity_id'].map(act_dict['act_name'])

    L90D_best_interval_df = pd.read_sql(
        sql=session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id, stravaBestSamples.ftp,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type),
                                                      stravaBestSamples.timestamp_local >= (
                                                              datetime.now() - timedelta(days=90))
                                                      ).statement, con=engine, index_col='interval')

    L90D_best_interval_df['act_name'] = L90D_best_interval_df['activity_id'].map(act_dict['act_name'])

    # # Data points for Power Curve Training Disribution
    muscle_power = L90D_best_interval_df.loc[10][power_unit]
    current = L90D_best_interval_df[L90D_best_interval_df['date'] == L90D_best_interval_df['date'].max()]
    current_ftp = current.watts_per_kg.values[0] if power_unit == 'watts_per_kg' else current.ftp.values[0]

    endurance_duration = L90D_best_interval_df[L90D_best_interval_df[power_unit] > current_ftp / 2].index.max()
    endurance_df = L90D_best_interval_df.loc[endurance_duration]

    fatigue_duration = L90D_best_interval_df[L90D_best_interval_df[power_unit] > current_ftp].index.max()
    fatigue_df = L90D_best_interval_df.loc[fatigue_duration]

    L6W_best_interval_df = pd.read_sql(
        sql=session.query(
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
        last_id = session.query(stravaSummary.activity_id).filter(stravaSummary.type.ilike(activity_type)).order_by(
            stravaSummary.start_date_utc.desc()).first()[0]

    recent_best_interval_df = pd.read_sql(
        sql=session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.activity_id == last_id,
                                                      stravaBestSamples.interval.in_(interval_lengths),
                                                      ).statement, con=engine, index_col='interval')
    recent_best_interval_df['act_name'] = recent_best_interval_df['activity_id'].map(act_dict['act_name'])

    first_workout_date = session.query(func.min(stravaSummary.start_date_utc)).first()[0]

    engine.dispose()
    session.close()

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

    # Make 2nd line for L6W pr and highlight orange and remove points from L6W df to avoid duplicate tooltips
    pr_df = L90D_best_interval_df.copy()
    # If less than 90 days of data, everything is a PR
    if first_workout_date < (datetime.now() - timedelta(days=90)):
        for i in pr_df.index:
            if pr_df.at[i, power_unit] == all_best_interval_df.at[i, power_unit]:
                L90D_best_interval_df.at[i, power_unit] = None
            else:
                pr_df.at[i, power_unit] = None

    tooltip = '''{}<br>{:.1f} W/kg''' if power_unit == 'watts_per_kg' else '''{}<br>{:.0f} W'''
    data = [
        go.Scatter(
            name='All',
            x=all_best_interval_df.index,
            y=all_best_interval_df[power_unit],
            mode='lines',
            text=[
                tooltip.format(
                    all_best_interval_df.loc[i]['act_name'],
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
                    pr_df.loc[i][power_unit])
                for i in pr_df.index],
            customdata=[
                '{}_{}_pr'.format(pr_df.loc[x]['activity_id'], int(x))
                for x in pr_df.index],
            hoverinfo='text',
            line={'shape': 'spline', 'color': orange},
            connectgaps=False,

        ),
    ]

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
    figure = {
        'data': data,
        'layout': go.Layout(
            transition=dict(duration=transition),
            font=dict(
                color='rgb(220,220,220)'
            ),
            #TODO: Clean up line formatting and add descriptions as to what each line representes (from stryd)
            shapes=[
                # Muscle Power
                dict(
                    type='line',
                    y0=0, y1=muscle_power,
                    xref='x',
                    yref='y',
                    x0=10, x1=10,
                    line=dict(
                        color="Grey",
                        width=1,
                        dash="dot",
                    ),
                ),
                dict(
                    type='line',
                    y0=muscle_power, y1=muscle_power,
                    xref='x',
                    yref='y',
                    x0=.9, x1=1,
                    line=dict(
                        color="Grey",
                        width=1,
                        dash="dot",
                    ),
                ),

                # Fatigue Resistance
                dict(
                    type='line',
                    y1=fatigue_df[power_unit],
                    xref='x',
                    yref='y',
                    x0=fatigue_duration, x1=fatigue_duration,
                    line=dict(
                        color="Grey",
                        width=1,
                        dash="dot",
                    ),
                ),
                dict(
                    type='line',
                    y0=fatigue_df[power_unit], y1=fatigue_df[power_unit],
                    xref='x',
                    yref='y',
                    x0=.9, x1=fatigue_duration,
                    line=dict(
                        color="Grey",
                        width=1,
                        dash="dot",
                    ),
                ),
                # Endurance

                dict(
                    type='line',
                    y1=endurance_df[power_unit],
                    xref='x',
                    yref='y',
                    x0=endurance_duration, x1=endurance_duration,
                    line=dict(
                        color="Grey",
                        width=1,
                        dash="dot",
                    ),
                ),
                dict(
                    type='line',
                    y0=endurance_df[power_unit], y1=endurance_df[power_unit],
                    xref='x',
                    yref='y',
                    x0=.9, x1=endurance_duration,
                    line=dict(
                        color="Grey",
                        width=1,
                        dash="dot",
                    ),
                ),

            ],

            annotations=[
                # Muscle Power
                go.layout.Annotation(
                    font={'size': 12},
                    x=1,
                    y=muscle_power,
                    xref="x",
                    yref="y",
                    text='''Muscle Power {:.2f} W/kg'''.format(
                        muscle_power) if power_unit == 'watts_per_kg' else '''Muscle Power {:.0f} W'''.format(
                        muscle_power),
                    showarrow=True,
                    arrowhead=1,
                    arrowcolor='Grey',
                    ax=30,
                    ay=-30,
                ),
                # Fatigue Resistance
                go.layout.Annotation(
                    font={'size': 12},
                    x=math.log(fatigue_duration, 10),
                    y=fatigue_df[power_unit],
                    xref="x",
                    yref="y",
                    text='''Fatigue Resistance {:%H:%M:%S} at {:.2f} W/kg'''.format(fatigue_df['time_interval'],
                                                                                    fatigue_df[
                                                                                        power_unit]) if power_unit == 'watts_per_kg' else '''Endurance Power {:.0f} W'''.format(
                        fatigue_df[power_unit]),
                    showarrow=True,
                    arrowhead=1,
                    arrowcolor='Grey',
                    ax=30,
                    ay=-30,

                ),
                # Endurance
                go.layout.Annotation(
                    font={'size': 12},
                    x=math.log(endurance_duration, 10),
                    y=endurance_df[power_unit],
                    xref="x",
                    yref="y",
                    text='''Endurance {:%H:%M:%S} at {:.2f} W/kg'''.format(endurance_df['time_interval'],
                                                                           endurance_df[
                                                                               power_unit]) if power_unit == 'watts_per_kg' else '''Endurance Power {:.0f} W'''.format(
                        endurance_df[power_unit]),
                    showarrow=True,
                    arrowhead=1,
                    arrowcolor='Grey',
                    ax=30,
                    ay=30,
                ),

            ],

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
    }
    return figure, hoverData


def create_ftp_chart(activity_type='ride', power_unit='watts'):
    activity_type = '%' + activity_type + '%'
    session, engine = db_connect()
    df_ftp = pd.read_sql(
        sql=session.query(stravaSummary).filter(stravaSummary.type.ilike(activity_type)).statement, con=engine,
        index_col='start_day_local')[
        ['activity_id', 'ftp', 'weight']]
    engine.dispose()
    session.close()

    df_ftp.set_index(pd.DatetimeIndex(df_ftp.index), inplace=True)
    df_ftp = df_ftp.resample('M').max()

    # Filter summary table on activities that have a different FTP from the previous activity
    df_ftp['previous_ftp'] = df_ftp['ftp'].shift(1)
    df_ftp = df_ftp[df_ftp['previous_ftp'] != df_ftp['ftp']]

    df_ftp['watts_per_kg'] = df_ftp['ftp'] / (df_ftp['weight'] / 2.20462)
    metric = 'ftp' if power_unit == 'ftp' else 'watts_per_kg'
    tooltip = '<b>{:.0f} W {}' if metric == 'ftp' else '<b>{:.1f} W/kg {}'
    title = 'Current FTP {:.0f} W' if metric == 'ftp' else 'Current FTP {:.1f} W/kg'

    if len(df_ftp) < 1:
        return None, {}

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
                ticktext=df_ftp['start_day_local'].apply(lambda x: datetime.strftime(x, "%b '%y")),
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
    session, engine = db_connect()
    if activity_id:
        df_samples = pd.read_sql(
            sql=session.query(stravaSamples).filter(stravaSamples.activity_id == activity_id).statement,
            con=engine,
            index_col=['timestamp_local'])
    else:
        df_samples = pd.read_sql(
            sql=session.query(stravaSamples).filter(
                stravaSamples.timestamp_local >= (datetime.now() - timedelta(days=42))).statement,
            con=engine,
            index_col=['timestamp_local'])

    engine.dispose()
    session.close()

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
    figure, hoverData = power_curve(activity_type, power_unit)
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
               Input('year-button', 'n_clicks')],
              [State('day-button', 'n_clicks_timestamp'),
               State('week-button', 'n_clicks_timestamp'),
               State('month-button', 'n_clicks_timestamp'),
               State('year-button', 'n_clicks_timestamp')]
              )
def update_power_profiles(activity_type, power_unit, day_n_clicks, week_n_clicks, month_n_clicks, year_n_clicks,
                          day_n_clicks_timestamp, week_n_clicks_timestamp, month_n_clicks_timestamp,
                          year_n_clicks_timestamp):
    latest = 'month'
    power_unit = 'watts_per_kg' if power_unit else 'mmp'
    activity_type = 'ride' if activity_type else 'run'

    day_style, week_style, month_style, year_style = {'marginRight': '1%'}, {'marginRight': '1%'}, {
        'marginRight': '1%'}, {'marginRight': '1%'}
    day_n_clicks_timestamp = 0 if not day_n_clicks_timestamp else day_n_clicks_timestamp
    week_n_clicks_timestamp = 0 if not week_n_clicks_timestamp else week_n_clicks_timestamp
    month_n_clicks_timestamp = 0 if not month_n_clicks_timestamp else month_n_clicks_timestamp
    year_n_clicks_timestamp = 0 if not year_n_clicks_timestamp else year_n_clicks_timestamp
    timestamps = {'day': day_n_clicks_timestamp, 'week': week_n_clicks_timestamp, 'month': month_n_clicks_timestamp,
                  'year': year_n_clicks_timestamp}

    if day_n_clicks or week_n_clicks or month_n_clicks or year_n_clicks:
        latest = max(timestamps.items(), key=operator.itemgetter(1))[0]

    if latest == 'day':
        day_style = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
    elif latest == 'week':
        week_style = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
    elif latest == 'month':
        month_style = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
    elif latest == 'year':
        year_style = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}

    return power_profiles(interval=5, group=latest, power_unit=power_unit, activity_type=activity_type), \
           power_profiles(interval=60, group=latest, power_unit=power_unit, activity_type=activity_type), \
           power_profiles(interval=300, group=latest, power_unit=power_unit, activity_type=activity_type), \
           power_profiles(interval=1200, group=latest, power_unit=power_unit, activity_type=activity_type), \
           day_style, week_style, month_style, year_style


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
    if hoverData is not None:
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
    return html.Div([

        html.Div(className='row', children=[
            html.Div(id='power-dashboard-header-container', className='col-12 text-center mt-2 mb-2', children=[

                html.I(id='running-icon', className='fa fa-running',
                       style={'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle'}),
                daq.ToggleSwitch(id='activity-type-toggle', className='mr-2 ml-2', style={'display': 'inline-block'}),

                html.I(id='bicycle-icon', className='fa fa-bicycle',
                       style={'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle',
                              'color': teal}),
                dbc.Tooltip('Analyze cycling activities', target="bicycle-icon"),
                dbc.Tooltip('Toggle activity type', target="activity-type-toggle"),
                dbc.Tooltip('Analyze running activities', target="running-icon"),

                html.I(style={'fontSize': '2rem', 'display': 'inline-block', 'paddingLeft': '1%',
                              'paddingRight': '1%'}),

                html.I(id='bolt-icon', className='fa fa-bolt',
                       style={'fontSize': '2rem', 'display': 'inline-block', 'vertical-align': 'middle',
                              'color': teal}),

                daq.ToggleSwitch(id='power-unit-toggle', className='mr-2 ml-2', style={'display': 'inline-block'},
                                 value=True),

                html.I(id='weight-icon', className='fa fa-weight',
                       style={'fontSize': '2rem', 'display': 'inline-block',
                              'vertical-align': 'middle'}),

                dbc.Tooltip('Show watts', target="bolt-icon"),
                dbc.Tooltip('Toggle power unit', target="power-unit-toggle"),
                dbc.Tooltip('Show watts/kg', target="weight-icon"),

            ]),
        ]),

        html.Div(id='power-curve-and-zone', className='row mt-2 mb-2',
                 children=[
                     html.Div(className='col-lg-6', children=[
                         dbc.Card(children=[
                             dbc.CardHeader(id='power-curve-kpis'),
                             dbc.CardBody(
                                 dcc.Graph(id='power-curve-chart', config={'displayModeBar': False},
                                           style={'height': '100%'}))
                         ]),
                     ]),
                     html.Div(className='col-lg-6', children=[
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
                 className='row text-center mt-2 mb-2', children=[
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
