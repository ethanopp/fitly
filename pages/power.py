import pandas as pd
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
import dash_daq as daq
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from lib.sqlalchemy_declarative import db_connect, stravaSummary, stravaSamples, stravaBestSamples, athlete
from dash_app import dash_app
from datetime import datetime, timedelta
import operator
import configparser
from sqlalchemy import or_, func
import math

# pre_style = {"backgroundColor": "#ddd", "fontSize": 20, "padding": "10px", "margin": "10px"}
hidden_style = {"display": "none"}
hidden_inputs = html.Div(id="hidden-inputs", style=hidden_style, children=[])

config = configparser.ConfigParser()
config.read('./config.ini')

white = config.get('oura', 'white')
teal = config.get('oura', 'teal')
light_blue = config.get('oura', 'light_blue')
dark_blue = config.get('oura', 'dark_blue')
orange = config.get('oura', 'orange')
ftp_color = 'rgb(100, 217, 236)'


def create_power_curve_kpis(interval, all, L90D, l6w, last, pr):
    return (
        ### Interval KPI ###
        html.Div(className='twelve columns', children=[
            html.H6('Power Curve {}'.format(timedelta(seconds=interval)),
                    style={'display': 'inline-block', 'color': 'rgba(220, 220, 220, 1)', 'marginTop': '0',
                           'marginBottom': '0'}),
        ]),
        ### All KPI ###
        html.Div(id='all-kpi', className='three columns nospace', children=[
            html.H6('All Time {}'.format(all),
                    style={'display': 'inline-block',  # 'fontWeight': 'bold',
                           'color': white, 'backgroundColor': dark_blue, 'marginTop': '0', 'marginBottom': '0',
                           'borderRadius': '.3rem'}),
        ]),

        ### L90D KPI ###
        html.Div(id='L90D-kpi', className='three columns', children=[
            html.H6('L90D {}'.format(L90D if pr == '' else pr),
                    style={'display': 'inline-block',  # 'fontWeight': 'bold',
                           'color': white, 'backgroundColor': light_blue if pr == '' else orange, 'marginTop': '0',
                           'marginBottom': '0',
                           'borderRadius': '.3rem'}),
        ]),

        ### L6W KPI ###
        html.Div(id='l6w-kpi', className='three columns', children=[
            html.H6('L6W {}'.format(l6w),
                    style={'display': 'inline-block',  # 'fontWeight': 'bold',
                           'color': 'rgb(46,46,46)', 'backgroundColor': white, 'marginTop': '0',
                           'marginBottom': '0',
                           'borderRadius': '.3rem'}),
        ]),

        ### Last KPI ###
        html.Div(id='last-kpi', className='three columns', children=[
            html.H6('Workout {}'.format(last),
                    style={'display': 'inline-block',  # 'fontWeight': 'bold',
                           'color': 'rgb(46,46,46)', 'backgroundColor': teal, 'marginTop': '0', 'marginBottom': '0',
                           'borderRadius': '.3rem'}),
        ]),
    )


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

    return [html.H6(datetime.strftime(df_samples['date'][0], "%A %b %d, %Y"), style={'height': '50%'},
                    className='twelve columns nospace'),
            html.H6(df_samples['act_name'][0], style={'height': '50%'}, className='twelve columns nospace')]


