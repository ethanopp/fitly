import pandas as pd
import numpy as np
import dash
import dash_table
import dash_core_components as dcc
import dash_html_components as html
import plotly.figure_factory as ff
import plotly.graph_objs as go
from ..app import app
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from sqlalchemy import func
from datetime import datetime, timedelta
from ..api.sqlalchemy_declarative import ouraReadinessSummary, ouraActivitySummary, \
    ouraActivitySamples, ouraSleepSamples, ouraSleepSummary, stravaSummary, athlete, withings
from ..api.ouraAPI import top_n_correlations
from ..api.database import engine
from ..utils import calc_next_saturday, calc_prev_sunday, utc_to_local, config, oura_credentials_supplied, \
    withings_credentials_supplied

transition = int(config.get('dashboard', 'transition'))
default_icon_color = 'rgb(220, 220, 220)'
white = config.get('oura', 'white')
teal = config.get('oura', 'teal')
light_blue = config.get('oura', 'light_blue')
dark_blue = config.get('oura', 'dark_blue')
orange = config.get('oura', 'orange')
grey = 'rgb(50,50,50)'
chartHeight = 150


def generate_correlation_table(n, metric, lookback_days=180):
    df = top_n_correlations(n, metric, lookback_days)
    df['Pos Corr Coef.'] = df['Pos Corr Coef.'].map('{:,.3f}'.format)
    df['Neg Corr Coef.'] = df['Neg Corr Coef.'].map('{:,.3f}'.format)
    return dash_table.DataTable(
        id=metric + '-correlation-table',
        columns=[{"name": i, "id": i} for i in df.columns],
        data=df.to_dict('records'),
        style_as_list_view=True,
        fixed_rows={'headers': True, 'data': 0},
        style_header={
            'backgroundColor': 'rgba(66, 66, 66, 0)',
            'borderBottom': '1px solid rgb(220, 220, 220)',
            'borderTop': '0px',
            'textAlign': 'center',
            'fontSize': 12,
            'fontWeight': 'bold',
            'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
        },
        style_cell={
            'backgroundColor': 'rgba(66, 66, 66, 0)',
            'color': 'rgb(220, 220, 220)',
            'borderBottom': '1px solid rgb(73, 73, 73)',
            'textOverflow': 'ellipsis',
            'fontSize': 12,
            'maxWidth': 30,
            'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
        },
        style_cell_conditional=[
            {
                'if': {'column_id': c},
                'textAlign': 'center'
            } for c in df.columns
        ],

        page_action="none",
    )


def modal_range_buttons(df, resample='D'):
    weekday = 35 + 7 + (calc_prev_sunday(df.index.max()) - df.index.max().date()).days
    # yearday = df.index.max().timetuple().tm_yday
    if resample == 'D':
        tickformat = '%b %d'
        buttons = list([
            # Specify row count to get rid of auto x-axis padding when using scatter markers
            dict(count=weekday,
                 label='L6W',
                 step='day',
                 stepmode='backward'),
            dict(count=30,
                 label='L30D',
                 step='day',
                 stepmode='backward'),
            dict(count=7,
                 label='L7D',
                 step='day',
                 stepmode='backward')
        ])
        range = [df.index.max() - timedelta(days=30),
                 df.index.max()]

    elif resample == 'W':
        tickformat = '%b %d'
        buttons = list([
            dict(label='ALL',
                 step='all'),
            dict(count=1,
                 label='YTD',
                 step='year',
                 stepmode='todate'),
            dict(count=weekday,
                 label='L6W',
                 step='day',
                 stepmode='backward')
        ])
        range = [pd.to_datetime('01-01-{}'.format(df.index.max().year)),
                 df.index.max()]
    elif resample == 'M':
        tickformat = '%b %Y'
        buttons = list([
            dict(label='ALL',
                 step='all'),
            dict(count=1,
                 label='YTD',
                 step='year',
                 stepmode='todate'),
            dict(count=6,
                 label='L6M',
                 step='month',
                 stepmode='backward')
        ])
        range = [pd.to_datetime('01-01-{}'.format(df.index.max().year)),
                 df.index.max()]
    elif resample == 'Y':
        tickformat = '%Y'
        buttons = []
        range = None

    return buttons, range, tickformat


def get_max_week_ending():
    date = app.session.query(func.max(ouraSleepSummary.report_date))[0][0]

    app.session.remove()
    return pd.to_datetime(date)


# TODO: Fix y axis sort
def generate_sleep_stages_chart(date):
    df = pd.read_sql(
        sql=app.session.query(ouraSleepSamples).filter(
            ouraSleepSamples.report_date == date, ouraSleepSamples.hypnogram_5min_desc != None).statement, con=engine,
        index_col='timestamp_local').sort_index(
        ascending=False)

    app.session.remove()

    df['Task'] = df['hypnogram_5min_desc']
    df['Start'] = df.index
    df['Finish'] = df['Start'].shift(1) - timedelta(seconds=1)
    df['Resource'] = df['hypnogram_5min']

    # Remove last item that doesnt have a Finish
    df = df[df['Finish'].notnull()]

    df = df.drop(
        columns=['summary_date', 'report_date', 'rmssd_5min', 'hr_5min', 'hypnogram_5min', 'hypnogram_5min_desc'])

    colors = {4: white, 2: light_blue, 1: dark_blue, 3: teal}

    fig = ff.create_gantt(df, colors=colors, index_col='Resource', bar_width=.5,
                          show_colorbar=False, showgrid_x=False, showgrid_y=False, group_tasks=True)

    # Set layout
    fig['layout'].update(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        height=150,
        xaxis={'showgrid': False,
               'zeroline': False,
               'showline': True,
               'showticklabels': True,
               'tickformat': '%I:%M %p',
               'range': [df.index.min(), df.index.max()],
               'color': white,
               'type': 'date',
               'rangeselector': None,
               },
        yaxis={'autorange': False,
               'range': [-1, 5],
               'showgrid': False,
               # 'ticktext': ['Deep ', 'Light ', 'REM ', 'Awake '],
               'tickvals': [0, 1, 2, 3],
               # 'showticklabels':False,
               'zeroline': False},
        # 'categoryarray': [1, 2, 3, 4]},
        margin={'l': 40, 'b': 30, 't': 0, 'r': 40},
        font={'color': white, 'size': 10},
        hovermode='x'
    )

    # Update tooltips
    for i in range(len(fig["data"])):
        chunk = fig["data"][i]
        if chunk['legendgroup'] == white:
            text = 'Awake'
        elif chunk['legendgroup'] == light_blue:
            text = 'Light'
        elif chunk['legendgroup'] == teal:
            text = 'REM'
        elif chunk['legendgroup'] == dark_blue:
            text = 'Deep'
        fig["data"][i].update(hoverinfo="text+x", text=text)

    return dcc.Graph(id='gantt', style={'height': '100%'}, figure=fig, config={'displayModeBar': False})


def daily_movement_color(x, name=False):
    if x <= 1:
        if name:
            return 'Inactive'
        else:
            return grey
    elif x <= 3:
        if name:
            return 'Low'
        else:
            return light_blue
    elif x <= 7:
        if name:
            return 'Medium'
        else:
            return teal
    else:
        if name:
            return 'High'
        else:
            return white


def generate_daily_movement_chart(date):
    df = pd.read_sql(
        sql=app.session.query(ouraActivitySamples.timestamp_local, ouraActivitySamples.met_1min,
                              ouraActivitySamples.class_5min).filter(
            ouraActivitySamples.summary_date == date, ouraActivitySamples.class_5min != None).statement, con=engine,
        index_col='timestamp_local')

    app.session.remove()

    df['color'] = df['met_1min'].apply(daily_movement_color)
    df['action'] = df['met_1min'].apply(lambda x: daily_movement_color(x, name=True))

    df['movement_tooltip'] = ['<b>{}:</b> {} MET'.format(x, y) for (x, y) in zip(df['action'], df['met_1min'])]

    return dcc.Graph(id='daily-movement-chart', className='col-lg-12',
                     config={'displayModeBar': False},
                     figure={
                         'data': [
                             go.Bar(
                                 x=df.index,
                                 y=df['met_1min'],
                                 text=df['movement_tooltip'],
                                 hoverinfo='text+x',
                                 marker={'color': df['color'].tolist()},
                             ),
                             go.Scatter(
                                 name='Low',
                                 x=df.index,
                                 y=[1 for x in df.index],
                                 mode='lines',
                                 hoverinfo='x',
                                 line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': .5},
                                 showlegend=False,
                             ),
                             go.Scatter(
                                 name='Med',
                                 x=df.index,
                                 y=[3 for x in df.index],
                                 mode='lines',
                                 hoverinfo='x',
                                 line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': .5},
                                 showlegend=False,
                             ),
                             go.Scatter(
                                 name='High',
                                 x=df.index,
                                 y=[7 for x in df.index],
                                 mode='lines',
                                 hoverinfo='x',
                                 line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': .5},
                                 showlegend=False,
                             ),
                         ],
                         'layout': go.Layout(
                             height=150,
                             transition=dict(duration=transition),
                             font=dict(
                                 size=10,
                                 color=white
                             ),
                             xaxis=dict(
                                 showticklabels=True,
                                 # tickvals=[x for x in df.index if
                                 #           x.minute == 0 and x.hour in [0, 8, 12, 16, 20]],
                                 tickformat='%I:%M %p',
                                 showgrid=False,
                                 showline=True,
                                 color=white
                             ),
                             yaxis=dict(
                                 showticklabels=True,
                                 range=[0, df['met_1min'].max() if df['met_1min'].max() > 7 else 8],
                                 tickvals=[1, 3, 7],
                                 ticktext=['Low ', 'Med ', 'High '],
                                 showgrid=True,

                             ),
                             showlegend=False,
                             margin={'l': 40, 'b': 30, 't': 0, 'r': 40},
                             hovermode='x'
                         )
                     }
                     )


def generate_rhr_day_chart(date):
    df = pd.read_sql(
        sql=app.session.query(ouraSleepSamples.timestamp_local, ouraSleepSamples.hr_5min).filter(
            ouraSleepSamples.report_date == date).statement, con=engine, index_col='timestamp_local')

    if len(df) == 0:
        date = app.session.query(func.max(ouraSleepSamples.report_date)).first()[0]
        df = pd.read_sql(
            sql=app.session.query(ouraSleepSamples.timestamp_local, ouraSleepSamples.hr_5min).filter(
                ouraSleepSamples.report_date == date).statement, con=engine, index_col='timestamp_local')

    app.session.remove()

    # Remove 0s from plotted line
    # df['hr_5min'] = df['hr_5min'].replace({0: np.nan})
    df = df[df['hr_5min'] != 0]

    # Take average including all data
    df['rhr_avg'] = round(df['hr_5min'].mean())

    return dcc.Graph(id='rhr-trend', config={'displayModeBar': False},
                     figure={
                         'data': [
                             go.Scatter(
                                 x=df.index,
                                 y=df['hr_5min'],
                                 mode='lines',
                                 text=['{:.0f} bpm'.format(x) for x in df['hr_5min']],
                                 hoverinfo='text+x',
                                 opacity=0.7,
                                 line={'shape': 'spline', 'color': teal},
                                 connectgaps=True
                             ),
                             go.Scatter(
                                 x=df.index,
                                 y=df['rhr_avg'],
                                 mode='lines',
                                 text=[
                                     '<b>{} Avg: </b>{:.0f} bpm'.format(datetime.strftime(df.index.date.min(), '%b %d'),
                                                                        x) for x in
                                     df['rhr_avg']],
                                 hoverinfo='text+x',
                                 opacity=0.7,
                                 line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': 2},
                                 connectgaps=True
                             ),

                         ],
                         'layout': go.Layout(
                             height=150,
                             transition=dict(duration=transition),
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
                                 tickformat='%I:%M %p',
                                 # Specify range to get rid of auto x-axis padding when using scatter markers
                                 # range=[df.index.min(), df.index.max()]
                             ),
                             yaxis=dict(
                                 showgrid=False,
                                 showticklabels=True,
                                 gridcolor='rgb(73, 73, 73)',
                                 # gridwidth=.5,

                             ),
                             margin={'l': 40, 'b': 30, 't': 5, 'r': 40},
                             showlegend=False,
                             annotations=[
                                 go.layout.Annotation(
                                     font={'size': 12},
                                     x=df['hr_5min'].idxmin(),
                                     y=df.loc[df['hr_5min'].idxmin()]['hr_5min'],
                                     xref="x",
                                     yref="y",
                                     text="{:.0f}".format(df.loc[df['hr_5min'].idxmin()]['hr_5min']),
                                     showarrow=True,
                                     arrowhead=0,
                                     arrowcolor=white,
                                     ax=5,
                                     ay=-20
                                 )
                             ],
                             hovermode='x',
                             autosize=True,
                         )
                     })


def generate_kpi_donut(kpi_name, metric, goal, current_streak, best_streak, color=None, streak_unit=''):
    is_best_streak = current_streak >= best_streak > 0
    if metric:
        if metric > goal:
            progress = 1
        else:
            progress = metric / goal
    else:
        progress = 0

    # Update for when no goal but metric
    remaining = 1 - progress if progress > 0 else 1
    if not color:
        color = teal if progress >= 1 else white
    return [html.H6(className='mb-2', children=['{}'.format(kpi_name)]),
            dcc.Graph(id=kpi_name + '-donut-chart',
                      config={
                          'displayModeBar': False,
                      },
                      figure={
                          'data': [
                              go.Pie(
                                  name=kpi_name,
                                  sort=False,
                                  values=[progress, remaining],
                                  hole=.8,
                                  hoverinfo='none',
                                  textinfo='none',
                                  marker=dict(colors=[color, 'rgb(48, 48, 48)'])),

                          ],
                          'layout': go.Layout(
                              height=chartHeight,
                              transition=dict(duration=transition),
                              showlegend=False,
                              autosize=True,
                              margin={'l': 0, 'b': 0, 't': 0, 'r': 0},
                              annotations=[
                                  dict(
                                      font={
                                          "size": 20,
                                          "color": color
                                      },
                                      showarrow=False,
                                      text="{:.0f}".format(metric),
                                      x=0.5,
                                      y=0.85
                                  ),
                                  dict(
                                      font={
                                          "size": 14,
                                          "color": color
                                      },
                                      showarrow=False,
                                      text="of",
                                      x=0.5,
                                      y=0.5
                                  ),
                                  dict(
                                      font={
                                          "size": 20,
                                          "color": color
                                      },
                                      showarrow=False,
                                      text="{:.0f}".format(goal),
                                      x=0.5,
                                      y=0.15
                                  ),

                                  # dict(
                                  #     font={
                                  #         "size": 14,
                                  #         "color": color
                                  #     },
                                  #     showarrow=False,
                                  #     text="{:.0f} {}{}".format(current_streak, streak_unit,
                                  #                               '⋆' if is_best_streak else ''),
                                  #     x=0.5,
                                  #     y=0.10
                                  # ),
                              ]

                          )
                      }
                      ),
            dbc.Tooltip(
                'Current Streak: {:.0f} {}\nBest Streak: {:.0f} {}'.format(current_streak, streak_unit, best_streak,
                                                                           streak_unit),
                target=kpi_name + '-donut-chart', placement='bottom'),
            ]


def calculate_streak_off_oura_readiness(date, df):
    ## Workout on days when readiness >= 80

    df_readiness = pd.read_sql(
        sql=app.session.query(ouraReadinessSummary.report_date, ouraReadinessSummary.score).filter(
            ouraReadinessSummary.report_date <= date,
            ouraReadinessSummary.score >= 80).statement, con=engine)

    df_readiness = df_readiness.set_index(pd.to_datetime(df_readiness['report_date']))

    app.session.remove()

    current_streak, best_streak, temp_best_streak = 0, 0, 0
    df_readiness = df_readiness.resample('W-SAT').size()
    df = df.resample('W-SAT').size()

    # Remove weeks where readiness data is not available (data before getting ring)
    df = df[df.index >= df_readiness.index.max()]

    streak_df = pd.concat([df, df_readiness], axis=1).sort_index(ascending=False).fillna(0)
    streak_df.columns = ['metric', 'weekly_goal']

    # Calculate current streak
    for week in streak_df.index:
        metric = streak_df.loc[week]['metric']
        weekly_goal = streak_df.loc[week]['weekly_goal']
        if metric < weekly_goal:
            break
        elif metric >= weekly_goal:
            current_streak += metric

    # Calculate best streak
    for week in streak_df.index:
        metric = streak_df.loc[week]['metric']
        weekly_goal = streak_df.loc[week]['weekly_goal']
        if metric < weekly_goal:
            if temp_best_streak > best_streak:
                best_streak = temp_best_streak
            temp_best_streak = 0
        elif metric >= weekly_goal:
            temp_best_streak += metric

    try:
        current_week_goal = streak_df.loc[date]['weekly_goal']
    except:
        current_week_goal = 0

    return current_streak, best_streak, current_week_goal


def calculate_streak(date, series, weekly_goal, sum_metric=None):
    current_streak, best_streak, temp_best_streak = 0, 0, 0
    # Add current week date to df so resample always goes to current week
    if not sum_metric:
        streak_df = series.resample('W-SAT').size().sort_index(ascending=False)
    elif sum_metric:
        streak_df = series.resample('W-SAT').sum().sort_index(ascending=False)
        streak_df = streak_df[sum_metric]

    # If the max date in streak_df is more than 1 week old, no activies were done for the last week, thus the streak has been broken
    # This is required so steak does not show broken for a new week where no activities have been done yet but the goal has been met in the prior week (Streak is still alive until end of week where if weekly goal is not met, then streak is broken)
    if streak_df.index.max() < date - timedelta(days=7):
        current_streak = 0
    else:
        for i, week in streak_df.items():
            # If current week, add any workouts to current streak so far
            if i == date:
                if not sum_metric:
                    current_streak += week
            elif week < weekly_goal:
                break
            elif week >= weekly_goal:
                if sum_metric:
                    current_streak += 1
                else:
                    current_streak += week

    # Calculate best streak
    for week in streak_df:
        if week < weekly_goal:
            if temp_best_streak > best_streak:
                best_streak = temp_best_streak
            temp_best_streak = 0
        elif week >= weekly_goal:
            if sum_metric:
                temp_best_streak += 1
            else:
                temp_best_streak += week

    return current_streak, best_streak


def generate_content_kpi_trend(df_name, metric):
    rolling_days = 42

    if df_name == 'sleep':
        df = pd.read_sql(sql=app.session.query(ouraSleepSummary).statement, con=engine).set_index('report_date')
    elif df_name == 'readiness':
        df = pd.read_sql(sql=app.session.query(ouraReadinessSummary).statement, con=engine).set_index('report_date')
    elif df_name == 'activity':
        df = pd.read_sql(sql=app.session.query(ouraActivitySummary).statement, con=engine).set_index('summary_date')
    elif df_name == 'withings':
        df = pd.read_sql(sql=app.session.query(withings).statement, con=engine)
        df = df.set_index(pd.to_datetime(df['date_utc'].apply(lambda x: utc_to_local(x).date())))
        # If multiple measurements in a single day, average together to only show 1 point per day on trend
        df = df.resample('D').mean().ffill()

    app.session.remove()

    df.index = pd.DatetimeIndex(df.index)
    metricAvg = df[metric].rolling(window=rolling_days).mean()

    # Set Graph Titles
    metricTitle = {'total': 'Total Sleep Time',
                   'duration': 'Time in Bed',
                   'hr_lowest': 'Resting Heart Rate',
                   'efficiency': 'Efficiency',
                   'rmssd': 'Heart Rate Variability',
                   'temperature_delta': 'Body Temperature',
                   'breath_average': 'Respiratory Rate',
                   'cal_goal_percentage': 'Goal Progress (Cal)',
                   'cal_total': 'Total Burn (Cal)',
                   'steps': 'Steps',
                   'daily_movement': 'Walking Equivalent (mi)',
                   'weight': 'Weight: {:.0f} lbs'.format(df.loc[df.index.max()][metric]),
                   'fat_ratio': 'Body Fat: {:.0f}%'.format(df.loc[df.index.max()][metric])
                   }

    # Set tooltip formats
    if metric == 'total' or metric == 'duration':
        metricTooltip = ['{:.0f}h {:.0f}m'.format(x // 3600, (x % 3600) // 60) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f}h {:.0f}m'.format(rolling_days, x // 3600, (x % 3600) // 60) for x
                            in metricAvg]
        # Update numbers for y axis alignment
        df[metric] = df[metric] / 60 / 60
        metricAvg = metricAvg / 60 / 60

    elif metric == 'hr_lowest':
        metricTooltip = ['{:.0f} bpm'.format(x) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f} bpm'.format(rolling_days, x) for x in metricAvg]
    elif metric == 'efficiency':
        metricTooltip = ['{:.0f}%'.format(x) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f}%'.format(rolling_days, x) for x in metricAvg]
    elif metric == 'rmssd':
        metricTooltip = ['{:.0f} ms'.format(x) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f} ms'.format(rolling_days, x) for x in metricAvg]
    elif metric == 'temperature_delta':
        metricTooltip = ['{:.1f}°F'.format(x * (9 / 5)) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.1f}°F'.format(rolling_days, x * (9 / 5)) for x in metricAvg]
    elif metric == 'breath_average':
        metricTooltip = ['{:.1f}'.format(x) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.1f}'.format(rolling_days, x) for x in metricAvg]

    elif metric == 'cal_active':
        # If "goal" is selected, plot the actual % but show actual and goal numbers in tooltip
        df['cal_goal_percentage'] = df['cal_active'] / df['target_calories']
        metric = 'cal_goal_percentage'
        metricTooltip = ['{:.0f}% {:.0f} / {:.0f}'.format(x * 100, y, z) for (x, y, z) in
                         zip(df['cal_goal_percentage'], df['cal_active'], df['target_calories'])]

        df['cal_goal_percentage_avg'] = df['cal_active'].rolling(window=rolling_days).mean() / df[
            'target_calories'].rolling(window=rolling_days).mean()
        metricAvg = df['cal_goal_percentage_avg']
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f}% {:.0f} / {:.0f}'.format(rolling_days, x * 100, y, z) for
                            (x, y, z)
                            in
                            zip(df['cal_goal_percentage_avg'],
                                df['cal_active'].rolling(window=rolling_days).mean(),
                                df['target_calories'].rolling(window=rolling_days).mean())]

    elif metric == 'cal_total' or metric == 'steps':
        metricTooltip = ['{} cal'.format(x) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f}'.format(rolling_days, x) for x in metricAvg]

    elif metric == 'daily_movement':
        metricTooltip = ['{:.1f} mi'.format(x * 0.000621371) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.1f} mi'.format(rolling_days, x * 0.000621371) for x in metricAvg]

    elif metric == 'weight':
        metricTooltip = ['{:.0f} lbs'.format(x) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f} lbs'.format(rolling_days, x) for x in metricAvg]

    elif metric == 'fat_ratio':
        metricTooltip = ['{:.0f}%'.format(x) for x in df[metric]]
        metricAvgTooltip = ['<b>{} Day Avg:</b> {:.0f}%'.format(rolling_days, x) for x in metricAvg]

    if metric == 'fat_ratio' or metric == 'weight':
        buttons = list([
            dict(count=1,
                 label='YTD',
                 step='year',
                 stepmode='todate'),
            dict(count=41,
                 label='L6W',
                 step='day',
                 stepmode='backward'),
            dict(count=29,
                 label='L30D',
                 step='day',
                 stepmode='backward')
        ])
        margin = {'l': 20, 'b': 30, 't': 0, 'r': 20}
    else:
        buttons = list([
            # Specify row count to get rid of auto x-axis padding when using scatter markers
            # dict(count=(len(df) + 1),
            #      label='ALL',
            #      step='day',
            #      stepmode='backward'),
            dict(count=1,
                 label='YTD',
                 step='year',
                 stepmode='todate'),
            dict(count=41,
                 label='L6W',
                 step='day',
                 stepmode='backward'),
            dict(count=29,
                 label='L30D',
                 step='day',
                 stepmode='backward'),
            dict(count=6,
                 label='L7D',
                 step='day',
                 stepmode='backward')
        ])
        margin = {'l': 35, 'b': 30, 't': 0, 'r': 35}

    return html.Div(id=metric + '-kpi-title', className='col-lg-12', children=[
        html.H6(children=[metricTitle[metric]]),
        dcc.Graph(id=metric + '-kpi-trend', config={'displayModeBar': False},
                  figure={
                      'data': [
                          go.Scatter(
                              x=df.index,
                              y=df[metric],
                              mode='lines',
                              text=metricTooltip,
                              hoverinfo='x+text',
                              opacity=0.7,
                              line={'shape': 'spline', 'color': teal}),
                          go.Scatter(
                              x=df.index,
                              y=metricAvg,
                              mode='lines',
                              text=metricAvgTooltip,
                              hoverinfo='x+text',
                              opacity=0.7,
                              line={'dash': 'dot',
                                    'color': white,
                                    'width': 2},
                          )
                      ],
                      'layout': go.Layout(
                          height=150,
                          transition=dict(duration=transition),
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
                              range=[df.index.max() - timedelta(days=41),
                                     df.index.max()],
                              rangeselector=dict(
                                  # bgcolor='rgba(66, 66, 66)',
                                  # bordercolor='#d4d4d4',
                                  borderwidth=.5,
                                  buttons=buttons,
                                  xanchor='center',
                                  x=.5,
                                  y=1,
                              ),
                          ),
                          yaxis=dict(
                              showgrid=False,
                              showticklabels=True,
                              gridcolor='rgb(73, 73, 73)',
                              gridwidth=.5,

                          ),
                          margin=margin,
                          showlegend=False,
                          hovermode='x',
                          autosize=True,
                      )
                  })
    ])


def update_kpis(date, days=7):
    df_summary = pd.read_sql(
        sql=app.session.query(stravaSummary).filter(stravaSummary.start_date_utc <= date).statement, con=engine,
        index_col='start_date_local')
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False

    ### Oura Donuts ###

    # Count days where 85 or greater oura score achieved
    df_sleep = pd.read_sql(sql=app.session.query(ouraSleepSummary.report_date, ouraSleepSummary.score).filter(
        ouraSleepSummary.report_date <= date, ouraSleepSummary.score >= 85).statement, con=engine)
    df_sleep = df_sleep.set_index(pd.to_datetime(df_sleep['report_date']))
    df_activity = pd.read_sql(sql=app.session.query(ouraActivitySummary.summary_date, ouraActivitySummary.score).filter(
        ouraActivitySummary.summary_date <= date, ouraActivitySummary.score >= 85).statement, con=engine)
    df_activity = df_activity.set_index(pd.to_datetime(df_activity['summary_date']))
    df_readiness = pd.read_sql(
        sql=app.session.query(ouraReadinessSummary.report_date, ouraReadinessSummary.score).filter(
            ouraReadinessSummary.report_date <= date, ouraReadinessSummary.score >= 85).statement, con=engine)
    df_readiness = df_readiness.set_index(pd.to_datetime(df_readiness['report_date']))

    # Filter df date's for donuts
    df_sleep = df_sleep[(df_sleep.index.date <= pd.to_datetime(date).date()) &
                        (df_sleep.index.date > pd.to_datetime(date - timedelta(days=days)).date())]
    df_readiness = df_readiness[(df_readiness.index.date <= pd.to_datetime(date).date()) &
                                (df_readiness.index.date > pd.to_datetime(date - timedelta(days=days)).date())]
    df_activity = df_activity[(df_activity.index.date <= pd.to_datetime(date).date()) &
                              (df_activity.index.date > pd.to_datetime(date - timedelta(days=days)).date())]

    # Calculate Streaks
    current_sleep_streak, best_sleep_streak = calculate_streak(date, df_sleep, athlete_info.weekly_sleep_score_goal)
    current_readiness_streak, best_readiness_streak = calculate_streak(date, df_readiness,
                                                                       athlete_info.weekly_readiness_score_goal)
    current_activity_streak, best_activity_streak = calculate_streak(date, df_activity,
                                                                     athlete_info.weekly_activity_score_goal)

    tss_goal = True if athlete_info.weekly_workout_goal == 100 else False

    if tss_goal:
        tss_df = pd.read_sql(
            sql=app.session.query(stravaSummary.start_day_local, stravaSummary.tss, stravaSummary.hrss,
                                  stravaSummary.trimp).filter(
                stravaSummary.elapsed_time > athlete_info.min_non_warmup_workout_time).statement,
            con=engine,
            index_col='start_day_local')

        if use_power:
            tss_df['stress_score'] = tss_df.apply(lambda row: row['hrss'] if np.isnan(row['tss']) else row['tss'],
                                                  axis=1).fillna(0)
        else:
            tss_df['stress_score'] = tss_df['trimp']

        tss_df = tss_df.set_index(pd.to_datetime(tss_df.index))
        # Calculate Streaks
        tss_streak, best_tss_streak = calculate_streak(date, tss_df, athlete_info.weekly_tss_goal,
                                                       sum_metric='stress_score')

        # Filter df date's for donuts
        tss_df = tss_df[(tss_df.index.date <= pd.to_datetime(date).date()) &
                        (tss_df.index.date > pd.to_datetime(date - timedelta(days=days)).date())]

        tss_color = orange if tss_df['stress_score'].sum() < athlete_info.weekly_tss_goal else None

        class_name = 'col-lg-2'
        specific_donuts = [
            html.Div(id='tss-donut', className=class_name,
                     children=generate_kpi_donut(kpi_name='Stress',
                                                 metric=tss_df['stress_score'].sum(),
                                                 goal=athlete_info.weekly_tss_goal,
                                                 current_streak=tss_streak,
                                                 best_streak=best_tss_streak,
                                                 streak_unit='wk',
                                                 color=tss_color))
        ]

    else:
        # Count workouts that are greater than min activity minutes
        df_workout = df_summary[
            ((df_summary['type'].str.lower().str.contains("ride")) | (
                df_summary['type'].str.lower().str.contains("run")) |
             df_summary['type'].str.lower().str.contains("weight")) &
            (df_summary['elapsed_time'] >= athlete_info.min_non_warmup_workout_time)]

        # Calculate Streaks
        athlete_weekly_workout_goal = athlete_info.weekly_workout_goal
        if athlete_info.weekly_workout_goal == 99:
            current_workout_streak, best_workout_streak, athlete_weekly_workout_goal = calculate_streak_off_oura_readiness(
                date, df_workout)
        else:
            current_workout_streak, best_workout_streak = calculate_streak(date, df_workout,
                                                                           athlete_weekly_workout_goal)

        # Filter df date's for donuts
        df_workout = df_workout[(df_workout.index.date <= pd.to_datetime(date).date()) &
                                (df_workout.index.date > pd.to_datetime(date - timedelta(days=days)).date())]

        workout_color = orange if df_workout.shape[
                                      0] < athlete_weekly_workout_goal and athlete_weekly_workout_goal != 99 else None

        class_name = 'col-lg-2 '
        specific_donuts = [html.Div(id='workout-donut', className=class_name,
                                    children=generate_kpi_donut(kpi_name='Workout', metric=df_workout.shape[0],
                                                                goal=athlete_weekly_workout_goal,
                                                                current_streak=current_workout_streak,
                                                                best_streak=best_workout_streak,
                                                                color=workout_color))]

    main_donuts = [html.Div(id='sleep-donut', className=class_name,
                            children=generate_kpi_donut(kpi_name='Sleep', metric=df_sleep.shape[0],
                                                        goal=athlete_info.weekly_sleep_score_goal,
                                                        current_streak=current_sleep_streak,
                                                        best_streak=best_sleep_streak)),
                   html.Div(id='readiness-donut', className=class_name,
                            children=generate_kpi_donut(kpi_name='Readiness', metric=df_readiness.shape[0],
                                                        goal=athlete_info.weekly_readiness_score_goal,
                                                        current_streak=current_readiness_streak,
                                                        best_streak=best_readiness_streak)),
                   html.Div(id='activity-donut', className=class_name,
                            children=generate_kpi_donut(kpi_name='Activity', metric=df_activity.shape[0],
                                                        goal=athlete_info.weekly_activity_score_goal,
                                                        current_streak=current_activity_streak,
                                                        best_streak=best_activity_streak))
                   ]

    if withings_credentials_supplied:
        main_donuts.extend([
            html.Div(id='weight-trend', className=class_name,
                     children=generate_content_kpi_trend('withings', 'weight')),
            html.Div(id='body-fat-trend', className='col-lg-2',
                     children=generate_content_kpi_trend('withings', 'fat_ratio'))

        ])

    app.session.remove()

    return html.Div(className='col-lg-12', children=[
        dbc.Card([
            dbc.CardBody([
                html.Div(className='row', children=specific_donuts + main_donuts)
            ])
        ])
    ])