def power_profiles(activity_type='ride', power_unit='mmp', group='month'):
    activity_type = '%' + activity_type + '%'
    session, engine = db_connect()
    # Filter only 5 sec, 1 min, 5 min and 20 min
    df_best_samples = pd.read_sql(
        sql=session.query(stravaBestSamples).filter(stravaBestSamples.type.ilike(activity_type),
                                                    or_(stravaBestSamples.interval == 5,
                                                        stravaBestSamples.interval == 60,
                                                        stravaBestSamples.interval == 300,
                                                        stravaBestSamples.interval == 1200,
                                                        )).statement, con=engine,
        index_col=['timestamp_local'])
    engine.dispose()
    session.close()

    if len(df_best_samples) < 1:
        return html.Div(className='twelve columns maincontainer', children=[
            html.H6('No {} workouts with power data found'.format(activity_type))
        ])

    pp_date_dict = {'day': 'D', 'week': 'W', 'month': 'M', 'year': 'Y'}

    # Create columns for x-axis
    df_best_samples['power_profile_dategroup'] = df_best_samples.index.to_period(pp_date_dict[group]).to_timestamp()
    pp_title = {5: '5 Second Max Power',
                60: '1 Minute Max Power',
                300: '5 Minute Max Power',
                1200: '20 Minute Max Power'}

    profile_charts = []
    for i in pp_title.keys():
        df = df_best_samples[['activity_id', power_unit, 'power_profile_dategroup', 'interval']]
        df = df[df['interval'] == i]
        df = df.loc[df.groupby('power_profile_dategroup')[power_unit].idxmax()]
        profile_charts.append(
            html.Div(id='power-profile-' + str(i), className='three columns maincontainer height-100', children=[
                html.H6(pp_title[i], className='nospace', style={'height': '10%'}),
                dcc.Graph(
                    id='power-profile-' + str(i) + '-chart',
                    style={'height': '90%'},
                    # Hide floating toolbar
                    config={
                        'displayModeBar': False
                    },
                    figure={
                        'data': [
                            go.Bar(
                                x=df['power_profile_dategroup'],
                                y=df[power_unit],
                                customdata=[
                                    '{}_{}_{}'.format(df.loc[x]['activity_id'], df.loc[x]['interval'].astype('int'),
                                                      i) for x in df.index],
                                # add fields to text so data can go through clickData
                                text=['{:.1f} W/kg'.format(x) if power_unit == 'watts_per_kg' else '{:.0f} W'.format(x)
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
                            # title=pp_title[i],
                            plot_bgcolor='rgb(66, 66, 66)',  # plot bg color
                            paper_bgcolor='rgb(66, 66, 66)',  # margin bg color
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
                            # margin={'l': 40, 'b': 25, 't': 5, 'r': 40},
                            margin={'l': 25, 'b': 25, 't': 5, 'r': 20},

                        )
                    }
                )
            ])
        )

    return html.Div(style={'height': '100%', 'backgroundColor': 'rgb(48,48,48)'}, children=profile_charts)


def power_curve(activity_type='ride', power_unit='mmp', last_id=None, showlegend=False,
                chart_id='power-curve-chart'):
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

    all_best_interval_df = pd.read_sql(
        sql=session.query(
            func.max(stravaBestSamples.mmp).label('mmp'),
            stravaBestSamples.activity_id, stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type)).statement,
        con=engine, index_col='interval')

    L90D_best_interval_df = pd.read_sql(
        sql=session.query(
            func.max(stravaBestSamples.mmp).label('mmp'), stravaBestSamples.activity_id,
            stravaBestSamples.interval, stravaBestSamples.time_interval,
            stravaBestSamples.date, stravaBestSamples.timestamp_local, stravaBestSamples.watts_per_kg,
        ).group_by(stravaBestSamples.interval).filter(stravaBestSamples.interval.in_(interval_lengths),
                                                      stravaBestSamples.type.ilike(activity_type),
                                                      stravaBestSamples.timestamp_local >= (
                                                              datetime.now() - timedelta(days=90))
                                                      ).statement, con=engine, index_col='interval')

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

    first_workout_date = session.query(func.min(stravaSummary.start_date_utc)).first()[0]

    engine.dispose()
    session.close()

    if len(all_best_interval_df) < 1:
        return html.Div(className='twelve columns maincontainer', children=[
            html.H6('No {} workouts with power data found'.format(activity_type))
        ])

    # Make 2nd line for L6W pr and highlight orange and remove points from L6W df to avoid duplicate tooltips
    pr_df = L90D_best_interval_df.copy()
    # If less than 90 days of data, everything is a PR

    if first_workout_date < (datetime.now() - timedelta(days=90)):
        for i in pr_df.index:
            if pr_df.at[i, power_unit] == all_best_interval_df.at[i, power_unit]:
                L90D_best_interval_df.at[i, power_unit] = None
            else:
                pr_df.at[i, power_unit] = None

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
    tooltip = '''Interval: {:%H:%M:%S} - {:%H:%M:%S}<br>Best: {:%Y-%m-%d}<br>{}: {:.1f} W/kg''' if power_unit == 'watts_per_kg' else '''Interval: {:%H:%M:%S} - {:%H:%M:%S}<br>Best: {:%Y-%m-%d}<br>{}: {:.0f} W'''
    data = [
        go.Scatter(
            name='All',
            x=all_best_interval_df.index,
            y=all_best_interval_df[power_unit],
            mode='lines',
            text=[
                tooltip.format(
                    pd.to_datetime(all_best_interval_df.loc[i]['time_interval']) - timedelta(
                        seconds=i),
                    pd.to_datetime(all_best_interval_df.loc[i]['time_interval']),
                    pd.to_datetime(all_best_interval_df.loc[i]['timestamp_local']), 'Power',
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
                    pd.to_datetime(L90D_best_interval_df.loc[i]['time_interval']) - timedelta(
                        seconds=i),
                    pd.to_datetime(L90D_best_interval_df.loc[i]['time_interval']),
                    pd.to_datetime(L90D_best_interval_df.loc[i]['timestamp_local']), 'Power',
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
                    pd.to_datetime(L6W_best_interval_df.loc[i]['time_interval']) - timedelta(
                        seconds=i),
                    pd.to_datetime(L6W_best_interval_df.loc[i]['time_interval']),
                    pd.to_datetime(L6W_best_interval_df.loc[i]['timestamp_local']), 'Power',
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
                    pd.to_datetime(recent_best_interval_df.loc[i]['time_interval']) - timedelta(
                        seconds=i),
                    pd.to_datetime(recent_best_interval_df.loc[i]['time_interval']),
                    pd.to_datetime(recent_best_interval_df.loc[i]['timestamp_local']), 'Power',
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
                    pd.to_datetime(pr_df.loc[i]['time_interval']) - timedelta(
                        seconds=i),
                    pd.to_datetime(pr_df.loc[i]['time_interval']),
                    pd.to_datetime(pr_df.loc[i]['timestamp_local']), 'Power',
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
    return dcc.Graph(id=chart_id, style={'height': '100%'},
                     config={
                         'displayModeBar': False
                     },
                     hoverData=hoverData,
                     figure={
                         'data': data,
                         'layout': go.Layout(
                             plot_bgcolor='rgb(66, 66, 66)',  # plot bg color
                             paper_bgcolor='rgb(66, 66, 66)',  # margin bg color
                             font=dict(
                                 color='rgb(220,220,220)'
                             ),
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

                     })


def create_ftp_chart(activity_type='ride', power_unit='watts'):
    activity_type = '%' + activity_type + '%'
    session, engine = db_connect()
    df_ftp = pd.read_sql(
        sql=session.query(stravaSummary).filter(stravaSummary.type.ilike(activity_type)).statement, con=engine,
        index_col='start_day_local')[
        ['activity_id', 'ftp', 'weight']]
    engine.dispose()
    session.close()

    # Filter summary table on activities that have a different FTP from the previous activity
    df_ftp['previous_ftp'] = df_ftp['ftp'].shift(1)
    df_ftp = df_ftp[df_ftp['previous_ftp'] != df_ftp['ftp']]

    df_ftp['watts_per_kg'] = df_ftp['ftp'] / (df_ftp['weight'] / 2.20462)
    metric = 'ftp' if power_unit == 'ftp' else 'watts_per_kg'
    tooltip = '<b>{:.0f} W {}' if metric == 'ftp' else '<b>{:.1f} W/kg {}'
    title = 'Current FTP {:.0f} W' if metric == 'ftp' else 'Current FTP {:.1f} W/kg'

    if len(df_ftp) < 1:
        return html.Div(className='twelve columns maincontainer', children=[
            html.H6('No {} FTP tests found'.format(activity_type))
        ])

    df_ftp['ftp_%'] = ['{}{:.0f}%'.format('+' if x > 0 else '', x) if x != 0 else '' for x in
                       (((df_ftp[metric] - df_ftp[metric].shift(1)) / df_ftp[metric].shift(1)) * 100).fillna(0)]

    df_ftp_tooltip = [tooltip.format(x, y) for x, y in
                      zip(df_ftp[metric], df_ftp['ftp_%'])]

    df_ftp = df_ftp.reset_index()

    ftp_header = [
        html.H6(id='ftp-title', children=[title.format(df_ftp.loc[df_ftp.index.max()][metric])],
                style={'display': 'inline-block',  # 'fontWeight': 'bold',
                       'color': white, 'marginTop': '0', 'marginBottom': '0', 'marginRight': '1%'}),

        dbc.Tooltip(
            'Functional Threshold Power (FTP) is the highest average power you can sustain for 1 hour, measured in watts. FTP is used to determine training zones when using a power meter and to measure improvement.',
            target="ftp-title", className='tooltip'),
    ]
    ftp_chart = [
        dcc.Graph(style={'paddingLeft': '0', 'paddingRight': '0', 'height': '100%', 'border': '0px'},
                  config={
                      'displayModeBar': False,
                  },
                  figure={
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
                          plot_bgcolor='rgb(66, 66, 66)',  # plot bg color
                          paper_bgcolor='rgb(66, 66, 66)',  # margin bg color
                          font=dict(
                              color='rgb(220,220,220)'
                          ),
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
                  )
    ]

    return html.Div(id='ftp-kpis-and-charts', style={'height': '100%'}, children=[

        ## Cycle FTP
        html.Div(className='twelve columns height-15', children=ftp_header),
        html.Div(className='twelve columns height-85', children=ftp_chart),

    ])


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
                plot_bgcolor='rgb(66, 66, 66)',  # plot bg color
                paper_bgcolor='rgb(66, 66, 66)',  # margin bg color
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


@dash_app.callback(
    Output('power-curve', 'children'),
    [Input('power-dashboard', 'children'),
     Input('activity-type-toggle', 'value'),
     Input('power-unit-toggle', 'value')]
)
def update_power_curve(dummy, activity_type, power_unit):
    power_unit = 'watts_per_kg' if power_unit else 'mmp'
    activity_type = 'run' if activity_type else 'ride'
    return power_curve(activity_type, power_unit)


# # Callbacks to figure out which is the latest chart that was clicked
# @dash_app.callback(
#     Output('power-curve-chart-timestamp', 'children'),
#     [Input('power-curve-chart', 'clickData')])
# def power_curve_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @dash_app.callback(
#     Output('power-profile-5-chart-timestamp', 'children'),
#     [Input('power-profile-5-chart', 'clickData')])
# def power_profile_5_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @dash_app.callback(
#     Output('power-profile-60-chart-timestamp', 'children'),
#     [Input('power-profile-60-chart', 'clickData')])
# def power_profile_60_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @dash_app.callback(
#     Output('power-profile-300-chart-timestamp', 'children'),
#     [Input('power-profile-300-chart', 'clickData')])
# def power_profile_300_chart_timestamp(dummy):
#     return datetime.utcnow()
#
#
# @dash_app.callback(
#     Output('power-profile-1200-chart-timestamp', 'children'),
#     [Input('power-profile-1200-chart', 'clickData')])
# def power_profile_1200_chart_timestamp(dummy):
#     return datetime.utcnow()


# # Store last clicked data into div for consumption by action callbacks
# @dash_app.callback(
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
# @dash_app.callback(
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
# @dash_app.callback(
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
# @dash_app.callback(
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
@dash_app.callback(
    [Output('bicycle-icon', 'style'),
     Output('running-icon', 'style')],
    [Input('activity-type-toggle', 'value')]
)
def update_icon(value):
    if value:
        return {'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': white}, {
            'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}
    else:
        return {'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}, {
            'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': white}


@dash_app.callback(
    [Output('bolt-icon', 'style'),
     Output('weight-icon', 'style')],
    [Input('power-unit-toggle', 'value')]
)
def update_icon(value):
    if value:
        return {'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': white}, {
            'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}
    else:
        return {'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}, {
            'fontSize': '2.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': white}


# FTP Chart
@dash_app.callback(
    Output('ftp', 'children'),
    [Input('power-curve-and-zone', 'children'),
     Input('activity-type-toggle', 'value'),
     Input('power-unit-toggle', 'value')]
)
def ftp_chart(dummy, activity_type, power_unit):
    power_unit = 'watts_per_kg' if power_unit else 'ftp'
    activity_type = 'run' if activity_type else 'ride'
    return create_ftp_chart(activity_type=activity_type, power_unit=power_unit)


# Group power profiles
@dash_app.callback([Output('power-profiles', 'children'),
                    Output('day-button', 'style'),
                    Output('week-button', 'style'),
                    Output('month-button', 'style'),
                    Output('year-button', 'style'), ],
                   [Input('power-dashboard', 'children'),
                    Input('activity-type-toggle', 'value'),
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
def update_power_profiles(dummy, activity_type, power_unit, day_n_clicks, week_n_clicks, month_n_clicks, year_n_clicks,
                          day_n_clicks_timestamp, week_n_clicks_timestamp, month_n_clicks_timestamp,
                          year_n_clicks_timestamp):
    latest = 'month'
    power_unit = 'watts_per_kg' if power_unit else 'mmp'
    activity_type = 'run' if activity_type else 'ride'

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

    return power_profiles(group=latest, power_unit=power_unit,
                          activity_type=activity_type), day_style, week_style, month_style, year_style


# # Main Dashboard Generation Callback
# @dash_app.callback(
#     Output('power-layout', 'children'),
#     [Input('activity-type-toggle', 'value'),
#      Input('power-unit-toggle', 'value')],
# )
# def performance_dashboard(dummy, activity_type, power_unit):
#     return generate_power_dashboard()


@dash_app.callback(
    Output('power-curve-kpis', 'children'),
    [Input('power-curve-chart', 'hoverData')],
    [State('power-unit-toggle', 'value')])
def update_fitness_kpis(hoverData, power_unit):
    at, L90D, l6w, last, pr = '', '', '', '', ''
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


layout = html.Div(id='power-canvas', children=[
    html.Div(id='power-dashboard', children=[

        html.Div(id='power-dashboard-header-container',
                 className='twelve columns nospace maincontainer', children=[

                html.Div(className='twelve columns', children=[

                    html.I(id='bicycle-icon', className='fa fa-bicycle',
                           style={'fontSize': '2.5rem', 'display': 'inline-block',
                                  'vertical-align': 'middle', 'color': teal}),
                    daq.ToggleSwitch(id='activity-type-toggle', style={'display': 'inline-block'}),
                    html.I(id='running-icon', className='fa fa-running',
                           style={'fontSize': '2.5rem', 'display': 'inline-block',
                                  'vertical-align': 'middle'}),

                    # dbc.Tooltip('Analyze cycling activities',
                    #             target="bicycle-icon", className='tooltip'),
                    # dbc.Tooltip('Analyze running activities',
                    #             target="running-icon", className='tooltip'),

                    html.I(style={'fontSize': '2.5rem', 'display': 'inline-block', 'paddingLeft': '1%',
                                  'paddingRight': '1%'}),

                    html.I(id='bolt-icon', className='fa fa-bolt',
                           style={'fontSize': '2.5rem', 'display': 'inline-block',
                                  'vertical-align': 'middle', 'color': teal}),
                    daq.ToggleSwitch(id='power-unit-toggle', style={'display': 'inline-block'}, value=True),
                    html.I(id='weight-icon', className='fa fa-weight',
                           style={'fontSize': '2.5rem', 'display': 'inline-block',
                                  'vertical-align': 'middle'}),

                    # dbc.Tooltip('Show watts',
                    #             target="bolt-icon", className='tooltip'),
                    # dbc.Tooltip('Show watts/kg',
                    #             target="weight-icon", className='tooltip'),
                ]),

            ]),
        html.Div(className='twelve columns', style={'backgroundColor': 'rgb(48, 48, 48)', 'paddingBottom': '1vh'}),

        html.Div(id='power-curve-and-zone', className='twelve columns',
                 children=[
                     html.Div(className='six columns maincontainer height-100', children=[

                         html.Div(style={'height': '100%'}, children=[
                             html.Div(id='power-curve-kpis', className='twelve columns nospace',
                                      style={'height': '15%'}),

                             # TODO: Add dcc.Loading() for power curve once able to not have it load on hoverData per
                             # https://github.com/plotly/dash/issues/951
                             html.Div(id='power-curve', className='twelve columns', style={'height': '85%'})
                         ]),

                     ]),

                     html.Div(className='six columns maincontainer height-100', children=[
                         # dcc.Loading(className='twelve columns height-15', children=[
                         #     html.Div(id='workout-title', style={'height': '100%'},
                         #              children=get_workout_title(activity_id=latest_activity_id))]
                         #             ),
                         # dcc.Loading(id='workout-trend-container', className='six columns nospace height-100',
                         #             children=[
                         #                 html.Div(id='workout-trends', className='height-100',
                         #                          children=[workout_details(activity_id=latest_activity_id)])]
                         #             ),
                         dcc.Loading(id='ftp', className='twelve columns height-100'),
                         # dcc.Loading(id='power-zone', className='six columns height-100', children=zone_chart()),
                     ])
                 ]),
        html.Div(className='twelve columns', style={'backgroundColor': 'rgb(48, 48, 48)', 'paddingBottom': '1vh'}),
        html.Div(id='power-profile-header',
                 className='twelve columns nospace', children=[

                html.H6(style={'display': 'inline-block', 'textAlign': 'center', 'verticalAlign': 'middle'},
                        children=['Power Profiles by']),
                html.Div(className='nospace',
                         style={'display': 'inline-block', 'textAlign': 'left', 'verticalAlign': 'middle',
                                'paddingLeft': '.5vw'}, children=[
                        html.Div(id='power-profile-buttons', className='twelve columns nospace', children=[
                            html.Button('Day', id='day-button', style={'marginRight': '1vw'}),
                            html.Button('Week', id='week-button', style={'marginRight': '1vw'}),
                            html.Button('Month', id='month-button', style={'marginRight': '1vw'}),
                            html.Button('Year', id='year-button'),
                        ]),
                    ])
            ]),
        html.Div(className='twelve columns', style={'backgroundColor': 'rgb(48, 48, 48)', 'paddingBottom': '1vh'}),
        dcc.Loading(
            html.Div(id='power-profiles', className='twelve columns')
        ),

        # html.Div(id='last-clicked', style={'display': 'none'}),
        # html.Div(id='power-curve-chart-timestamp', style={'display': 'none'}, children=datetime.utcnow()),
        # html.Div(id='power-profile-5-chart-timestamp', style={'display': 'none'}, children=datetime.utcnow()),
        # html.Div(id='power-profile-60-chart-timestamp', style={'display': 'none'}, children=datetime.utcnow()),
        # html.Div(id='power-profile-300-chart-timestamp', style={'display': 'none'}, children=datetime.utcnow()),
        # html.Div(id='power-profile-1200-chart-timestamp', style={'display': 'none'}, children=datetime.utcnow()),

    ])
])