def generate_contributor_bar(df, id, column_name, top_left_title, top_right_title=None):
    score = df[column_name].max()
    textColor = orange if score < 70 else white
    barColor = orange if score < 70 else teal

    if not top_right_title:
        if score < 70:
            top_right_title = 'Pay Attention'
        elif score < 85:
            top_right_title = 'Good'
        else:
            top_right_title = 'Optimal'

    # Update bars for Oura Rest Mode
    if score == 0:
        top_right_title = 'Rest Mode'
        textColor = None

    tooltipDict = {
        "previous-night": "How you slept last night can have a significant impact on your readiness to perform during the day.\n\nGetting enough good quality sleep is necessary for physical recovery, memory and learning, all part of your readiness to perform.\n\nFor a maximum positive contribution to your Readiness Score, your Sleep Score needs to be above 88%, and at the high end of your normal range.",
        "sleep-balance": "Sleep Balance shows if the sleep you've been getting over the past two weeks is in balance with your needs.\n\nSleep Balance is based on a long-term view on your sleep patterns. It's measured by comparing your total sleep time from the past two weeks to your long-term sleep history and the amount of sleep recommended for your age.\n\nTypically adults need 7-9 hours of sleep to stay healthy, alert, and to perform at their best both mentally and physically. Insufficient sleep can eventually lead to sleep debt. Paying back sleep debt and rebuilding Sleep Balance takes several nights of good sleep.",
        "previous-day-activity": "Your level of physical activity yesterday is one of the key contributors to your Readiness Score.\n\nWhen Previous Day is in balance and the contributor bar is at 100%, you’ll know you’ve balanced your need for activity and rest, and substituted a nice amount of inactive time with low activity.\n\nAn exceptionally high amount of inactivity or activity leads to a drop in your Readiness Score. If your readiness is low due to intense training and increased Activity Burn, taking time to recover can pay off as improved fitness.",
        "activity-balance": "Activity Balance measures how your activity level over the past days is affecting your readiness to perform.\n\nA full bar indicates that you've been active, but kept from training at your maximum capacity. This has boosted your recovery and helped build up your energy levels.\n\nWhile easier days can have a positive effect on your readiness level, challenging your body every now and then by increasing your training volumes helps maintain and develop your physical capacity in the long run.",
        "body-temperature": "Oura tracks the variations of your Body Temperature by measuring your skin temperature each night.\n\nBody Temperature is a well-regulated vital parameter. When you sleep, Oura compares your skin temperature to measurements from your earlier nights to estimate your normal range.\n\nA full contributor bar indicates that your estimated Body Temperature is within normal variation. You'll see a lowered Readiness Score when your Body Temperature is outside your normal range.",
        "resting-heart-rate": "Resting Heart Rate (RHR) is the number of times your heart beats per minute when you're at rest. It's a reliable measurement of your recovery status, and an important contributor to your readiness.\n\nOura evaluates the optimal level for your RHR by studying your data after active days and recovery days for a couple of weeks. Once it knows your normal range, your Readiness Score will start to become more accurate.\n\nOura interprets a RHR slightly below your average as a sign of good readiness, whereas an exceptionally high or low RHR is a sign of increased need for recovery.\n\nAn intense training day, a late night workout, elevated body temperature, or a heavy meal just before bed can keep your RHR elevated during the night, often resulting to a lowered Readiness score.",
        "recovery-index": "Recovery Index measures how long it takes for your Resting Heart Rate (RHR) to stabilize during the night.\n\nA sign of very good recovery is that your RHR stabilizes during the first half of the night, at least 6 hours before you wake up.\n\nAlcohol, a heavy meal before bed or late exercise speed up your metabolism and keep your RHR elevated, delaying your recovery and increasing your sleep needs.",
        "total-sleep": "Total Sleep refers to the total amount of time you spend in light, REM and deep sleep.\n\nThe amount of sleep needed varies from person to person. As a general rule, the younger you are, the more sleep you need. Most adults need 7-9 hours to perform well and stay healthy.\n\nGetting a good amount of sleep for your age will keep your Total Sleep time in balance, approximately at 80%. You'll see a full bar when your Total Sleep time reaches 9 hours.",
        "efficiency": "Sleep Efficiency is a measurement of your sleep quality. It's the percentage of time you actually spend asleep after going to bed.\n\nFor adults, a generally accepted cut-off score for good Sleep Efficiency is 85%. It's common for Sleep Efficiency to slightly decrease with age.\n\nFor a maximum positive contribution to your Sleep Score, your Sleep Efficiency needs to be 95%. You'll see a lowered Sleep Score if it has taken more than 20 minutes for you to fall asleep, or if you experience one long or multiple shorter wake-ups during the night.",
        "restfulness": "Sleep Disturbances caused by wake-ups, get-ups and restless time during your sleep can have a big impact on your sleep quality and daytime cognitive performance.\n\nRestless sleep is less restorative than uninterrupted sleep, and it's usually the cause of daytime sleepiness.\n\nDisturbances can be caused by various different factors, such as stress, noise, partners, pets or different foods. To improve your chances of getting restful sleep:\n 	•  Optimize your sleep environment by making sure your mattress is comfortable and your bedroom is cool (≈ 65 ℉/18 ℃), quiet and dark.\n 	•  Avoid spicy, heavy meals and alcohol close to bedtime, and caffeine in the afternoon and evening.\n 	•  While regular physical activity can make your sleep more restful, try to complete exercise at least 1-2 h before bedtime.\n 	•  Help your brain and body to wind down by disconnecting from bright screens and dimming bright lights 1-2 h before going to sleep.",
        "rem-sleep": "REM (rapid eye movement) Sleep plays an essential role in re-energizing your mind and your body, making it an important contributor to your sleep quality.\n\nREM is associated with dreaming, memory consolidation, learning and creativity.\n\nMaking up anywhere between 5-50% of your total sleep time, the amount of REM can vary significantly between nights and individuals. On average REM counts for 20-25% (1.5h - 2h) of total sleep time for adults, and it usually decreases with age.\n\nREM is regulated by circadian rhythms, i.e. your body clock. Getting a full night's sleep, sticking to a regular sleep schedule and avoiding caffeine, alcohol or other stimulants in the evening may increase your chances of getting more REM.",
        "deep-sleep": "Deep Sleep is the most restorative and rejuvenating sleep stage, enabling muscle growth and repair.\n\nSleep can be classified into non-rapid eye movement (NREM, stages 1-3) and rapid eye movement (REM) sleep, which alternate in cycles throughout the night. Deep Sleep or N3 is the deepest NREM sleep phase.\n\nWhen you're in Deep Sleep, your blood pressure drops, heart and breathing rates are regular, arm and leg muscles are relaxed and you're very difficult to awaken.\n\nVarying significantly between nights and individuals, Deep Sleep can make up anywhere between 0-35% of your total sleep time. On average adults spend 15-20% of their total sleep time in Deep Sleep, the percentage usually decreasing with age.\n\nRegular physical activity, avoiding heavy meals and alcohol before bed and long naps and caffeine in the afternoon can improve your chances of getting more deep sleep.",
        "latency": "Sleep Latency is the time it takes for you to fall asleep.\n\nIdeally falling asleep shouldn't take more than 15-20 minutes.\n\nFalling asleep immediately (in less than 5 minutes) could be a sign that you're not getting enough sleep for your needs.\n\nIf you have trouble falling asleep, try getting out of bed and doing something relaxing, ideally in low light conditions, until you feel sleepy again.",
        "timing": "Your Sleep Timing is an important contributor to your sleep quality and daytime performance.\n\nMost of your body’s essential processes such as your body temperature, hormone release and hunger run in 24-hour cycles called circadian rhythms. Sleeping during the night and staying awake and active during the day can help keep these internal rhythms in balance, and helps you perform better throughout the day.\n\nOura considers your Sleep Timing to be optimal and aligned with the sun when the midpoint of your sleep falls between midnight and 3 am, allowing some variability for morning and evening types. A timing significantly earlier or later can lower your Sleep Score.",
        "stay-active": "Moving around and avoiding long periods of inactivity helps you stay healthy, and keeps your metabolism active throughout the day.\n\nOura measures the time you’ve spent sitting, standing or otherwise inactive during the past 24 hours. Inactive time doesn’t include resting or sleep.\n\nHaving 5-8 hours or less of inactive time per day has a positive effect on your Activity Score. You can see your inactive time under the sitting icon in the Activity view.\n\nIf your inactive time exceeds 12 hours, it’s recommended to take action, and increase the amount of Low or Medium+ intensity level activities. Breaking up inactive time by taking walking breaks will also help keep your Activity Score at a good level.",
        "move-every-hour": "Oura tracks the time you spend sitting, standing or otherwise passive, and guides you to break up long periods of inactivity.\n\nOura shows the number of continuous one-hour periods of inactivity above the sitting icon, and your total daily inactive time below it. Keeping both numbers as small as possible has a positive impact on your Activity Score.\n\nIf you've enabled notifications, Oura will remind you to get moving after 50 minutes of inactivity. Once the alert goes off, you have 10 minutes to react to it. You can reset the alert by walking briskly for 1-2 minutes or doing some low intensity activity for 2-3 minutes.",
        "meet-daily-goals": "Meet Daily Targets shows how often you’ve reached your daily activity targets over the past 7 days.\n\nOura gives you a daily activity target based on your age, gender and readiness level.\n\nYour daily activity is measured from 4 am to 4 am. Whether it's everyday activities or intense training, all daily movement measured during this 24-hour period moves you closer to your daily target.\n\nMeet Daily Targets will be at 100% when you’ve met your target 6-7 times a week. Falling short of your target on 3 or more days starts to lower your Activity Score.",
        "training-frequency": "Training Frequency measures how often you've gotten medium and high intensity activity over the past 7 days.\n\nOptimal training frequency is key to maintaining and developing your cardiovascular fitness.\n\nOura recommends getting at least 100 MET minutes of Medium+ Activity a day (100-150 kcal, depending on your body weight). This is equivalent to 20 minutes of jogging or 30 minutes of brisk walking.\n\nTo stay in balance and to boost your Activity Score, your Training Frequency should be at 3-4 times a week.\n\nMET or Metabolic Equivalent is a common measure used to express the energy expenditure and intensity of different physical activities. If the MET value of a specific activity is 4, it means that you’re burning 4 times as many calories as you would burn while resting.\n\nThe time engaged in different activities can be expressed as MET minutes. For example:\n  • 30 min x 5 METs = 150 MET min\n • 30 min x 7 METs = 210 MET min",
        "training-volume": "Training Volume measures the amount of medium and high intensity activity you’ve gotten over the past 7 days.\n\nLike Training Frequency, Training Volume is an essential aspect of maintaining and improving your fitness level.\n\nFor your Training Volume to have a maximum positive contribution to your Activity Score, you need to get 2000 MET minutes of medium to high intensity activity per week (2000-3000 kcal, depending on your body weight).\n\nWhen your activity level goes below 750 MET minutes a week (750-1500 kcal), your Activity Score will start to decline.\n\nMET or Metabolic Equivalent is a common measure used to express the energy expenditure and intensity of different physical activities. If the MET value of a specific activity is 4, it means that you’re burning 4 times as many calories as you would burn while resting.\n\nThe time engaged in different activities can be expressed as MET minutes. For example:\n  • 30 min x 5 METs = 150 MET min\n  • 30 min x 7 METs = 210 MET min",
        "recovery-time": "Having a sufficient amount of easier days in your training program boosts your performance and helps speed up your recovery.\n\nNo matter how much you train, the actual fitness progress takes place during Recovery Time, when your muscles have time to repair and grow.\n\nFor Oura, an easy day means keeping the amount of medium intensity level activity below 200 MET minutes (200-300 kcal/day), and high intensity activity below 100 MET minutes (100-150 kcal/day).\n\nIn practice this can mean doing lots of low intensity activities, getting healthy amounts of medium intensity activity (30-60 min), but only a small amount of high intensity activity (below 10 min).\n\nMET or Metabolic Equivalent is a common measure used to express the energy expenditure and intensity of different physical activities. If the MET value of a specific activity is 4, it means that you’re burning 4 times as many calories as you would burn while resting.\n\nThe time engaged in different activities can be expressed as MET minutes. For example:\n  • 30 min x 5 METs = 150 MET min\n  • 30 min x 7 METs = 210 MET min",
        "hrv-balance": "HRV Balance helps you keep track of your recovery status by comparing your 2-week heart rate variability trend to your 3-month average.\n\n Optimal= Your recent HRV trend is on par or better than your average, which is usually a sign of good recovery.\n\n Good = Your recent HRV trend is slightly different from your average, but on a good level.\n\n Pay attention = Your recent HRV trend is below your average, which can be a sign that your body or mind is under stress."
    }

    return html.Div(
        className='row', children=[
            html.Div(id=id, className='col-lg-12', style={'clear': 'both'}, children=[
                html.P(top_left_title, className='contributorleft'),
                html.P(top_right_title, className='contributorright', style={'color': textColor})
            ]),
            dbc.Tooltip(tooltipDict[id], target=id + '-bar'),
            dcc.Graph(id=id + '-bar', className='col-lg-12',
                      config={'displayModeBar': False},
                      figure={
                          'data': [
                              go.Bar(
                                  y=df.index,
                                  x=df[column_name],
                                  orientation='h',
                                  hoverinfo='none',
                                  marker={'color': barColor},
                              ),
                              go.Bar(
                                  y=df.index,
                                  x=100 - df[column_name],
                                  orientation='h',
                                  hoverinfo='none',
                                  marker={'color': 'grey'}
                              ),
                          ],
                          'layout': go.Layout(
                              height=10,
                              transition=dict(duration=transition),
                              xaxis=dict(
                                  showgrid=False,
                                  showticklabels=False,
                                  range=[0, 100],
                              ),
                              yaxis=dict(
                                  showgrid=False,
                                  showticklabels=False,
                                  gridcolor='rgb(73, 73, 73)',
                                  gridwidth=.5,
                              ),
                              margin={'l': 0, 'b': 0, 't': 0, 'r': 0},
                              showlegend=False,
                              barmode='stack',
                          )
                      })
        ])


def generate_oura_sleep_header_kpi(date):
    df = pd.read_sql(
        sql=app.session.query(ouraSleepSummary.score).filter(ouraSleepSummary.report_date == date).statement,
        con=engine)
    # Default to max date if date passed is not yet in db (not on oura cloud)
    if len(df) == 0:
        date = app.session.query(func.max(ouraSleepSummary.report_date)).first()[0]
        df = pd.read_sql(
            sql=app.session.query(ouraSleepSummary.score).filter(ouraSleepSummary.report_date == date).statement,
            con=engine)

    app.session.remove()

    score = df.loc[df.index.max()]['score']
    star = (score >= 85)

    return datetime.strftime(date, "%A %b %d, %Y"), star, '{:.0f}'.format(score)


def generate_oura_sleep_header_chart(date, days=7, summary=False, resample='D'):
    height = chartHeight if not summary else 300

    if summary:
        df = pd.read_sql(sql=app.session.query(ouraSleepSummary).statement,
                         con=engine, index_col='report_date')
    else:
        df = pd.read_sql(sql=app.session.query(ouraSleepSummary).filter(ouraSleepSummary.report_date > date).statement,
                         con=engine, index_col='report_date')[:days]

    daily_sleep_hr_target = app.session.query(athlete).filter(athlete.athlete_id == 1).first().daily_sleep_hr_target

    app.session.remove()

    # Resampling for modal buttons
    df = df.set_index(pd.to_datetime(df.index))
    df = df.resample(resample).mean()
    buttons, range, tickformat = modal_range_buttons(df=df, resample=resample)

    df['awake_tooltip'] = ['<b>Awake</b>: {:.0f}h {:.0f}m'.format(x, y) for (x, y) in
                           zip(df['awake'] // 3600, (df['awake'] % 3600) // 60)]

    df['rem_tooltip'] = ['<b>REM</b>: {:.0f}h {:.0f}m <b>{:.0f}%'.format(x, y, z) for (x, y, z) in
                         zip(df['rem'] // 3600, (df['rem'] % 3600) // 60, (df['rem'] / df['total']) * 100)]

    df['light_tooltip'] = ['<b>Light</b>: {:.0f}h {:.0f}m <b>{:.0f}%'.format(x, y, z) for (x, y, z) in
                           zip(df['light'] // 3600, (df['light'] % 3600) // 60, (df['light'] / df['total']) * 100)]

    df['deep_tooltip'] = ['<b>Deep</b>: {:.0f}h {:.0f}m <b>{:.0f}%'.format(x, y, z) for (x, y, z) in
                          zip(df['deep'] // 3600, (df['deep'] % 3600) // 60, (df['deep'] / df['total']) * 100)]

    full_chart = [
        go.Scatter(
            name='Deep',
            x=df.index,
            y=round(df['deep'] / 60),
            mode='lines',
            text=df['deep_tooltip'],
            hoverinfo='text',
            opacity=0.7,
            line={'shape': 'spline', 'color': dark_blue},
            fill='tonexty',
            fillcolor=dark_blue,
            stackgroup='one'
        ),
        go.Scatter(
            name='Light',
            x=df.index,
            y=round(df['light'] / 60),
            mode='lines',
            text=df['light_tooltip'],
            hoverinfo='text',
            opacity=0.7,
            line={'shape': 'spline', 'color': light_blue},
            fill='tonexty',
            fillcolor=light_blue,
            stackgroup='one'
        ),
        go.Scatter(
            name='REM',
            x=df.index,
            y=round(df['rem'] / 60),
            mode='lines',
            text=df['rem_tooltip'],
            hoverinfo='text',
            opacity=0.7,
            line={'shape': 'spline', 'color': teal},
            fill='tonexty',
            fillcolor=teal,
            stackgroup='one'
        ),
        go.Scatter(
            name='Awake',
            x=df.index,
            y=round(df['awake'] / 60),
            mode='lines',
            text=df['awake_tooltip'],
            hoverinfo='text',
            opacity=0.7,
            line={'shape': 'spline', 'color': white},
            fill='tonexty',
            fillcolor=white,
            stackgroup='one'
        ),
        go.Scatter(
            name='8hr target',
            x=df.index,
            y=[daily_sleep_hr_target * 60 for x in df.index],
            mode='lines+text',
            text=['{} hours'.format(daily_sleep_hr_target) if x == df.index.max() else '' for x
                  in
                  df.index],
            textfont=dict(
                size=11,
                color='rgb(150,150,150)'
            ),
            textposition='bottom left',
            hoverinfo='none',
            # opacity=0.7,
            line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': 1},
            showlegend=False,
        )
    ]

    summary_chart = [
        go.Scatter(
            name='Deep',
            x=df.index,
            y=round(df['deep'] / 60),
            mode='lines',
            text=df['deep_tooltip'],
            hoverinfo='text+x',
            opacity=0.7,
            line={'shape': 'spline', 'color': dark_blue},
            fill='tonexty',
            fillcolor=dark_blue,
            stackgroup='one'
        ),
        go.Scatter(
            name='Light',
            x=df.index,
            y=round(df['light'] / 60),
            mode='lines',
            text=df['light_tooltip'],
            hoverinfo='text+x',
            opacity=0.7,
            line={'shape': 'spline', 'color': light_blue},
            fill='tonexty',
            fillcolor=light_blue,
            stackgroup='one'
        ),
        go.Scatter(
            name='REM',
            x=df.index,
            y=round(df['rem'] / 60),
            mode='lines',
            text=df['rem_tooltip'],
            hoverinfo='text+x',
            opacity=0.7,
            line={'shape': 'spline', 'color': teal},
            fill='tonexty',
            fillcolor=teal,
            stackgroup='one'
        ),
        go.Scatter(
            name='Awake',
            x=df.index,
            y=round(df['awake'] / 60),
            mode='lines',
            text=df['awake_tooltip'],
            hoverinfo='text+x',
            opacity=0.7,
            line={'shape': 'spline', 'color': white},
            fill='tonexty',
            fillcolor=white,
            stackgroup='one'
        ),
        go.Scatter(
            name='8hr target',
            x=df.index,
            y=[daily_sleep_hr_target * 60 for x in df.index],
            mode='lines+text',
            text=['{} hours'.format(daily_sleep_hr_target) if x == df.index.max() else '' for x
                  in
                  df.index],
            textfont=dict(
                size=11,
                color='rgb(150,150,150)'
            ),
            textposition='bottom left',
            hoverinfo='x',
            # opacity=0.7,
            line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': 1},
            showlegend=False,
        )
    ]
    full_layout = go.Layout(
        height=height,
        transition=dict(duration=transition),
        font=dict(
            color=white,
            size=10,
        ),
        # hoverlabel={'font': {'size': 10}},
        xaxis=dict(
            showline=True,
            color=white,
            showgrid=False,
            showticklabels=True,
            tickvals=df.index,
            tickformat='%a',
            # Specify range to get rid of auto x-axis padding when using scatter markers
            # range=[df.index.min(),
            #        df.index.max()],
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            gridcolor='rgb(73, 73, 73)',
            gridwidth=.5
        ),
        # Set margins to 0, style div sets padding
        margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
        showlegend=False,
        legend=dict(
            x=.5,
            y=-.2,
            xanchor='center',
            orientation="h",
        ),
        hovermode='x'
    )

    summary_layout = go.Layout(
        height=height,
        transition=dict(duration=transition),
        font=dict(
            color=white,
            size=10,
        ),
        # hoverlabel={'font': {'size': 10}},
        xaxis=dict(
            showline=True,
            color=white,
            showgrid=False,
            showticklabels=True,
            tickvals=df.index,
            tickformat='%b %d',
            range=range,
            rangeselector=dict(
                # bgcolor='rgb(66, 66, 66)',
                # bordercolor='#d4d4d4',
                borderwidth=.5,
                buttons=buttons,
                xanchor='center',
                x=.5,
                y=.97,
            ),
            rangeslider=dict(
                visible=True
            ),
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            gridcolor='rgb(73, 73, 73)',
            gridwidth=.5
        ),
        # Set margins to 0, style div sets padding
        margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
        showlegend=False,
        hovermode='x'
    )

    short_layout = go.Layout(
        height=height,
        transition=dict(duration=transition),
        font=dict(
            color=white,
            size=10,
        ),
        # hoverlabel={'font': {'size': 10}},
        xaxis=dict(
            showline=True,
            color=white,
            showgrid=False,
            showticklabels=True,
            tickvals=df.index,
            tickformat='%a',
            # Specify range to get rid of auto x-axis padding when using scatter markers
            # range=[df.index.min(),
            #        df.index.max()],
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            gridcolor='rgb(73, 73, 73)',
            gridwidth=.5,
        ),
        # Set margins to 0, style div sets padding
        margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
        showlegend=False,
        legend=dict(
            x=.5,
            y=-.2,
            xanchor='center',
            orientation="h",
            font=dict(
                size=10,
                color=white
            ),
        ),
        # barmode='stack',
    )

    short_chart = [
        go.Bar(
            name='Deep',
            x=df.index,
            y=round(df['deep'] / 60),
            text=df['deep_tooltip'],
            hoverinfo='text',
            marker={'color': dark_blue},
        ),

        go.Bar(
            name='Light',
            x=df.index,
            y=round(df['light'] / 60),
            text=df['light_tooltip'],
            hoverinfo='text',
            marker={'color': light_blue},
        ),
        go.Bar(
            name='REM',
            x=df.index,
            y=round(df['rem'] / 60),
            text=df['rem_tooltip'],
            hoverinfo='text',
            marker={'color': teal},
        ),
        go.Bar(
            name='Awake',
            x=df.index,
            y=round(df['awake'] / 60),
            text=df['awake_tooltip'],
            hoverinfo='text',
            marker={'color': white},
        ),
    ]

    if summary:
        chart = summary_chart
        layout = summary_layout
    else:
        chart = short_chart if len(df) <= 3 else full_chart
        layout = short_layout if len(df) <= 3 else full_layout

    # chart = short_chart
    # layout = short_layout

    figure = {
        'data': chart,
        'layout': layout
    }

    # Initial click data so callback will fire for content container
    clickData = {'points': [{'x': df.index.max(),
                             'y': df['deep'].max()},
                            {'y': df['light'].max()},
                            {'y': df['rem'].max()},
                            {'y': df['awake'].max()},
                            {'y': daily_sleep_hr_target}]}

    return figure, clickData


def generate_oura_sleep_content(date):
    # If the date passed is today's date (usually the default on load), grab the max date from db just in case oura cloud does not have current date yet
    if not date or date == datetime.today().date():
        date = app.session.query(func.max(ouraSleepSummary.report_date))[0][0]

    df = pd.read_sql(sql=app.session.query(ouraSleepSummary).filter(ouraSleepSummary.report_date == date).statement,
                     con=engine, index_col='report_date')

    app.session.remove()

    return [html.Div(className='row', children=[
        html.Div(id='oura-sleep-content-kpi-trend', className='col', style={'display': 'none'})
    ]),

            html.Div(id='sleep-content-kpi', className='row', children=[
                html.Div(className='col', children=[
                    dbc.Button(id='total-sleep-time-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['TOTAL SLEEP TIME']),
                        html.H6(('{}h {}m'.format(df['total'].max() // 3600, (df['total'].max() % 3600) // 60)),
                                className='mb-0')
                    ]),

                    dbc.Button(id='total-time-in-bed-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['TIME IN BED']),
                        html.H6('{}h {}m'.format(df['duration'].max() // 3600, (df['duration'].max() % 3600) // 60),
                                className='mb-0')
                    ]),
                    dbc.Button(id='sleep-efficiency-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['SLEEP EFFICIENCY']),
                        html.H6('{}%'.format(df['efficiency'].max()),
                                className='mb-0')
                    ]),
                    dbc.Tooltip('Sleep efficiency is the percentage of time sleeping while in bed',
                                target='sleep-efficiency-button'),
                ])
            ]),

            html.Div(className='row', children=[
                html.Div(id='sleep-stages-day-trend', className='col', children=[
                    html.H6('Sleep Stages', style={'marginBottom': '0%'}),
                    html.Div(id='sleep-stages-chart-container', className='col',
                             children=generate_sleep_stages_chart(date)),
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(id='sleep-contributors', className='col-lg-12', children=[
                    html.H6('Sleep Contributors'),
                    generate_contributor_bar(df=df, id='total-sleep', column_name='score_total',
                                             top_left_title='Total Sleep',
                                             top_right_title='{}h {}m'.format(df['total'].max() // 3600,
                                                                              (df['total'].max() % 3600) // 60)),
                    generate_contributor_bar(df=df, id='efficiency', column_name='score_efficiency',
                                             top_left_title='Efficiency',
                                             top_right_title='{:.0f}%'.format(df['score_efficiency'].max())),
                    generate_contributor_bar(df=df, id='restfulness', column_name='score_disturbances',
                                             top_left_title='Restfulness'),
                    generate_contributor_bar(df=df, id='rem-sleep', column_name='score_rem',
                                             top_left_title='REM Sleep',
                                             top_right_title='{:.0f}h {:.0f}m, {:.0f}%'.format(
                                                 df['rem'].max() // 3600, (df['rem'].max() % 3600) // 60,
                                                 (df['rem'].max() / df['total'].max()) * 100)),
                    generate_contributor_bar(df=df, id='deep-sleep', column_name='score_deep',
                                             top_left_title='Deep Sleep',
                                             top_right_title='{:.0f}h {:.0f}m, {:.0f}%'.format(
                                                 df['deep'].max() // 3600, (df['deep'].max() % 3600) // 60,
                                                 (df['deep'].max() / df['total'].max()) * 100)),
                    generate_contributor_bar(df=df, id='latency', column_name='score_latency',
                                             top_left_title='Latency',
                                             top_right_title='{:.0f}m'.format(df['onset_latency'].max() / 60)),
                    generate_contributor_bar(df=df, id='timing', column_name='score_alignment',
                                             top_left_title='Timing')

                ])
            ])

            ]


def generate_sleep_modal_summary(days=7):
    date = datetime.now().date() - timedelta(days=days)

    df = pd.read_sql(
        sql=app.session.query(ouraSleepSummary.report_date, ouraSleepSummary.score, ouraSleepSummary.total,
                              ouraSleepSummary.bedtime_end_local).filter(
            ouraSleepSummary.report_date > date).statement, con=engine,
        index_col='report_date')

    app.session.remove()

    df['wakeup'] = df['bedtime_end_local'].apply(
        lambda x: datetime.strptime('1970-01-01', '%Y-%m-%d') + timedelta(hours=x.hour) + timedelta(minutes=x.minute))

    sleep_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                   figure={
                                       'data': [go.Bar(
                                           name='Sleep',
                                           x=df.index,
                                           y=df['score'],
                                           yaxis='y',
                                           text=df['score'],
                                           hoverinfo='text',
                                           hovertext=['Sleep: <b>{:.0f}'.format(x) for x in df['score']],
                                           textposition='auto',
                                           marker={'color': light_blue},
                                       )],
                                       'layout': go.Layout(
                                           height=300,
                                           font=dict(
                                               size=10,
                                               color=white
                                           ),
                                           xaxis=dict(
                                               showline=True,
                                               color=white,
                                               showticklabels=True,
                                               showgrid=False,
                                               tickvals=df.index,
                                               tickformat='%a',
                                           ),
                                           yaxis=dict(
                                               showticklabels=True,
                                               showgrid=True,
                                               gridcolor='rgb(66,66,66)',
                                               color=white,
                                               tickformat=',d',
                                           ),
                                           showlegend=False,
                                           margin={'l': 40, 'b': 20, 't': 0, 'r': 0},
                                       )
                                   })

    total_sleep_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                         figure={
                                             'data': [go.Bar(
                                                 name='Total Sleep Time',
                                                 x=df.index,
                                                 y=df['total'] / 3600,
                                                 yaxis='y',
                                                 hoverinfo='text',
                                                 text=['Total Sleep: <b>{:.0f}h {:.0f}m'.format(x // 3600,
                                                                                                (x // 3600) % 60) for x
                                                       in
                                                       df['total']],
                                                 marker={'color': light_blue},
                                             )],
                                             'layout': go.Layout(
                                                 height=300,
                                                 font=dict(
                                                     size=10,
                                                     color=white
                                                 ),

                                                 xaxis=dict(
                                                     showline=True,
                                                     color=white,
                                                     showticklabels=True,
                                                     showgrid=False,
                                                     tickvals=df.index,
                                                     tickformat='%a',
                                                 ),
                                                 yaxis=dict(
                                                     showticklabels=True,
                                                     showgrid=True,
                                                     gridcolor='rgb(66,66,66)',
                                                     color=white,
                                                     tickformat=',d',
                                                 ),
                                                 showlegend=False,
                                                 margin={'l': 40, 'b': 20, 't': 0, 'r': 0},
                                             )
                                         })

    wake_up_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                     figure={
                                         'data': [go.Scatter(
                                             name='Wake Up Time',
                                             x=df.index,
                                             y=df['wakeup'],
                                             yaxis='y',
                                             text=df['wakeup'],
                                             hovertext=['Wake Up: <b>{}'.format(datetime.strftime(x, '%I:%M%p')) for x
                                                        in df['wakeup']],
                                             hoverinfo='text',
                                             # textfont=dict(
                                             #     size=10,
                                             # ),
                                             # textposition='middle center',
                                             mode='lines+markers',
                                             line={'dash': 'dot',
                                                   'color': white,
                                                   'width': 2},
                                             showlegend=False,
                                             marker={'size': 5},
                                         )],
                                         'layout': go.Layout(
                                             height=300,
                                             font=dict(
                                                 size=10,
                                                 color=white
                                             ),
                                             xaxis=dict(
                                                 showline=True,
                                                 color=white,
                                                 showticklabels=True,
                                                 showgrid=False,
                                                 tickvals=df.index,
                                                 tickformat='%a',
                                             ),
                                             yaxis=dict(
                                                 showticklabels=True,
                                                 showgrid=True,
                                                 gridcolor='rgb(66,66,66)',
                                                 color=white,
                                                 tickformat='%I:%M%p',
                                             ),
                                             showlegend=False,
                                             margin={'l': 50, 'b': 20, 't': 0, 'r': 0},
                                         )
                                     })

    return [
        html.Div(id='sleep-modal-last-7-container', className='row align-items-center text-center mb-2',
                 style={'whiteSpace': 'normal'}, children=[
                html.Div(id='sleep-score-last-7', className='col-lg-4', children=[
                    html.Div(id='sleep-score-last-7-title', className='col-lg-12',
                             children=[
                                 html.P('Your average sleep score for the last 7 days is {:.0f}'.format(
                                     df['score'].mean()))
                             ]),
                    html.Div(id='sleep-score-last-7-chart', className='col-lg-12',
                             children=[sleep_last_7_graph]
                             )
                ]),
                html.Div(id='total-sleep-last-7', className='col-lg-4', children=[
                    html.Div(id='total-sleep-last-7-title', className='col-lg-12',
                             children=[
                                 html.P('Over the last 7 nights you slept on average {:.0f}h {:.0f}m per night'.format(
                                     df['total'].mean() // 3600, (df['total'].mean() // 3600) % 60))
                             ]),
                    html.Div(id='total-sleep-last-7-chart', className='col-lg-12',
                             children=[total_sleep_last_7_graph]
                             )
                ]),
                html.Div(id='wake-up-last-7', className='col-lg-4', children=[
                    html.Div(id='wake-up-last-7-title', className='col-lg-12',
                             children=[
                                 html.P(
                                     "Here's a summary of your wake-up times over the last 7 days")
                             ]),
                    html.Div(id='wake-up-last-7-chart', className='col-lg-12',
                             children=[wake_up_last_7_graph]
                             )
                ]),
            ]),

        html.Div(className='row', children=[
            html.Div(id='sleep-score-correlations', className='col-lg-6', children=[
                html.Div(id='sleep-score-correlation-title', className='col-lg-12 text-center',
                         children=[html.P('Sleep Score Correlations (L6M)')]),
                html.Div(id='sleep-score-correlation-chart', className='col-lg-12',
                         children=[generate_correlation_table(10, 'Sleep score', 180)]
                         )
            ]),

            html.Div(className='col-lg-6', children=[
                html.Div(className='row align-items-center text-center', children=[
                    html.Div(id='sleep-groupby-controls', className='col-lg-12 mb-2 mt-2', children=[
                        dbc.Button('Year', id='sleep-year-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Month', id='sleep-month-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Week', id='sleep-week-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Day', id='sleep-day-button', size='sm')
                    ]),
                ]),

                html.Div(className='row', children=[
                    html.Div(className='col-lg-12', children=[
                        dbc.Spinner(color='info', children=[

                            dcc.Graph(id='sleep-modal-full-chart',
                                      config={'displayModeBar': False}
                                      ),

                        ]),
                    ]),
                ]),
            ])

        ])

    ]


def generate_oura_readiness_header_kpi(date):
    df = pd.read_sql(
        sql=app.session.query(ouraReadinessSummary.score).filter(ouraReadinessSummary.report_date == date).statement,
        con=engine)
    # Default to max date if date passed is not yet in db (not on oura cloud)
    if len(df) == 0:
        date = app.session.query(func.max(ouraReadinessSummary.report_date)).first()[0]
        df = pd.read_sql(
            sql=app.session.query(ouraReadinessSummary.score).filter(
                ouraReadinessSummary.report_date == date).statement,
            con=engine)

    app.session.remove()
    score = df.loc[df.index.max()]['score']
    star = (score >= 85)

    return datetime.strftime(date, "%A %b %d, %Y"), star, '{:.0f}'.format(score)


def generate_oura_readiness_header_chart(date, days=7, summary=False, resample='D'):
    height = chartHeight if not summary else 300

    if summary:
        df = pd.read_sql(
            sql=app.session.query(ouraReadinessSummary).statement, con=engine,
            index_col='report_date')

        hrv_df = pd.read_sql(
            sql=app.session.query(ouraSleepSummary.report_date, ouraSleepSummary.rmssd,
                                  ouraSleepSummary.hr_lowest).statement, con=engine,
            index_col='report_date')

    else:
        df = pd.read_sql(
            sql=app.session.query(ouraReadinessSummary).filter(ouraReadinessSummary.report_date > date).statement,
            con=engine,
            index_col='report_date')[:days]

        hrv_df = pd.read_sql(
            sql=app.session.query(ouraSleepSummary.report_date, ouraSleepSummary.rmssd,
                                  ouraSleepSummary.hr_lowest).filter(
                ouraSleepSummary.report_date > date).statement, con=engine,
            index_col='report_date')[:days]

    # Merge with rediness summary
    df = df.merge(hrv_df, how='left', left_index=True, right_index=True)

    app.session.remove()

    # Resampling for modal buttons
    df = df.set_index(pd.to_datetime(df.index))
    df = df.resample(resample).mean()
    buttons, range, tickformat = modal_range_buttons(df=df, resample=resample)

    if summary:
        data = [
            go.Bar(
                name='Readiness',
                x=df.index,
                y=df['score'],
                yaxis='y1',
                text=round(df['score']),
                hoverinfo='text+x',
                hovertext=['Readiness: <b>{:.0f}'.format(x) for x in df['score']],
                # textfont=dict(
                #     size=10,
                # ),
                # marker=dict(
                #     color=ftp_color,
                # ),
                textposition='auto',

                # opacity=0.7,
                marker={'color': light_blue},
            ),

            # Plotting HRV
            go.Scatter(
                name='HR Variability',
                x=df.index,
                y=round(df['rmssd']),
                yaxis='y2',
                text=['HRV: <b>{:.0f}'.format(x) for x in df['rmssd']],
                hoverinfo='text+x',
                # textfont=dict(
                #     size=10,
                # ),
                # textposition='middle center',
                mode='lines+markers',
                line={'dash': 'dot',
                      'color': teal,
                      'width': 2},
                showlegend=False,
                marker={'size': 5},
            ),

            go.Scatter(
                name='Resting HR',
                x=df.index,
                y=round(df['hr_lowest']),
                yaxis='y2',
                text=['RHR: <b>{:.0f}'.format(x) for x in df['hr_lowest']],
                hoverinfo='text+x',
                # textfont=dict(
                #     size=10,
                # ),
                # textposition='middle center',
                mode='lines+markers',
                line={'dash': 'dot',
                      'color': white,
                      'width': 2},
                showlegend=False,
                marker={'size': 5},
            ),

        ]
        layout = go.Layout(
            height=height,
            transition=dict(duration=transition),
            font=dict(
                size=10,
                color=white
            ),
            # hoverlabel={'font': {'size': 10}},
            xaxis=dict(
                showline=True,
                color=white,
                showticklabels=True,
                showgrid=False,
                tickvals=df.index,
                tickformat=tickformat,
                range=range,
                rangeselector=dict(
                    borderwidth=.5,
                    buttons=buttons,
                    xanchor='center',
                    x=.5,
                    y=.97,
                ),
                rangeslider=dict(
                    visible=True
                ),
            ),
            yaxis=dict(
                showticklabels=False,
                showgrid=False,
            ),
            yaxis2=dict(
                showticklabels=False,
                showgrid=False,
                anchor="free",
                overlaying="y",
                side="right",
            ),
            showlegend=False,
            legend=dict(
                x=.5,
                y=-.2,
                xanchor='center',
                orientation="h",
                font=dict(
                    size=10,
                    color=white
                )),
            margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
        )
    else:
        data = [
            go.Bar(
                name='Readiness',
                x=df.index,
                y=df['score'],
                yaxis='y1',
                text=df['score'],
                hoverinfo='text',
                hovertext=['Readiness: <b>{:.0f}'.format(x) for x in df['score']],
                # textfont=dict(
                #     size=10,
                # ),
                # marker=dict(
                #     color=ftp_color,
                # ),
                textposition='auto',

                # opacity=0.7,
                marker={'color': light_blue},
            ),

            # Plotting HRV
            go.Scatter(
                name='HR Variability',
                x=df.index,
                y=round(df['rmssd']),
                yaxis='y2',
                text=['HRV: <b>{:.0f}'.format(x) for x in df['rmssd']],
                hoverinfo='text',
                # textfont=dict(
                #     size=10,
                # ),
                # textposition='middle center',
                mode='lines+markers',
                line={'dash': 'dot',
                      'color': teal,
                      'width': 2},
                showlegend=False,
                marker={'size': 5},
            ),

            go.Scatter(
                name='Resting HR',
                x=df.index,
                y=round(df['hr_lowest']),
                yaxis='y2',
                text=['RHR: <b>{:.0f}'.format(x) for x in df['hr_lowest']],
                hoverinfo='text',
                # textfont=dict(
                #     size=10,
                # ),
                # textposition='middle center',
                mode='lines+markers',
                line={'dash': 'dot',
                      'color': white,
                      'width': 2},
                showlegend=False,
                marker={'size': 5},
            ),

        ]
        layout = go.Layout(
            height=height,
            transition=dict(duration=transition),
            font=dict(
                size=10,
                color=white
            ),
            # hoverlabel={'font': {'size': 10}},
            xaxis=dict(
                showline=True,
                color=white,
                showticklabels=True,
                showgrid=False,
                tickvals=df.index,
                tickformat='%a',
            ),
            yaxis=dict(
                # range=[0, 100],
                showticklabels=False,
                showgrid=False,
            ),
            yaxis2=dict(
                showticklabels=False,
                showgrid=False,
                anchor="free",
                overlaying="y",
                side="right",
            ),
            showlegend=False,
            legend=dict(
                x=.5,
                y=-.2,
                xanchor='center',
                orientation="h",
                font=dict(
                    size=10,
                    color=white
                )),
            margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
        )
    figure = {
        'data': data,
        'layout': layout
    }
    clickData = {'points': [{'x': df.index.max()}]}

    return figure, clickData


def generate_oura_readiness_content(date):
    # Most readiness data comes from sleep tables

    # If the date passed is today's date (usually the default on load), grab the max date from db just in case oura cloud does not have current date yet
    if not date or date == datetime.today().date():
        sleep_date = app.session.query(func.max(ouraSleepSummary.report_date))[0][0]
        ready_date = app.session.query(func.max(ouraReadinessSummary.report_date))[0][0]
    else:
        sleep_date, ready_date = date, date

    df = pd.read_sql(
        sql=app.session.query(ouraSleepSummary).filter(ouraSleepSummary.report_date == sleep_date).statement,
        con=engine, index_col='report_date')
    df_contributors = pd.read_sql(
        sql=app.session.query(ouraReadinessSummary).filter(ouraReadinessSummary.report_date == ready_date).statement,
        con=engine, index_col='report_date')

    app.session.remove()

    return [html.Div(className='row', children=[
        html.Div(id='oura-readiness-content-kpi-trend', className='col',
                 style={'height': '0%'})
    ]),

            html.Div(id='readiness-content-kpi', className='row', children=[
                html.Div(className='col', children=[
                    dbc.Button(id='resting-heart-rate-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['RESTING HR']),
                        html.H6('{} bpm'.format(df['hr_lowest'].max()),
                                className='mb-0')
                    ]),

                    dbc.Button(id='heart-rate-variability-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['HR VARIABILITY']),
                        html.H6('{} ms'.format(df['rmssd'].max()),
                                className='mb-0'),
                        dbc.Tooltip(
                            'Heart Rate Variability is a measure which indicates the variation in your heartbeats within a specific timeframe.\n\nGenerally speaking, it tells us how recovered and ready we are for the day.\n\nOn the whole, high heart rate variability is an indication of especially cardiovascular, but also overall health as well as general fitness.',
                            target='heart-rate-variability-button'),
                    ]),

                    dbc.Button(id='body-temperature-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['BODY TEMP']),
                        html.H6('{:.1f}°F '.format((df['temperature_delta'].max() * (9 / 5))),
                                className='mb-0')
                    ]),
                    dbc.Tooltip(
                        "Body temperature is a well-regulated vital sign and a powerful indicator of your health status and recovery.\n\nAn elevated body temperature is often a sign that something in your body status requires attention.",
                        target='body-temperature-button'),
                ])
            ]),

            html.Div(className='row', children=[
                html.Div(id='resting-heart-rate-day-trend', className='col', children=[
                    html.H6('Resting Heart Rate', style={'marginBottom': '0%'}),
                    html.Div(id='resting-heart-rate-chart-conainer', className='col',
                             children=generate_rhr_day_chart(date)),
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(id='readiness-contributors', className='col-lg-12', children=[
                    html.H6('Readiness Contributors'),
                    generate_contributor_bar(df=df_contributors, id='resting-heart-rate',
                                             column_name='score_resting_hr',
                                             top_left_title='Resting Heart Rate',
                                             top_right_title='{} bpm'.format(df['hr_lowest'].max())),

                    generate_contributor_bar(df=df_contributors, id='hrv-balance', column_name='score_hrv_balance',
                                             top_left_title='HRV Balance'),

                    generate_contributor_bar(df=df_contributors, id='body-temperature', column_name='score_temperature',
                                             top_left_title='Body Temperature'),
                    generate_contributor_bar(df=df_contributors, id='recovery-index',
                                             column_name='score_recovery_index',
                                             top_left_title='Recovery Index'),
                    generate_contributor_bar(df=df_contributors, id='previous-night',
                                             column_name='score_previous_night',
                                             top_left_title='Previous Night',
                                             top_right_title='Sleep Score {}'.format(df['score'].max())),
                    generate_contributor_bar(df=df_contributors, id='sleep-balance', column_name='score_sleep_balance',
                                             top_left_title='Sleep Balance'),
                    generate_contributor_bar(df=df_contributors, id='previous-day-activity',
                                             column_name='score_previous_day',
                                             top_left_title='Previous Day Activity'),
                    generate_contributor_bar(df=df_contributors, id='activity-balance',
                                             column_name='score_activity_balance',
                                             top_left_title='Activity Balance'),

                ])
            ])

            ]


def generate_readiness_modal_summary(days=7):
    date = datetime.now().date() - timedelta(days=days)

    df = pd.read_sql(
        sql=app.session.query(ouraReadinessSummary).filter(ouraReadinessSummary.report_date > date).statement,
        con=engine,
        index_col='report_date')
    hrv_df = pd.read_sql(
        sql=app.session.query(ouraSleepSummary.report_date, ouraSleepSummary.rmssd, ouraSleepSummary.hr_lowest).filter(
            ouraSleepSummary.report_date > date).statement, con=engine,
        index_col='report_date')

    app.session.remove()
    df = df.merge(hrv_df, how='left', left_index=True, right_index=True)

    if len(df) > 1:
        hrv_slope, hrv_intercept = np.polyfit(df.reset_index().index, df['rmssd'], 1)
        hrv_insight = 'Your {} HRV trend implies that {}'.format("downward" if hrv_slope < 0 else "upwards",
                                                                 "you should keep an eye on your recovery status" if hrv_slope < 0 else "you've recovered well")

        rhr_slope, rhr_intercept = np.polyfit(df.reset_index().index, df['hr_lowest'], 1)
        rhr_insight = 'Your {} RHR trend implies that {}'.format("downward" if rhr_slope < 0 else "upwards",
                                                                 "you've recovered well" if rhr_slope < 0 else "something may be challenging your recovery")

    else:
        hrv_slope, hrv_intercept = 0, 0
        rhr_slope, rhr_intercept = 0, 0
        hrv_insight = 'Not enough data to calculate insights from your HRV trend'
        rhr_insight = 'Not enough data to calculate insights from your RHR trend'

    df['hrv_trend'] = (df.reset_index().index * hrv_slope) + hrv_intercept
    df['rhr_trend'] = (df.reset_index().index * rhr_slope) + rhr_intercept

    readiness_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                       figure={
                                           'data': [go.Bar(
                                               name='Readiness',
                                               x=df.index,
                                               y=df['score'],
                                               yaxis='y',
                                               text=df['score'],
                                               hoverinfo='text',
                                               hovertext=['Readiness: <b>{:.0f}'.format(x) for x in df['score']],
                                               textposition='auto',
                                               marker={'color': light_blue},
                                           )],
                                           'layout': go.Layout(
                                               height=300,
                                               font=dict(
                                                   size=10,
                                                   color=white
                                               ),
                                               xaxis=dict(
                                                   showline=True,
                                                   color=white,
                                                   showticklabels=True,
                                                   showgrid=False,
                                                   tickvals=df.index,
                                                   tickformat='%a',
                                               ),
                                               yaxis=dict(
                                                   showticklabels=True,
                                                   showgrid=True,
                                                   gridcolor='rgb(66,66,66)',
                                                   color=white,
                                                   tickformat=',d',
                                               ),
                                               showlegend=False,
                                               margin={'l': 20, 'b': 20, 't': 0, 'r': 0},
                                           )
                                       })

    hrv_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                 figure={
                                     'data': [go.Scatter(
                                         name='HR Variability',
                                         x=df.index,
                                         y=round(df['rmssd']),
                                         yaxis='y',
                                         text=['HRV: <b>{:.0f} ms'.format(x) for x in df['rmssd']],
                                         hoverinfo='text',
                                         mode='lines+markers',
                                         line={'dash': 'dot',
                                               'color': teal,
                                               'width': 2},
                                         showlegend=False,
                                         marker={'size': 5},
                                     ),
                                         go.Scatter(
                                             name='HRV Trend',
                                             x=df.index,
                                             y=df['hrv_trend'],
                                             yaxis='y',
                                             hoverinfo='none',
                                             mode='lines',
                                             line={
                                                 'color': teal,
                                                 'width': 2},
                                             showlegend=False,
                                         ),
                                         go.Scatter(
                                             name='Average',
                                             x=df.index,
                                             y=[df['rmssd'].mean() for x in df.index],
                                             mode='lines+text',
                                             text=[
                                                 'Avg: <b>{:.0f} ms'.format(
                                                     df['rmssd'].mean()) if x == df.index.max() else ''
                                                 for x
                                                 in
                                                 df.index],
                                             textfont=dict(
                                                 size=11,
                                                 color='rgb(150,150,150)'
                                             ),
                                             textposition='top left',
                                             hoverinfo='none',
                                             # opacity=0.7,
                                             line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': 1},
                                             showlegend=False,
                                         )
                                     ],
                                     'layout': go.Layout(
                                         height=300,
                                         font=dict(
                                             size=10,
                                             color=white
                                         ),
                                         xaxis=dict(
                                             showline=True,
                                             color=white,
                                             showticklabels=True,
                                             showgrid=False,
                                             tickvals=df.index,
                                             tickformat='%a',
                                         ),
                                         yaxis=dict(
                                             showticklabels=True,
                                             showgrid=True,
                                             gridcolor='rgb(66,66,66)',
                                             color=white,
                                             tickformat=',d',
                                         ),
                                         showlegend=False,
                                         margin={'l': 20, 'b': 20, 't': 0, 'r': 0},
                                     )
                                 })
    rhr_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                 figure={
                                     'data': [go.Scatter(
                                         name='Resting HR',
                                         x=df.index,
                                         y=round(df['hr_lowest']),
                                         yaxis='y',
                                         text=['RHR: <b>{:.0f} bpm'.format(x) for x in df['hr_lowest']],
                                         hoverinfo='text',
                                         # textfont=dict(
                                         #     size=10,
                                         # ),
                                         # textposition='middle center',
                                         mode='lines+markers',
                                         line={'dash': 'dot',
                                               'color': white,
                                               'width': 2},
                                         showlegend=False,
                                         marker={'size': 5},
                                     ),
                                         go.Scatter(
                                             name='RHR Trend',
                                             x=df.index,
                                             y=df['rhr_trend'],
                                             yaxis='y',
                                             hoverinfo='none',
                                             mode='lines',
                                             line={
                                                 'color': white,
                                                 'width': 2},
                                             showlegend=False,
                                         ),
                                         go.Scatter(
                                             name='Average',
                                             x=df.index,
                                             y=[df['hr_lowest'].mean() for x in df.index],
                                             mode='lines+text',
                                             text=[
                                                 'Avg: <b>{:.0f} bpm'.format(
                                                     df['hr_lowest'].mean()) if x == df.index.max() else ''
                                                 for x
                                                 in
                                                 df.index],
                                             textfont=dict(
                                                 size=11,
                                                 color='rgb(150,150,150)'
                                             ),
                                             textposition='top left',
                                             hoverinfo='none',
                                             # opacity=0.7,
                                             line={'dash': 'dot', 'color': 'rgb(150,150,150)', 'width': 1},
                                             showlegend=False,
                                         )
                                     ],
                                     'layout': go.Layout(
                                         height=300,
                                         font=dict(
                                             size=10,
                                             color=white
                                         ),
                                         xaxis=dict(
                                             showline=True,
                                             color=white,
                                             showticklabels=True,
                                             showgrid=False,
                                             tickvals=df.index,
                                             tickformat='%a',
                                         ),
                                         yaxis=dict(
                                             showticklabels=True,
                                             showgrid=True,
                                             gridcolor='rgb(66,66,66)',
                                             color=white,
                                             tickformat=',d',
                                         ),
                                         showlegend=False,
                                         margin={'l': 20, 'b': 20, 't': 0, 'r': 0},
                                     )
                                 })

    return [
        html.Div(id='readiness-modal-last-7-container', className='row align-items-center text-center mb-2',
                 style={'whiteSpace': 'normal'}, children=[
                html.Div(id='readiness-score-last-7', className='col-lg-4', children=[
                    html.Div(id='readiness-score-last-7-title',
                             children=[
                                 html.P('Your average readiness score for the last 7 days is {:.0f}'.format(
                                     df['score'].mean()))
                             ]),
                    html.Div(id='readiness-score-last-7-chart',
                             children=[readiness_last_7_graph]
                             )
                ]),
                html.Div(id='hrv-score-last-7', className='col-lg-4', children=[
                    html.Div(id='hrv-score-last-7-title',
                             children=[
                                 html.P(hrv_insight)
                             ]),
                    html.Div(id='hrv-score-last-7-chart',
                             children=[hrv_last_7_graph]
                             )
                ]),
                html.Div(id='rhr-score-last-7', className='col-lg-4', children=[
                    html.Div(id='rhr-score-last-7-title',
                             children=[
                                 html.P(rhr_insight)
                             ]),
                    html.Div(id='rhr-score-last-7-chart',
                             children=[rhr_last_7_graph]
                             )
                ]),
            ]),

        html.Div(className='row', children=[
            html.Div(id='readiness-score-correlations', className='col-lg-6', children=[
                html.Div(id='readiness-score-correlation-title', className='col-lg-12 text-center',
                         children=[html.P('Readiness Score Correlations (L6M)')]),
                html.Div(id='readiness-score-correlation-chart', className='col-lg-12',
                         children=[generate_correlation_table(10, 'Readiness score', 180)]
                         )
            ]),

            html.Div(className='col-lg-6', children=[
                html.Div(className='row align-items-center text-center', children=[
                    html.Div(id='readiness-groupby-controls', className='col-lg-12 mb-2 mt-2', children=[
                        dbc.Button('Year', id='readiness-year-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Month', id='readiness-month-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Week', id='readiness-week-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Day', id='readiness-day-button', size='sm')
                    ]),
                ]),

                html.Div(className='row', children=[
                    html.Div(className='col-lg-12', children=[
                        dbc.Spinner(color='info', children=[

                            dcc.Graph(id='readiness-modal-full-chart',
                                      config={'displayModeBar': False}
                                      ),

                        ]),
                    ]),
                ]),
            ])

        ])

    ]


def generate_oura_activity_header_kpi(date):
    df = pd.read_sql(
        sql=app.session.query(ouraActivitySummary.score).filter(ouraActivitySummary.summary_date == date).statement,
        con=engine)
    # Default to max date if date passed is not yet in db (not on oura cloud)
    if len(df) == 0:
        date = app.session.query(func.max(ouraActivitySummary.summary_date)).first()[0]
        df = pd.read_sql(
            sql=app.session.query(ouraActivitySummary.score).filter(ouraActivitySummary.summary_date == date).statement,
            con=engine)

    app.session.remove()
    score = df.loc[df.index.max()]['score']
    star = (score >= 85)
    return datetime.strftime(date, "%A %b %d, %Y"), star, '{:.0f}'.format(score)


def generate_oura_activity_header_chart(date, days=7, summary=False, resample='D'):
    height = chartHeight if not summary else 300

    if summary:
        df = pd.read_sql(sql=app.session.query(ouraActivitySummary).statement, con=engine, index_col='summary_date')
    else:
        df = pd.read_sql(
            sql=app.session.query(ouraActivitySummary).filter(ouraActivitySummary.summary_date > date).statement,
            con=engine, index_col='summary_date')[:days]

    app.session.remove()

    # Resampling for modal buttons
    df = df.set_index(pd.to_datetime(df.index))
    df = df.resample(resample).mean()
    buttons, range, tickformat = modal_range_buttons(df=df, resample=resample)

    df['high_tooltip'] = ['<b>High</b>: {:.0f}h {:.0f}m'.format(x, y) for (x, y) in
                          zip(df['high'] // 60, df['high'] % 60)]
    df['medium_tooltip'] = ['<b>Medium</b>: {:.0f}h {:.0f}m'.format(x, y) for (x, y) in
                            zip(df['medium'] // 60, df['medium'] % 60)]
    df['low_tooltip'] = ['<b>Low</b>: {:.0f}h {:.0f}m'.format(x, y) for (x, y) in
                         zip(df['low'] // 60, df['low'] % 60)]

    # barmode = 'group' if len(df) <= 3 else 'stack'
    barmode = 'group'

    if summary:
        data = [
            go.Bar(
                name='Low',
                x=df.index,
                y=round(df['low'], 1),
                # mode='markers',
                text=df['low_tooltip'],
                hoverinfo='text+x',
                marker={'color': light_blue}
            ),
            go.Bar(
                name='Medium',
                x=df.index,
                y=round(df['medium'], 1),
                # mode='markers',
                text=df['medium_tooltip'],
                hoverinfo='text+x',
                marker={'color': teal}
            ),
            go.Bar(
                name='High',
                x=df.index,
                y=round(df['high'], 1),
                # mode='markers',
                text=df['high_tooltip'],
                hoverinfo='text+x',
                marker={'color': white}
            ),

        ]
        layout = go.Layout(
            height=height,
            transition=dict(duration=transition),
            font=dict(
                color=white,
                size=10,
            ),
            # hoverlabel={'font': {'size': 10}},
            xaxis=dict(
                showline=True,
                color=white,
                showgrid=False,
                showticklabels=True,
                tickvals=df.index,
                tickformat='%b %d',
                range=range,
                rangeselector=dict(
                    # bgcolor='rgb(66, 66, 66)',
                    # bordercolor='#d4d4d4',
                    borderwidth=.5,
                    buttons=buttons,
                    xanchor='center',
                    x=.5,
                    y=.97,
                ),
                rangeslider=dict(
                    visible=True
                ),
            ),
            yaxis=dict(
                showgrid=False,
                showticklabels=False,
                gridcolor='rgb(73, 73, 73)',
                gridwidth=.5,
            ),
            # Set margins to 0, style div sets padding
            margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
            showlegend=False,
            legend=dict(
                x=.5,
                y=-.2,
                xanchor='center',
                orientation="h",
                font=dict(
                    size=10,
                    color=white
                )),
            hovermode='x',
            barmode='stack',
            # autosize=True,
        )
    else:
        data = [
            go.Bar(
                name='Low',
                x=df.index,
                y=round(df['low'], 1),
                # mode='markers',
                text=df['low_tooltip'],
                hoverinfo='text',
                marker={'color': light_blue}
            ),
            go.Bar(
                name='Medium',
                x=df.index,
                y=round(df['medium'], 1),
                # mode='markers',
                text=df['medium_tooltip'],
                hoverinfo='text',
                marker={'color': teal}
            ),
            go.Bar(
                name='High',
                x=df.index,
                y=round(df['high'], 1),
                # mode='markers',
                text=df['high_tooltip'],
                hoverinfo='text',
                marker={'color': white}
            ),

        ]
        layout = go.Layout(
            height=height,
            transition=dict(duration=transition),
            font=dict(
                size=10,
                color=white
            ),
            # hoverlabel={'font': {'size': 10}},
            xaxis=dict(
                showline=True,
                color=white,
                showgrid=False,
                showticklabels=True,
                tickvals=df.index,
                tickformat='%a',

                # Specify range to get rid of auto x-axis padding when using scatter markers
                # range=[pmd.index.max() - timedelta(days=43 + forecast_days),
                #        pmd.index.max()],
            ),
            yaxis=dict(
                showgrid=False,
                showticklabels=False,
                gridcolor='rgb(73, 73, 73)',
                gridwidth=.5,
            ),
            # Set margins to 0, style div sets padding
            margin={'l': 0, 'b': 20, 't': 0, 'r': 0},
            showlegend=False,
            legend=dict(
                x=.5,
                y=-.2,
                xanchor='center',
                orientation="h",
                font=dict(
                    size=10,
                    color=white
                )),
            hovermode='x',
            barmode=barmode,
            # autosize=True,
        )

    clickData = {'points': [{'x': df.index.max(),
                             'y': df['low'].max()},
                            {'y': df['medium'].max()},
                            {'y': df['high'].max()}]}
    figure = {
        'data': data,
        'layout': layout
    }

    return figure, clickData


def generate_oura_activity_content(date):
    # If the date passed is today's date (usually the default on load), grab the max date from db just in case oura cloud does not have current date yet
    if not date or date == datetime.today().date():
        date = app.session.query(func.max(ouraActivitySummary.summary_date))[0][0]

    df = pd.read_sql(
        sql=app.session.query(ouraActivitySummary).filter(ouraActivitySummary.summary_date == date).statement,
        con=engine, index_col='summary_date')

    app.session.remove()

    return [html.Div(className='row', children=[
        html.Div(id='oura-activity-content-kpi-trend', className='col',
                 style={'height': '0%'})
    ]),

            html.Div(id='activity-content-kpi', className='row', children=[
                html.Div(className='col', children=[
                    dbc.Button(id='goal-progress-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['CAL PROGRESS']),
                        html.H6('{} / {}'.format(df['cal_active'].max(), df['target_calories'].max()),
                                className='mb-0')
                    ]),

                    dbc.Button(id='total-burn-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['TOTAL BURN (CAL)']),
                        html.H6('{}'.format(df['cal_total'].max()),
                                className='mb-0')
                    ]),
                    dbc.Button(id='walking-equivalency-button', className='col-lg-4 contentbutton', children=[
                        html.Div(children=['WALKING EQUIV.']),
                        html.H6('{:.1f} mi'.format(df['daily_movement'].max() * 0.000621371),
                                className='mb-0')
                    ])
                ])
            ]),

            html.Div(className='row', children=[
                html.Div(id='daily-movement-day-trend', className='col', children=[
                    html.H6('Daily Movement', style={'marginBottom': '0%'}),
                    html.Div(id='daily-movement-chart-conainer', className='col',
                             children=generate_daily_movement_chart(date)),
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(id='activity-contributors', className='col-lg-12', children=[
                    html.H6('Activity Contributors'),
                    generate_contributor_bar(df=df, id='stay-active',
                                             column_name='score_stay_active',
                                             top_left_title='Stay Active',
                                             top_right_title='{}h {}m'.format(
                                                 df['inactive'].max() // 60,
                                                 (df['inactive'].max() % 60))),
                    generate_contributor_bar(df=df, id='move-every-hour',
                                             column_name='score_move_every_hour',
                                             top_left_title='Move Every Hour',
                                             top_right_title='{:.0f} alerts'.format(
                                                 df['inactivity_alerts'].max())),
                    generate_contributor_bar(df=df, id='meet-daily-goals',
                                             column_name='score_meet_daily_targets',
                                             top_left_title='Meet Daily Goals'),
                    generate_contributor_bar(df=df, id='training-frequency',
                                             column_name='score_training_frequency',
                                             top_left_title='Training Frequency'),
                    generate_contributor_bar(df=df, id='training-volume',
                                             column_name='score_training_volume',
                                             top_left_title='Training Volume'),
                    generate_contributor_bar(df=df, id='recovery-time',
                                             column_name='score_recovery_time',
                                             top_left_title='Recovery Time')

                ])
            ])

            ]


def generate_activity_modal_summary(days=7):
    date = datetime.now().date() - timedelta(days=days)

    df = pd.read_sql(
        sql=app.session.query(ouraActivitySummary.summary_date, ouraActivitySummary.score,
                              ouraActivitySummary.cal_active,
                              ouraActivitySummary.target_calories, ouraActivitySummary.inactive).filter(
            ouraActivitySummary.summary_date > date).statement, con=engine,
        index_col='summary_date')

    app.session.remove()

    df['completion'] = df['cal_active'] / df['target_calories']

    activity_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                      figure={
                                          'data': [go.Bar(
                                              name='Activity',
                                              x=df.index,
                                              y=df['score'],
                                              yaxis='y',
                                              text=df['score'],
                                              hoverinfo='text',
                                              hovertext=['Activity: <b>{:.0f}'.format(x) for x in df['score']],
                                              textposition='auto',
                                              marker={'color': light_blue},
                                          )],
                                          'layout': go.Layout(
                                              height=300,
                                              font=dict(
                                                  size=10,
                                                  color=white
                                              ),
                                              xaxis=dict(
                                                  showline=True,
                                                  color=white,
                                                  showticklabels=True,
                                                  showgrid=False,
                                                  tickvals=df.index,
                                                  tickformat='%a',
                                              ),
                                              yaxis=dict(
                                                  showticklabels=True,
                                                  showgrid=True,
                                                  gridcolor='rgb(66,66,66)',
                                                  color=white,
                                                  tickformat=',d',
                                              ),
                                              showlegend=False,
                                              margin={'l': 40, 'b': 20, 't': 0, 'r': 0},
                                          )
                                      })

    goal_completion_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                             figure={
                                                 'data': [go.Bar(
                                                     name='Goal Completion',
                                                     x=df.index,
                                                     y=df['completion'],
                                                     yaxis='y',
                                                     hoverinfo='text',
                                                     text=['Goal Completion: <b>{:.0f}%'.format(x) for x in
                                                           df['completion'] * 100],
                                                     marker={'color': light_blue},
                                                 )],
                                                 'layout': go.Layout(
                                                     height=300,
                                                     font=dict(
                                                         size=10,
                                                         color=white
                                                     ),
                                                     xaxis=dict(
                                                         showline=True,
                                                         color=white,
                                                         showticklabels=True,
                                                         showgrid=False,
                                                         tickvals=df.index,
                                                         tickformat='%a',
                                                     ),
                                                     yaxis=dict(
                                                         showticklabels=True,
                                                         showgrid=True,
                                                         gridcolor='rgb(66,66,66)',
                                                         color=white,
                                                         tickformat='%',
                                                     ),
                                                     showlegend=False,
                                                     margin={'l': 40, 'b': 20, 't': 0, 'r': 0},
                                                 )
                                             })
    inactive_last_7_graph = dcc.Graph(config={'displayModeBar': False},
                                      figure={
                                          'data': [go.Bar(
                                              name='Inactive Time',
                                              x=df.index,
                                              y=df['inactive'] / 60,
                                              yaxis='y',
                                              hoverinfo='text',
                                              text=['Inactive Time: <b>{}h {}m'.format(x // 60, x % 60) for x in
                                                    df['inactive']],
                                              marker={'color': light_blue},
                                          )],
                                          'layout': go.Layout(
                                              height=300,
                                              font=dict(
                                                  size=10,
                                                  color=white
                                              ),
                                              xaxis=dict(
                                                  showline=True,
                                                  color=white,
                                                  showticklabels=True,
                                                  showgrid=False,
                                                  tickvals=df.index,
                                                  tickformat='%a',
                                              ),
                                              yaxis=dict(
                                                  showticklabels=True,
                                                  showgrid=True,
                                                  gridcolor='rgb(66,66,66)',
                                                  color=white,
                                                  tickformat=',d',
                                              ),
                                              showlegend=False,
                                              margin={'l': 40, 'b': 20, 't': 0, 'r': 0},
                                          )
                                      })

    return [
        html.Div(id='activity-modal-last-7-container', className='row align-items-center text-center mb-2',
                 style={'whiteSpace': 'normal'}, children=[
                html.Div(id='activity-score-last-7', className='col-lg-4', children=[
                    html.Div(id='activity-score-last-7-title',
                             children=[
                                 html.P('Your average activity score for the last 7 days is {:.0f}'.format(
                                     df['score'].mean()))
                             ]),
                    html.Div(id='activity-score-last-7-chart',
                             children=[activity_last_7_graph]
                             )
                ]),
                html.Div(id='goal-completion-last-7', className='col-lg-4', children=[
                    html.Div(id='goal-completion-last-7-title',
                             children=[
                                 html.P('Your average activity goal completion for the last 7 days is {:.0f}%'.format(
                                     df['completion'].mean() * 100))
                             ]),
                    html.Div(id='goal-completion-last-7-chart',
                             children=[goal_completion_last_7_graph]
                             )
                ]),
                html.Div(id='inactive-last-7', className='col-lg-4', children=[
                    html.Div(id='inactive-last-7-title',
                             children=[
                                 html.P(
                                     'Your daily average inactive time over the last 7 days is {:.0f}h {:.0f}m'.format(
                                         df['inactive'].mean() // 60, df['inactive'].mean() % 60))
                             ]),
                    html.Div(id='inactive-last-7-chart',
                             children=[inactive_last_7_graph]
                             )
                ]),
            ]),

        html.Div(className='row', children=[
            html.Div(id='activity-score-correlations', className='col-lg-6', children=[
                html.Div(id='activity-score-correlation-title', className='col-lg-12 text-center',
                         children=[html.P('Activity Score Correlations (L6M)')]),
                html.Div(id='activity-score-correlation-chart', className='col-lg-12',
                         children=[generate_correlation_table(10, 'Activity score', 180)]
                         )
            ]),

            html.Div(className='col-lg-6', children=[
                html.Div(className='row align-items-center text-center', children=[
                    html.Div(id='activity-groupby-controls', className='col-lg-12 mb-2 mt-2', children=[
                        dbc.Button('Year', id='activity-year-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Month', id='activity-month-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Week', id='activity-week-button', n_clicks=0, size='sm', className='mr-3'),
                        dbc.Button('Day', id='activity-day-button', size='sm')
                    ]),
                ]),

                html.Div(className='row', children=[
                    html.Div(className='col-lg-12', children=[
                        dbc.Spinner(color='info', children=[

                            dcc.Graph(id='activity-modal-full-chart',
                                      config={'displayModeBar': False}
                                      ),

                        ]),
                    ]),
                ]),
            ])

        ])

    ]


# Callbacks to update donuts when new week ending selected
@app.callback(
    Output('kpi-shelf', 'children'),
    [Input('week-ending', 'children')])
def update_kpi_shelf(date):
    return update_kpis(datetime.strptime(date, '%A %b %d, %Y'))


# Hide forward button if on current week, show if on previous week
@app.callback(
    Output('forward-week', 'style'),
    [Input('week-ending', 'children')]
)
def toggle_forward_arrow_display(week_ending):
    if calc_next_saturday(datetime.strptime(week_ending, '%A %b %d, %Y')) == calc_next_saturday(get_max_week_ending()):
        return {'color': 'rgba(0,0,0,0)', 'backgroundColor': 'rgba(0,0,0,0)',
                'border': '0'}
    else:
        return {'display': 'inline-block', 'backgroundColor': 'rgba(0,0,0,0)', 'border': '0'}


# Hide back button if on min week, show otherwise
@app.callback(
    Output('back-week', 'style'),
    [Input('week-ending', 'children')]
)
def toggle_back_arrow_display(week_ending):
    min_saturday = calc_next_saturday(pd.to_datetime(app.session.query(func.min(ouraSleepSummary.report_date))[0][0]))

    app.session.remove()
    if calc_next_saturday(datetime.strptime(week_ending, '%A %b %d, %Y')) == min_saturday:
        return {'color': 'rgba(0,0,0,0)', 'backgroundColor': 'rgba(0,0,0,0)',
                'border': '0'}
    else:
        return {'display': 'inline-block', 'backgroundColor': 'rgba(0,0,0,0)', 'border': '0'}


# Week Cycling callback
@app.callback(
    Output('week-ending', 'children'),
    [Input('back-week', 'n_clicks'),
     Input('forward-week', 'n_clicks')],
    [State('week-ending', 'children')]
)
def cycle_week(back_week_n_clicks, forward_week_n_clicks, current_week_selection):
    ctx = dash.callback_context
    if not ctx.triggered:
        return datetime.strftime(calc_next_saturday(get_max_week_ending()), '%A %b %d, %Y')
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    min_saturday = calc_next_saturday(pd.to_datetime(app.session.query(func.min(ouraSleepSummary.report_date))[0][0]))

    app.session.remove()

    if button_id == 'back-week':
        # If going earlier than min week, stay on current week
        if datetime.strptime(current_week_selection, '%A %b %d, %Y').date() == min_saturday:
            return current_week_selection
        else:
            return datetime.strftime(datetime.strptime(current_week_selection, '%A %b %d, %Y') - timedelta(days=7),
                                     '%A %b %d, %Y')
    # If going past current week, stay on current week
    elif datetime.strptime(current_week_selection, '%A %b %d, %Y').date() + timedelta(days=7) > calc_next_saturday(
            get_max_week_ending()):
        return current_week_selection
    else:
        return datetime.strftime(datetime.strptime(current_week_selection, '%A %b %d, %Y') + timedelta(days=7),
                                 '%A %b %d, %Y')


# Update Header containers
@app.callback(
    [Output('sleep-trend', 'figure'),
     Output('sleep-trend', 'clickData'),
     Output('readiness-scatter', 'figure'),
     Output('readiness-scatter', 'clickData'),
     Output('activity-bars', 'figure'),
     Output('activity-bars', 'clickData')
     ],
    [Input('week-ending', 'children')]
)
def update_header_containers(week_ending):
    date = datetime.strptime(week_ending, '%A %b %d, %Y')
    date -= timedelta(days=7)
    sleep_figure, sleep_clickData = generate_oura_sleep_header_chart(date)
    readiness_figure, readiness_clickData = generate_oura_readiness_header_chart(date)
    activity_figure, activity_clickData = generate_oura_activity_header_chart(date)
    return sleep_figure, sleep_clickData, readiness_figure, readiness_clickData, activity_figure, activity_clickData


# Sleep content kpi trend action
@app.callback(
    [Output('oura-sleep-content-kpi-trend', 'children'),
     Output('oura-sleep-content-kpi-trend', 'style'),
     Output('current-sleep-content-trend', 'children')],
    [Input('total-sleep-time-button', 'n_clicks'),
     Input('total-time-in-bed-button', 'n_clicks'),
     Input('sleep-efficiency-button', 'n_clicks'), ],
    [State('current-sleep-content-trend', 'children')]
)
def sleep_content_kpi_trend(total_sleep_time, total_time_in_bed, sleep_efficiency, current_trend):
    # Get latest kpi that was selected
    ctx = dash.callback_context
    latest_dict = {'total-sleep-time-button': 'total', 'total-time-in-bed-button': 'duration',
                   'sleep-efficiency-button': 'efficiency'}
    if len(ctx.triggered) == 1:
        latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]
        if current_trend == latest:
            return [], {'display': 'none'}, []
        else:
            return generate_content_kpi_trend('sleep', latest), {'display': 'inherit'}, latest
    else:
        return [], {'display': 'none'}, []


# Readiness content kpi trend action
@app.callback(
    [Output('oura-readiness-content-kpi-trend', 'children'),
     Output('oura-readiness-content-kpi-trend', 'style'),
     Output('current-readiness-content-trend', 'children')],
    [Input('resting-heart-rate-button', 'n_clicks'),
     Input('heart-rate-variability-button', 'n_clicks'),
     Input('body-temperature-button', 'n_clicks'), ],
    [State('current-readiness-content-trend', 'children')]
)
def readiness_content_kpi_trend(resting_heart_rate, heart_rate_variability, body_temperature, current_trend):
    # Get latest kpi that was selected
    ctx = dash.callback_context
    latest_dict = {'resting-heart-rate-button': 'hr_lowest', 'heart-rate-variability-button': 'rmssd',
                   'body-temperature-button': 'temperature_delta'}
    if len(ctx.triggered) == 1:
        latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]
        if current_trend == latest:
            return [], {'display': 'none'}, []
        else:
            return generate_content_kpi_trend('sleep', latest), {'display': 'inherit'}, latest
    else:
        return [], {'display': 'none'}, []


# Activity content kpi trend action
@app.callback(
    [Output('oura-activity-content-kpi-trend', 'children'),
     Output('oura-activity-content-kpi-trend', 'style'),
     Output('current-activity-content-trend', 'children')],
    [Input('goal-progress-button', 'n_clicks'),
     Input('total-burn-button', 'n_clicks'),
     Input('walking-equivalency-button', 'n_clicks'), ],
    [State('current-activity-content-trend', 'children')]

)
def activity_content_kpi_trend(goal_progress, total_burn, walking_equivalency, current_trend):
    ctx = dash.callback_context
    latest_dict = {'goal-progress-button': 'cal_active', 'total-burn-button': 'cal_total',
                   'walking-equivalency-button': 'daily_movement'}
    if len(ctx.triggered) == 1:
        latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]
        if current_trend == latest:
            return [], {'display': 'none'}, []
        else:
            return generate_content_kpi_trend('activity', latest), {'display': 'inherit'}, latest
    else:
        return [], {'display': 'none'}, []


@app.callback(
    Output('last-chart-clicked', 'children'),
    [Input('sleep-trend', 'clickData'),
     Input('readiness-scatter', 'clickData'),
     Input('activity-bars', 'clickData')]
)
def update_last_clicked(sleepClick, readinessClick, activityClick):
    ctx = dash.callback_context
    latest_dict = {'sleep-trend': 'sleep', 'readiness-scatter': 'readiness', 'activity-bars': 'activity'}
    if not ctx.triggered:
        date = datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S')
    else:
        latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]
        if latest == 'sleep':
            date = sleepClick['points'][0]['x']
        elif latest == 'readiness':
            date = readinessClick['points'][0]['x']
        elif latest == 'activity':
            date = activityClick['points'][0]['x']

    if len(date) > 10:
        date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S").date()

    return str(date)


# Show exclamations when dates not aligned
@app.callback(
    Output('sleep-exclamation', 'style'),
    [Input('sleep-date', 'children')]
)
def show_sleep_exclamation(dummy):
    show = {'display': 'inline-block', 'fontSize': '1rem', 'color': orange, 'paddingLeft': '1%'}
    hide = {'display': 'none'}

    max_sleep_date = app.session.query(func.max(ouraSleepSummary.report_date)).first()[0]
    max_readiness_date = app.session.query(func.max(ouraReadinessSummary.report_date)).first()[0]
    max_activity_date = app.session.query(func.max(ouraActivitySummary.summary_date)).first()[0]

    app.session.remove()
    max_date = max([max_sleep_date, max_readiness_date, max_activity_date])
    sleep_style = show if max_sleep_date != max_date else hide

    return sleep_style


# Show exclamations when dates not aligned
@app.callback(
    Output('readiness-exclamation', 'style'),
    [Input('readiness-date', 'children')]
)
def show_readiness_exclamation(dummy):
    show = {'display': 'inline-block', 'fontSize': '1rem', 'color': orange, 'paddingLeft': '1%'}
    hide = {'display': 'none'}

    max_sleep_date = app.session.query(func.max(ouraSleepSummary.report_date)).first()[0]
    max_readiness_date = app.session.query(func.max(ouraReadinessSummary.report_date)).first()[0]
    max_activity_date = app.session.query(func.max(ouraActivitySummary.summary_date)).first()[0]

    app.session.remove()
    max_date = max([max_sleep_date, max_readiness_date, max_activity_date])
    readiness_style = show if max_readiness_date != max_date else hide

    return readiness_style


# Show exclamations when dates not aligned
@app.callback(
    Output('activity-exclamation', 'style'),
    [Input('activity-date', 'children')]
)
def show_activity_exclamation(dummy):
    show = {'display': 'inline-block', 'fontSize': '1rem', 'color': orange, 'paddingLeft': '1%'}
    hide = {'display': 'none'}

    max_sleep_date = app.session.query(func.max(ouraSleepSummary.report_date)).first()[0]
    max_readiness_date = app.session.query(func.max(ouraReadinessSummary.report_date)).first()[0]
    max_activity_date = app.session.query(func.max(ouraActivitySummary.summary_date)).first()[0]

    app.session.remove()
    max_date = max([max_sleep_date, max_readiness_date, max_activity_date])
    activity_style = show if max_activity_date != max_date else hide

    return activity_style


# Sleep content click data action
@app.callback(
    [Output('sleep-date', 'children'),
     Output('sleep-kpi', 'children'),
     Output('oura-sleep-content', 'children')],
    [Input('last-chart-clicked', 'children')],

)
def update_oura_sleep_contents(date):
    date = pd.to_datetime(date).date()
    date_title, star, score = generate_oura_sleep_header_kpi(date)
    if star:
        kpi_score = [html.I(className='fa fa-star align-middle mr-1', style={'fontSize': '25%'}),
                     score,
                     html.I(className='fa fa-star align-middle ml-1', style={'fontSize': '25%'})]
    else:
        kpi_score = score
    return date_title, kpi_score, generate_oura_sleep_content(date)


# Readiness content click data action
@app.callback(
    [Output('readiness-date', 'children'),
     Output('readiness-kpi', 'children'),
     Output('oura-readiness-content', 'children')],
    [Input('last-chart-clicked', 'children')]
)
def update_oura_readiness_contents(date):
    date = pd.to_datetime(date).date()
    date_title, star, score = generate_oura_readiness_header_kpi(date)
    if star:
        kpi_score = [html.I(className='fa fa-star align-middle mr-1', style={'fontSize': '25%'}),
                     score,
                     html.I(className='fa fa-star align-middle ml-1', style={'fontSize': '25%'})]
    else:
        kpi_score = score
    return date_title, kpi_score, generate_oura_readiness_content(date)


# Activity content click data action
@app.callback(
    [Output('activity-date', 'children'),
     Output('activity-kpi', 'children'),
     Output('oura-activity-content', 'children')],
    [Input('last-chart-clicked', 'children')]
)
def update_oura_activity_contents(date):
    date = pd.to_datetime(date).date()
    date_title, star, score = generate_oura_activity_header_kpi(date)
    if star:
        kpi_score = [html.I(className='fa fa-star align-middle mr-1', style={'fontSize': '25%'}),
                     score,
                     html.I(className='fa fa-star align-middle ml-1', style={'fontSize': '25%'})]
    else:
        kpi_score = score
    return date_title, kpi_score, generate_oura_activity_content(date)


# Sleep Summary Modal Toggle
@app.callback(
    Output("oura-sleep-summary-modal", "is_open"),
    [Input("sleep-kpi-summary-button", "n_clicks"), Input("close-sleep-summary-modal-button", "n_clicks")],
    [State("oura-sleep-summary-modal", "is_open")]
)
def toggle_sleep_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


# Sleep Summary Modal Content
@app.callback(
    Output("oura-sleep-summary-modal-body", "children"),
    [Input("oura-sleep-summary-modal", "is_open")]
)
def sleep_modal_content(is_open):
    if is_open:
        return generate_sleep_modal_summary()
    return []


# Sleep Group By chart
@app.callback([Output("sleep-modal-full-chart", "figure"),
               Output('sleep-year-button', 'style'),
               Output('sleep-month-button', 'style'),
               Output('sleep-week-button', 'style'),
               Output('sleep-day-button', 'style')],
              [Input("oura-sleep-summary-modal", "is_open"),
               Input('sleep-year-button', 'n_clicks'),
               Input('sleep-month-button', 'n_clicks'),
               Input('sleep-week-button', 'n_clicks'),
               Input('sleep-day-button', 'n_clicks')]
              )
def sleep_modal_chart(is_open, year_n_clicks, month_n_clicks, week_n_clicks, day_n_clicks):
    style = {'Y': {'marginRight': '1%'}, 'M': {'marginRight': '1%'}, 'W': {'marginRight': '1%'},
             'D': {'marginRight': '1%'}}
    if is_open:
        ctx = dash.callback_context
        latest_dict = {'sleep-year-button': 'Y', 'sleep-month-button': 'M', 'sleep-week-button': 'W',
                       'sleep-day-button': 'D'}
        if not ctx.triggered:
            latest = 'W'
        else:
            latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]

        style[latest] = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}

        figure, clickData = generate_oura_sleep_header_chart(date=None, summary=True, resample=latest)
        return figure, style['Y'], style['M'], style['W'], style['D']
    else:
        return {}, style['Y'], style['M'], style['W'], style['D']


# Readiness Summary Modal Toggle
@app.callback(
    Output("oura-readiness-summary-modal", "is_open"),
    [Input("readiness-kpi-summary-button", "n_clicks"), Input("close-readiness-summary-modal-button", "n_clicks")],
    [State("oura-readiness-summary-modal", "is_open")]
)
def toggle_readiness_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


# Readiness Summary Modal Content
@app.callback(
    Output("oura-readiness-summary-modal-body", "children"),
    [Input("oura-readiness-summary-modal", "is_open")]
)
def readiness_modal_content(is_open):
    if is_open:
        return generate_readiness_modal_summary()
    return []


# Readiness Group By chart
@app.callback([Output("readiness-modal-full-chart", "figure"),
               Output('readiness-year-button', 'style'),
               Output('readiness-month-button', 'style'),
               Output('readiness-week-button', 'style'),
               Output('readiness-day-button', 'style')],
              [Input("oura-readiness-summary-modal", "is_open"),
               Input('readiness-year-button', 'n_clicks'),
               Input('readiness-month-button', 'n_clicks'),
               Input('readiness-week-button', 'n_clicks'),
               Input('readiness-day-button', 'n_clicks')]
              )
def readiness_modal_chart(is_open, year_n_clicks, month_n_clicks, week_n_clicks, day_n_clicks):
    style = {'Y': {'marginRight': '1%'}, 'M': {'marginRight': '1%'}, 'W': {'marginRight': '1%'},
             'D': {'marginRight': '1%'}}
    if is_open:
        ctx = dash.callback_context
        latest_dict = {'readiness-year-button': 'Y', 'readiness-month-button': 'M', 'readiness-week-button': 'W',
                       'readiness-day-button': 'D'}
        if not ctx.triggered:
            latest = 'W'
        else:
            latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]

        style[latest] = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
        figure, clickData = generate_oura_readiness_header_chart(date=None, summary=True, resample=latest)
        return figure, style['Y'], style['M'], style['W'], style['D']
    else:
        return {}, style['Y'], style['M'], style['W'], style['D']


# Activity Summary Modal Toggle
@app.callback(
    Output("oura-activity-summary-modal", "is_open"),
    [Input("activity-kpi-summary-button", "n_clicks"), Input("close-activity-summary-modal-button", "n_clicks")],
    [State("oura-activity-summary-modal", "is_open")]
)
def toggle_readiness_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


# Activity Summary Modal Content
@app.callback(
    Output("oura-activity-summary-modal-body", "children"),
    [Input("oura-activity-summary-modal", "is_open")]
)
def readiness_modal_content(is_open):
    if is_open:
        return generate_activity_modal_summary()
    return []


# Activity Group By chart
@app.callback([Output("activity-modal-full-chart", "figure"),
               Output('activity-year-button', 'style'),
               Output('activity-month-button', 'style'),
               Output('activity-week-button', 'style'),
               Output('activity-day-button', 'style')],
              [Input("oura-activity-summary-modal", "is_open"),
               Input('activity-year-button', 'n_clicks'),
               Input('activity-month-button', 'n_clicks'),
               Input('activity-week-button', 'n_clicks'),
               Input('activity-day-button', 'n_clicks')]
              )
def activity_modal_chart(is_open, year_n_clicks, month_n_clicks, week_n_clicks, day_n_clicks):
    style = {'Y': {'marginRight': '1%'}, 'M': {'marginRight': '1%'}, 'W': {'marginRight': '1%'},
             'D': {'marginRight': '1%'}}
    if is_open:
        ctx = dash.callback_context
        latest_dict = {'activity-year-button': 'Y', 'activity-month-button': 'M', 'activity-week-button': 'W',
                       'activity-day-button': 'D'}
        if not ctx.triggered:
            latest = 'W'
        else:
            latest = latest_dict[ctx.triggered[0]['prop_id'].split('.')[0]]

        style[latest] = {'marginRight': '1%', 'color': '#64D9EC', 'borderColor': '#64D9EC'}
        figure, clickData = generate_oura_activity_header_chart(date=None, summary=True, resample=latest)
        return figure, style['Y'], style['M'], style['W'], style['D']
    else:
        return {}, style['Y'], style['M'], style['W'], style['D']


def get_layout(**kwargs):
    # Oura data required for home page
    if not oura_credentials_supplied:
        return html.H1('Please provide oura credentials in config', className='text-center')
    else:
        return html.Div(className='align-items-center text-center', children=[
            html.Div(id='week-selection', className='row mt-2 mb-2',
                     children=[
                         html.Div(className='col-lg-12', children=[
                             dbc.Card([
                                 dbc.CardBody(style={'paddingTop': '0', 'paddingBottom': '0'}, children=[

                                     html.Div(className='col-lg-12', children=[
                                         html.P('Week Ending', className='mb-0',
                                                style={'color': teal, 'fontSize': '1rem'}),
                                     ]),
                                     html.Div(className='col-lg-12', children=[
                                         html.Button(id='back-week', className='fa fa-arrow-left mr-2', n_clicks=0),
                                         html.H4(id='week-ending', className='d-inline-block'),
                                         html.Button(id='forward-week', className='fa fa-arrow-right ml-2'),
                                     ])
                                 ])
                             ])
                         ])
                     ]),

            dbc.Spinner(color='info', children=[

                html.Div(id='kpi-shelf', className='row mt-2 mb-2')
            ]
                        ),

            html.Div(id='oura-containers', className='row', children=[
                dbc.Modal(id="oura-sleep-summary-modal", centered=True, fade=False, autoFocus=True, backdrop=True,
                          size='xl',
                          children=[
                              dbc.ModalHeader("Sleep Summary"),
                              dbc.ModalBody(id="oura-sleep-summary-modal-body"),
                              dbc.ModalFooter(
                                  dbc.Button("Close", id="close-sleep-summary-modal-button", size='sm', color='primary',
                                             className="ml-auto", n_clicks=0)
                              ),
                          ]),

                dbc.Modal(id="oura-readiness-summary-modal", centered=True, fade=False, autoFocus=True, backdrop=True,
                          size='xl',
                          children=[
                              dbc.ModalHeader("Readiness Summary"),
                              dbc.ModalBody(html.Div(id="oura-readiness-summary-modal-body")),
                              dbc.ModalFooter(
                                  dbc.Button("Close", id="close-readiness-summary-modal-button", size='sm',
                                             color='primary', className="ml-auto", n_clicks=0)
                              ),
                          ]),

                dbc.Modal(id="oura-activity-summary-modal", centered=True, fade=False, autoFocus=True, backdrop=True,
                          size='xl',
                          children=[
                              dbc.ModalHeader("Activity Summary"),
                              dbc.ModalBody(html.Div(id="oura-activity-summary-modal-body")),
                              dbc.ModalFooter(
                                  dbc.Button("Close", id="close-activity-summary-modal-button", size='sm',
                                             color='primary', className="ml-auto", n_clicks=0)
                              ),
                          ]),

                html.Div(className='col-lg-4 align-items-center text-center', children=[
                    dbc.Card([
                        dbc.CardBody(id='oura-sleep-container',
                                     children=[
                                         html.Div(className='row', children=[
                                             html.Div(id='oura-sleep-kpi', className='col-lg-12',
                                                      children=[
                                                          html.P(id='sleep-date', className='mb-0 d-inline-block',
                                                                 style={'fontSize': '1rem', 'color': teal}),
                                                          html.I(id='sleep-exclamation',
                                                                 className='fa fa-exclamation-circle',
                                                                 style={'display': 'none'}),
                                                          dbc.Tooltip(
                                                              "Latest sleep data not yet posted to Oura cloud",
                                                              target='sleep-exclamation'),

                                                      ])
                                         ]),

                                         html.Div(className='row', children=[
                                             dbc.Button(id='sleep-kpi-summary-button', className='col-4 offset-4',
                                                        color='primary', n_clicks=0, size='sm',
                                                        style={'height': '100%', 'text-transform': 'inherit'},
                                                        children=[
                                                            html.H6('Sleep', style={'lineHeight': 1},
                                                                    className='col mb-0'),
                                                            html.H2(id='sleep-kpi', className='col mb-0',
                                                                    style={'lineHeight': 1})
                                                        ]),
                                             dbc.Tooltip('Click for Sleep summary', target='sleep-kpi-summary-button'),
                                         ]),
                                         html.Div(className='row', children=[
                                             dcc.Graph(id='sleep-trend', className='col-lg-12',
                                                       config={'displayModeBar': False}
                                                       ),

                                             html.Div(id='oura-sleep-header', className='col-lg-12',
                                                      # style={'height': '20%'}
                                                      )
                                         ]),
                                         html.Div(className='row', children=[
                                             html.Div(id='oura-sleep-content', className='col-lg-12',
                                                      style={'height': '65%'})])
                                     ]),

                    ])
                ]),

                html.Div(className='col-lg-4 align-items-center text-center', children=[
                    dbc.Card([
                        dbc.CardBody(id='oura-readiness-container',
                                     children=[
                                         html.Div(className='row', children=[
                                             html.Div(id='oura-readiness-kpi', className='col-lg-12',
                                                      children=[

                                                          html.P(id='readiness-date', className='mb-0 d-inline-block',
                                                                 style={'fontSize': '1rem', 'color': teal}),
                                                          html.I(id='readiness-exclamation',
                                                                 className='fa fa-exclamation-circle',
                                                                 style={'display': 'none'}),
                                                          dbc.Tooltip(
                                                              "Latest readiness data not yet posted to Oura cloud",
                                                              target='readiness-exclamation'),

                                                      ])
                                         ]),

                                         html.Div(className='row', children=[
                                             dbc.Button(id='readiness-kpi-summary-button', className='col-4 offset-4',
                                                        color='primary', n_clicks=0, size='sm',
                                                        style={'height': '100%', 'text-transform': 'inherit'},
                                                        children=[
                                                            html.H6('Readiness', style={'lineHeight': 1},
                                                                    className='col mb-0'),
                                                            html.H2(id='readiness-kpi', className='col mb-0',
                                                                    style={'lineHeight': 1})
                                                        ]),
                                             dbc.Tooltip('Click for Readiness summary',
                                                         target='readiness-kpi-summary-button'),
                                         ]),
                                         html.Div(className='row', children=[
                                             dcc.Graph(id='readiness-scatter', className='col-lg-12',
                                                       config={'displayModeBar': False},
                                                       )

                                         ]),
                                         html.Div(className='row', children=[
                                             html.Div(id='oura-readiness-content', className='col-lg-12',
                                                      style={'height': '65%'})])
                                     ]),

                    ])
                ]),

                html.Div(className='col-lg-4 align-items-center text-center', children=[
                    dbc.Card([
                        dbc.CardBody(id='oura-activity-container',
                                     children=[
                                         html.Div(className='row', children=[
                                             html.Div(id='oura-activity-kpi', className='col-lg-12',
                                                      children=[

                                                          html.P(id='activity-date', className='mb-0 d-inline-block',
                                                                 style={'fontSize': '1rem', 'color': teal}),
                                                          html.I(id='activity-exclamation',
                                                                 className='fa fa-exclamation-circle',
                                                                 style={'display': 'none'}),
                                                          dbc.Tooltip(
                                                              "Latest activity data not yet posted to Oura cloud",
                                                              target='activity-exclamation'),

                                                      ])
                                         ]),

                                         html.Div(className='row', children=[
                                             dbc.Button(id='activity-kpi-summary-button', className='col-4 offset-4',
                                                        color='primary', n_clicks=0, size='sm',
                                                        style={'height': '100%', 'text-transform': 'inherit'},
                                                        children=[
                                                            html.H6('Activity', style={'lineHeight': 1},
                                                                    className='col mb-0'),
                                                            html.H2(id='activity-kpi', className='col mb-0',
                                                                    style={'lineHeight': 1})
                                                        ]),
                                             dbc.Tooltip('Click for Activity summary',
                                                         target='activity-kpi-summary-button'),
                                         ]),
                                         html.Div(className='row', children=[
                                             dcc.Graph(id='activity-bars', className='col-lg-12',
                                                       config={'displayModeBar': False},
                                                       )

                                         ]),
                                         html.Div(className='row', children=[
                                             html.Div(id='oura-activity-content', className='col-lg-12',
                                                      style={'height': '65%'})])
                                     ]),

                    ])
                ]),

                # Dummy divs for controlling which over happened last to update all containers
                html.Div(id='last-chart-clicked', style={'display': 'none'}),
                # Dummy divs for controlling show/hide of content kpi trend
                html.Div(id='current-sleep-content-trend', style={'display': 'none'}),
                html.Div(id='current-readiness-content-trend', style={'display': 'none'}),
                html.Div(id='current-activity-content-trend', style={'display': 'none'})
            ])
        ])
