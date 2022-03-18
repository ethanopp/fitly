import dash
from datetime import datetime, timedelta
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_daq as daq
import dash_html_components as html
import dash_table
import numpy as np
import pandas as pd
import plotly.graph_objs as go
from dash.dependencies import Input, Output, State
from sqlalchemy import or_, delete, extract
from ..app import app
from ..api.sqlalchemy_declarative import athlete, stravaSummary, stravaSamples, workoutStepLog, ouraSleepSummary, \
    strydSummary, ouraReadinessSummary, annotations
from ..api.database import engine
from ..utils import utc_to_local, config, oura_credentials_supplied, stryd_credentials_supplied, \
    peloton_credentials_supplied
from ..pages.power import power_curve, zone_chart
import re
import json
import operator
import scipy

transition = int(config.get('dashboard', 'transition'))

ctl_color = 'rgb(171, 131, 186)'
atl_color = 'rgb(245,226,59)'
tsb_color = 'rgb(193, 125, 55)'
tsb_fill_color = 'rgba(193, 125, 55, .5)'
ftp_color = 'rgb(100, 217, 236)'
white = config.get('oura', 'white')
teal = config.get('oura', 'teal')
light_blue = config.get('oura', 'light_blue')
dark_blue = config.get('oura', 'dark_blue')
orange = config.get('oura', 'orange')
orange_faded = 'rgba(217,100,43,.75)'

# Oura readiness ranges for recommendation
oura_high_threshold = 85
oura_med_threshold = 77
oura_low_threshold = 70


def get_layout(**kwargs):
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    pmc_switch_settings = json.loads(athlete_info.pmc_switch_settings)
    use_run_power = True if athlete_info.use_run_power else False
    use_cycle_power = True if athlete_info.use_cycle_power else False
    use_power = True if use_run_power or use_cycle_power else False
    app.session.remove()
    return html.Div([
        # Dummy div for simultaneous callbacks on page load
        dbc.Modal(id="annotation-modal", centered=True, autoFocus=True, fade=False, backdrop='static', size='xl',
                  children=[
                      dbc.ModalHeader(id='annotation-modal-header', children=['Annotations']),
                      dbc.ModalBody(id='annotation-modal-body', className='align-items-center text-center',
                                    children=[
                                        html.Div(className='col-lg-12 mb-2', style={'padding': 0},
                                                 children=[
                                                     html.Div(id='annotation-table-container', className='col mb-2',
                                                              style={'padding': 0},
                                                              children=[html.Div(id='annotation-table')]),
                                                     dbc.Button('Add Row', id='annotation-add-rows-button',
                                                                color='primary', size='sm', n_clicks=0)
                                                 ]),
                                        html.Div(id='annotation-save-container', className='col',
                                                 children=[
                                                     html.H6('Enter admin password to save changes',
                                                             className='col d-inline-block'),

                                                     html.Div(className='col mb-2', children=[
                                                         dbc.Input(id='annotation-password', bs_size="sm",
                                                                   type='password', placeholder='Password', value=''),
                                                     ]),

                                                     html.Div(className='col mb-2', children=[
                                                         dbc.Button("Save",
                                                                    id="save-close-annotation-modal-button",
                                                                    color='primary', size='sm', n_clicks=0),
                                                         html.Div(id='annotation-save-status')
                                                     ])
                                                 ])]),

                      dbc.ModalFooter(
                          dbc.Button("Close", id="close-annotation-modal-button", color='primary', size='sm',
                                     href=f'/performance?refresh={str(datetime.now())}')
                      ),
                  ]),
        dbc.Modal(id="activity-modal", is_open=False, centered=True, autoFocus=True, fade=False, backdrop='static',
                  size='xl',
                  children=[
                      dbc.ModalHeader(id='activity-modal-header'),
                      dbc.ModalBody([
                          html.Div([
                              dbc.Spinner(color='info', children=[
                                  html.Div(id='activity-modal-body', className='row mt-2 mb-2', children=[
                                      html.Div(className='col-lg-10', children=[
                                          html.Div(className='row', children=[
                                              html.Div(className='col-lg-12', children=[
                                                  dbc.Card(color='dark', children=[
                                                      dbc.CardHeader(html.H4('Activity Stream')),
                                                      dbc.CardBody([
                                                          html.Div(className='row', children=[
                                                              html.Div(id='modal-workout-summary',
                                                                       className='col-lg-3'),
                                                              html.Div(id='modal-workout-trends', className='col-lg-9'),
                                                          ])
                                                      ])
                                                  ])
                                              ])
                                          ])
                                      ]),

                                      html.Div(id='modal-workout-stats', className='col-lg-2',
                                               style={'height': '100%'}),
                                  ]),
                              ]),
                          ]),

                          html.Div([
                              dbc.Spinner(color='info', children=[
                                  html.Div(id="activity-modal-body-2", className='row mt-2 mb-2',
                                           children=[
                                               html.Div(className='col-lg-6' if use_power else 'col-lg-12', children=[
                                                   dbc.Card(color='dark', children=[
                                                       dbc.CardHeader(id='modal-zone-title'),
                                                       dbc.CardBody(id='modal-zones')
                                                   ])
                                               ]),
                                               html.Div(className='col-lg-6',
                                                        style={} if use_power else {'display': 'none'}, children=[
                                                       dbc.Card(id='modal-power-curve-card', color='dark', children=[
                                                           dbc.CardHeader(html.H4('Power Curve')),
                                                           dbc.CardBody([
                                                               dcc.Graph(id='modal-power-curve-chart',
                                                                         config={'displayModeBar': False},
                                                                         style={'height': '100%'})
                                                           ]
                                                           )
                                                       ])
                                                   ]),

                                           ])
                              ]),
                          ]),
                      ]),

                      dbc.ModalFooter(
                          dbc.Button("Close", id="close-activity-modal-button", size='sm', color='primary', n_clicks=0)
                      ),
                  ]),
        html.Div(className='row align-items-start text-center mt-2 mb-2', children=[
            html.Div(id='pmd-header-and-chart', className='col-lg-8',
                     children=[
                         dbc.Card([
                             dbc.CardHeader([
                                 html.Div(id='pmd-kpi')
                             ]),
                             dbc.CardBody([

                                 # Start Graph #

                                 html.Div(className='row', children=[

                                     html.Div(id='daily-recommendations',  # Populated by callback
                                              className='col-lg-3' if oura_credentials_supplied else '',
                                              style={'display': 'none' if not oura_credentials_supplied else 'normal'}),

                                     # PMC Chart
                                     dcc.Graph(id='pm-chart',
                                               className='col-lg-8 mr-0 ml-0' if oura_credentials_supplied else 'col-lg-11 mr-0 ml-0',
                                               # Populated by callback
                                               style={'height': '100%'},
                                               config={'displayModeBar': False}),
                                     # Switches
                                     html.Div(id='pmc-controls', className='col-lg-1 text-left',
                                              style={'display': 'flex', 'justifyContent': 'space-between'}, children=[
                                             html.Div(className='row', children=[
                                                 html.Div(className='col-lg-12 col-3',
                                                          style={'padding': '0', 'alignSelf': 'center'},
                                                          children=[
                                                              html.Button(id="open-annotation-modal-button",
                                                                          className='fa fa-comment-alt',
                                                                          n_clicks=0,
                                                                          style={'fontSize': '1.5rem',
                                                                                 'display': 'inline-block',
                                                                                 'vertical-align': 'middle',
                                                                                 'border': '0'}),
                                                          ]),
                                                 dbc.Tooltip(
                                                     'Chart Annotations',
                                                     target="open-annotation-modal-button"),

                                                 html.Div(id='run-pmc',
                                                          className='col-lg-12 col-3 align-items-center',
                                                          style={'padding': '0', 'alignSelf': 'center'},
                                                          children=[
                                                              daq.BooleanSwitch(
                                                                  id='run-pmc-switch',
                                                                  on=True,
                                                                  style={'display': 'inline-block',
                                                                         'vertical-align': 'middle'}
                                                              ),
                                                              html.I(id='run-pmc-icon', className='fa fa-running',
                                                                     style={'fontSize': '1.5rem',
                                                                            'display': 'inline-block',
                                                                            'vertical-align': 'middle',
                                                                            'paddingLeft': '.25vw', }),

                                                          ]),
                                                 dbc.Tooltip(
                                                     'Include running workouts in Fitness trend.',
                                                     target="run-pmc"),
                                                 html.Div(id='ride-pmc', className='col-lg-12 col-3',
                                                          style={'padding': '0', 'alignSelf': 'center'},
                                                          children=[
                                                              daq.BooleanSwitch(
                                                                  id='ride-pmc-switch',
                                                                  on=pmc_switch_settings['ride_status'],
                                                                  style={'display': 'inline-block',
                                                                         'vertical-align': 'middle'}
                                                              ),
                                                              html.I(id='ride-pmc-icon', className='fa fa-bicycle',
                                                                     style={'fontSize': '1.5rem',
                                                                            'display': 'inline-block',
                                                                            'vertical-align': 'middle',
                                                                            'paddingLeft': '.25vw', }),

                                                          ]),
                                                 dbc.Tooltip(
                                                     'Include cycling workouts in Fitness trend.',
                                                     target="ride-pmc"),

                                                 html.Div(id='all-pmc', className='col-lg-12 col-3',
                                                          style={'padding': '0', 'alignSelf': 'center'},
                                                          children=[
                                                              daq.BooleanSwitch(
                                                                  id='all-pmc-switch',
                                                                  on=pmc_switch_settings['all_status'],
                                                                  style={'display': 'inline-block',
                                                                         'vertical-align': 'middle'}
                                                              ),
                                                              html.I(id='all-pmc-icon', className='fa fa-stream',
                                                                     style={'fontSize': '1.5rem',
                                                                            'display': 'inline-block',
                                                                            'vertical-align': 'middle',
                                                                            'paddingLeft': '.25vw', }),

                                                          ]),
                                                 dbc.Tooltip(
                                                     'Include all other workouts in Fitness trend.',
                                                     target="all-pmc"),
                                                 html.Div(id='power-pmc', className='col-lg-12 col-3',
                                                          style={'padding': '0', 'alignSelf': 'center'},
                                                          children=[
                                                              daq.BooleanSwitch(
                                                                  id='power-pmc-switch',
                                                                  on=use_power,
                                                                  style={'display': 'inline-block',
                                                                         'vertical-align': 'middle'},
                                                                  disabled=pmc_switch_settings[
                                                                               'power_status'] and not use_power
                                                              ),
                                                              html.I(id='power-pmc-icon', className='fa fa-bolt',
                                                                     style={'fontSize': '1.5rem',
                                                                            'display': 'inline-block',
                                                                            'vertical-align': 'middle',
                                                                            'paddingLeft': '.25vw', }),

                                                          ]),
                                                 dbc.Tooltip(
                                                     'Include power data for stress scores.',
                                                     target="power-pmc"),
                                                 html.Div(id='hr-pmc', className='col-lg-12 col-3',
                                                          style={'padding': '0', 'alignSelf': 'center'},
                                                          children=[
                                                              daq.BooleanSwitch(
                                                                  id='hr-pmc-switch',
                                                                  on=pmc_switch_settings['hr_status'],
                                                                  style={'display': 'inline-block',
                                                                         'vertical-align': 'middle'}
                                                              ),
                                                              html.I(id='hr-pmc-icon', className='fa fa-heart',
                                                                     style={'fontSize': '1.5rem',
                                                                            'display': 'inline-block',
                                                                            'vertical-align': 'middle',
                                                                            'paddingLeft': '.25vw', }),

                                                          ]),
                                                 dbc.Tooltip(
                                                     'Include heart rate data for stress scores.',
                                                     target="hr-pmc"),

                                                 html.Div(id='atl-pmc', className='col-lg-12 col-3',
                                                          style={'padding': '0', 'alignSelf': 'center'},
                                                          children=[
                                                              daq.BooleanSwitch(
                                                                  id='atl-pmc-switch',
                                                                  on=pmc_switch_settings['atl_status'],
                                                                  style={'display': 'inline-block',
                                                                         'vertical-align': 'middle'},
                                                              ),
                                                              html.I(id='atl-pmc-icon', className='fa fa-chart-line',
                                                                     style={'fontSize': '1.5rem',
                                                                            'display': 'inline-block',
                                                                            'vertical-align': 'middle',
                                                                            'paddingLeft': '.25vw', }),

                                                          ]),
                                                 dbc.Tooltip(
                                                     'Always include fatigue from all sports',
                                                     target="atl-pmc"),

                                             ]),
                                         ]),

                                 ]),
                             ]),
                         ]),
                     ]),
            html.Div(id='trend-containers', className='col-lg-4', children=[

                html.Div(className='row mb-2', children=[
                    html.Div(className='col-lg-12', children=[
                        dbc.Card([
                            dbc.CardHeader(className='align-items-center text-left', children=[
                                html.H6('90 Day Performance', id='performance-title', className='mb-0',
                                        style={'display': 'inline-block'}),

                            ]),
                            dbc.CardBody([
                                html.Div(className='row align-items-center',
                                         # style={'paddingBottom': '1.25rem'},
                                         children=[

                                             html.Div(className='col-12 align-items-center mb-2',
                                                      style={'height': '1.375rem'}, children=[

                                                     dbc.DropdownMenu(children=
                                                     [
                                                         dbc.DropdownMenuItem("All Dates",
                                                                              id="performance-time-selector-all",
                                                                              n_clicks_timestamp=0),
                                                         dbc.DropdownMenuItem("YTD",
                                                                              # id=f"{datetime.now().strftime('%j')}"),
                                                                              id='performance-time-selector-ytd',
                                                                              n_clicks_timestamp=0),
                                                         dbc.DropdownMenuItem("L90D",
                                                                              id="performance-time-selector-l90d",
                                                                              n_clicks_timestamp=1),
                                                         dbc.DropdownMenuItem("L6W",
                                                                              id='performance-time-selector-l6w',
                                                                              n_clicks_timestamp=0),
                                                         dbc.DropdownMenuItem("L30D",
                                                                              id="performance-time-selector-l30d",
                                                                              n_clicks_timestamp=0),
                                                     ],
                                                         label="L90D",
                                                         bs_size='sm',
                                                         className="mb-0",
                                                         id='performance-time-selector',
                                                         style={'display': 'inline-block', 'paddingRight': '2vw'},
                                                     ),
                                                     html.I(id='performance-trend-running-icon',
                                                            className='fa fa-running',
                                                            style={'fontSize': '1.5rem', 'display': 'inline-block'}),
                                                     daq.ToggleSwitch(id='performance-activity-type-toggle',
                                                                      className='mr-2 ml-2',
                                                                      style={'display': 'inline-block'}, value=True),

                                                     html.I(id='performance-trend-bicycle-icon',
                                                            className='fa fa-bicycle',
                                                            style={'fontSize': '1.5rem', 'display': 'inline-block'}),
                                                     dbc.Tooltip('Analyze cycling activities',
                                                                 target="performance-trend-bicycle-icon"),
                                                     dbc.Tooltip('Toggle activity type',
                                                                 target="performance-activity-type-toggle"),
                                                     dbc.Tooltip('Analyze running activities',
                                                                 target="performance-trend-running-icon"),

                                                     dbc.DropdownMenu(children=
                                                     [
                                                         dbc.DropdownMenuItem("All Intensities",
                                                                              id="performance-intensity-selector-all",
                                                                              n_clicks_timestamp=1),
                                                         dbc.DropdownMenuItem("High Intensity",
                                                                              id='performance-intensity-selector-high',
                                                                              n_clicks_timestamp=0),
                                                         dbc.DropdownMenuItem("Mod Intensity",
                                                                              id="performance-intensity-selector-mod",
                                                                              n_clicks_timestamp=0),
                                                         dbc.DropdownMenuItem("Low Intensity",
                                                                              id='performance-intensity-selector-low',
                                                                              n_clicks_timestamp=0),
                                                     ],
                                                         label="All Intensities",
                                                         bs_size='sm',
                                                         className="mb-0",
                                                         id='performance-intensity-selector',
                                                         style={'display': 'inline-block', 'paddingLeft': '2vw'},
                                                     ),
                                                 ]),

                                             # sport_filter_icons(id='zones'),
                                             html.Div(
                                                 className='col-lg-6 col-12 mt-2' if peloton_credentials_supplied else 'col-12 mt-2',
                                                 children=[
                                                     dbc.Spinner(color='info', children=[
                                                         html.Div(id='performance-trend-zones'),
                                                     ]),
                                                 ]),
                                             # populated by callback
                                             html.Div(className='col-lg-6 col-12 mt-2', style={
                                                 'display': 'none'} if not peloton_credentials_supplied else {},
                                                      children=[
                                                          dbc.Spinner(color='info', children=[
                                                              html.Div(className='col-lg-12',
                                                                       children=[
                                                                           html.P(['Training Distribution'], style={
                                                                               'height': '20px',
                                                                               'font-family': '"Open Sans", verdana, arial, sans-serif',
                                                                               'font-size': '14px',
                                                                               'color': white,
                                                                               'fill': 'rgb(220, 220, 220)',
                                                                               'line-height': '10px',
                                                                               'opacity': 1,
                                                                               'font-weight': 'normal',
                                                                               'white-space': 'pre',
                                                                               'marginBottom': 0})
                                                                       ]),
                                                              html.Div(id='workout-distribution-table',
                                                                       children=[
                                                                           dash_table.DataTable(
                                                                               id='workout-type-distributions',
                                                                               columns=[{'name': 'Activity',
                                                                                         'id': 'workout'},
                                                                                        {'name': '%',
                                                                                         'id': 'Percent of Total'}],
                                                                               style_as_list_view=True,
                                                                               fixed_rows={'headers': True, 'data': 0},
                                                                               style_table={'height': '180px',
                                                                                            'overflowY': 'auto'},
                                                                               style_header={
                                                                                   'backgroundColor': 'rgba(0,0,0,0)',
                                                                                   'borderBottom': '1px solid rgb(220, 220, 220)',
                                                                                   'borderTop': '0px',
                                                                                   # 'textAlign': 'center',
                                                                                   'fontSize': 12,
                                                                                   'fontWeight': 'bold',
                                                                                   'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                                                                               },
                                                                               style_cell={
                                                                                   'backgroundColor': 'rgba(0,0,0,0)',
                                                                                   'color': 'rgb(220, 220, 220)',
                                                                                   'borderBottom': '1px solid rgb(73, 73, 73)',
                                                                                   'textOverflow': 'ellipsis',
                                                                                   'maxWidth': 25,
                                                                                   'fontSize': 12,
                                                                                   'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                                                                               },
                                                                               style_cell_conditional=[
                                                                                   {
                                                                                       'if': {'column_id': c},
                                                                                       'textAlign': 'center'
                                                                                   } for c in
                                                                                   ['workout', 'Percent of Total']
                                                                               ],

                                                                               page_action="none",
                                                                           )

                                                                       ]),
                                                          ]),
                                                      ]),
                                         ]),
                                html.Div(className='row', style={'paddingTop': '.75rem'}, children=[

                                    html.Div(className='col-lg-6' if use_power else '', children=[
                                        html.Div(id='performance-power-curve-container', children=[
                                            dbc.Spinner(color='info', children=[
                                                dcc.Graph(id='performance-power-curve',
                                                          config={'displayModeBar': False})
                                            ])
                                        ])
                                    ]),
                                    html.Div(className='col-lg-5 col-11' if use_power else 'col-11',
                                             style={'paddingRight': 0},
                                             children=[

                                                 # Generated by callback
                                                 html.Div([
                                                     dbc.Spinner(color='info', children=[
                                                         dcc.Graph(id='trend-chart', config={'displayModeBar': False})
                                                     ]),
                                                 ]),
                                             ]),

                                    html.Div(id='trend-controls', className='col-1',
                                             style={'display': 'flex',
                                                    'justifyContent': 'space-between',
                                                    'paddingLeft': 0, 'paddingRight': 0},
                                             children=get_trend_controls()),

                                ]),

                            ])
                        ])
                    ]),

                ]),

            ]),

        ]),

        html.Div(className='row', children=[
            html.Div(className='col-lg-8', children=[
                dbc.Card([
                    dbc.CardBody([
                        html.Div(className='col-lg-12', style={'overflow': 'hidden'},
                                 children=dash_table.DataTable(
                                     id='activity-table',
                                     data=create_activity_table(),
                                     columns=[
                                         {'name': 'Date', 'id': 'date'},
                                         {'name': 'Name', 'id': 'name'},
                                         {'name': 'Type', 'id': 'type'},
                                         {'name': 'Time', 'id': 'time'},
                                         {'name': 'Mileage', 'id': 'distance'},
                                         {'name': 'PSS', 'id': 'tss'},
                                         {'name': 'HRSS', 'id': 'hrss'},
                                         # {'name': 'TRIMP', 'id': 'trimp'},
                                         # {'name': 'NP', 'id': 'weighted_average_power'},
                                         # {'name': 'IF', 'id': 'relative_intensity'},
                                         # {'name': 'EF', 'id': 'efficiency_factor'},
                                         # {'name': 'VI', 'id': 'variability_index'},
                                         {'name': 'FTP', 'id': 'ftp'},
                                         {'name': 'activity_id', 'id': 'activity_id'}
                                     ] if use_power else [{'name': 'Date', 'id': 'date'},
                                                          {'name': 'Name', 'id': 'name'},
                                                          {'name': 'Type', 'id': 'type'},
                                                          {'name': 'Time', 'id': 'time'},
                                                          {'name': 'Mileage', 'id': 'distance'},
                                                          {'name': 'TRIMP', 'id': 'trimp'},
                                                          {'name': 'activity_id', 'id': 'activity_id'}],
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

            html.Div(id='growth-container', className='col-lg-4',
                     children=[
                         dbc.Card([
                             dbc.CardHeader(
                                 html.Div(className='row align-items-center text-left', children=[
                                     ### Title ###
                                     html.Div(id='growth-header', className='col-lg-12')
                                 ]),

                             ),
                             dbc.CardBody([
                                 html.Div(className='col-12 text-center align-items-center mb-2', children=[
                                     dbc.DropdownMenu(
                                         [

                                             dbc.DropdownMenuItem("Running", header=True),
                                             dbc.DropdownMenuItem("Distance", id="run|distance"),
                                             dbc.DropdownMenuItem("Duration", id="run|elapsed_time"),
                                             dbc.DropdownMenuItem("hrSS", id="run|hrss"),
                                             dbc.DropdownMenuItem("Stress Score", id="run|tss"),
                                             dbc.DropdownMenuItem("Trimp", id="run|trimp"),

                                             dbc.DropdownMenuItem(divider=True),
                                             dbc.DropdownMenuItem("Cycling", header=True),
                                             dbc.DropdownMenuItem("Distance", id="ride|distance"),
                                             dbc.DropdownMenuItem("Duration", id="ride|elapsed_time"),
                                             dbc.DropdownMenuItem("hrSS", id="ride|hrss"),
                                             dbc.DropdownMenuItem("Stress Score", id="ride|tss"),
                                             dbc.DropdownMenuItem("Trimp", id="ride|trimp"),

                                         ],
                                         label="Run Distance",
                                         bs_size='sm',
                                         className="mb-0",
                                         id='growth-chart-metric-select',
                                     ),
                                 ]),
                                 dcc.Graph(id='growth-chart', config={'displayModeBar': False},
                                           # style={'height': '90%'}
                                           )
                             ])
                         ]),
                     ]),
        ]),

        html.Div(id='modal-activity-id-type-metric', style={'display': 'none'}),
    ])


# def detect_trend(ln_rmssd_7_slope_trivial, hr_average_7_slope_trivial, cv_rmssd_7_slope_trivial,
#                  ln_rmssd_normalized_7_slope_trivial, atl_7_slope_trivial):
#     if ln_rmssd_7_slope_trivial >= 0 and hr_average_7_slope_trivial <= 0 and cv_rmssd_7_slope_trivial < 0:
#         return 'Coping well'
#     elif ln_rmssd_7_slope_trivial < 0 and hr_average_7_slope_trivial < 0 \
#             and atl_7_slope_trivial >= 0:  # E.O Customization
#         return 'Risk of accumulated fatigue'
#     elif hr_average_7_slope_trivial > 0 and cv_rmssd_7_slope_trivial > 0:
#         return 'Maladaptation'
#     elif ln_rmssd_7_slope_trivial < 0 and hr_average_7_slope_trivial > 0 and cv_rmssd_7_slope_trivial < 0 \
#             and atl_7_slope_trivial > 0:  # E.O Customization:
#         return 'Accumulated fatigue'
#     else:
#         return 'No Relevant Trends'


def zscore(x, y, window):
    '''

    :param x: metric to compare to mean & std
    :param y: metric to do the rolling calculation on
    :param window: number of days to rollback
    :return:
    '''
    r = y.rolling(window=window)
    m = r.mean()  # .shift(1)
    s = r.std(ddof=0)  # .shift(1)
    z = (x - m) / s
    return z


def daily_z_recommendation(hrv_z_score, hr_z_score):
    # https://www.myithlete.com/how-to-use-the-ithlete-pro-training-guide/
    x, y = hrv_z_score, hr_z_score

    if (x < -1 and y > 1.75) or (x < -1 and y < -2):
        return 'Rest'
    elif (x < -1 and -2 < y < 1.75) or (x > -1 and y > 1.75) or (x > -1 and y < -2):
        return 'Low'
    elif (-1 < x < 1 and -2 < y < 1.75) or (x > 1 and -2 < y < -1) or (x > 1 and 1 < y < 1.75):
        return 'Mod'
    elif (x > 1 and -1 < y < 1):
        return 'High'


def daily_z_desc(hrv_z_score, hr_z_score):
    # https://www.myithlete.com/how-to-use-the-ithlete-pro-training-guide/
    x, y = hrv_z_score, hr_z_score

    if x < -1 and y > 1.75:
        return 'Stress / Illness'
    elif x < -1 and -2 < y < 1.75:
        return 'Impaired Recovery'
    elif -1 < x < 1 and -2 < y < 1.75:
        return 'Normal Training'
    elif x > 1 and -1 < y < 1:
        return 'Intensive Training'
    elif x > 0 and y < -2:
        return 'Low Energy / Activation'
    else:
        return 'No Trend Detected'


def z_adaptation(hrv7_z_score, hr7_z_score):
    x, y = hrv7_z_score, hr7_z_score
    if -1 < x < 0 and 0 < y < 1.75:
        return 'Competition Ready'
    elif 0 < x < 1.5 and -2 < y < 0:
        return 'Coping Well'
    elif -2.25 < x < -1 and 0 < y < 1.75:
        return 'Not Coping Well'
    else:
        return 'No Trend Detected'


def z_color(z_trend):
    if z_trend in ['Competition Ready', 'Intensive Training']:
        return teal
    elif z_trend in ['Coping Well', 'Normal Training']:
        return light_blue
    elif z_trend in ['Not Coping Well', 'Low Energy / Activation', 'Impaired Recovery']:
        return orange
    elif z_trend == 'Stress / Illness':
        return 'red'
    else:
        return white


def z_recommendation_chart(hrv_z_score, hr_z_score, hrv7_z_score, hr7_z_score, hrv, hr, z_desc):
    shapes = [
        ## Rest ##
        dict(type='rect', xref='x',
             yref='y', x0=-3, x1=-1, y0=1.75, y1=3,
             fillcolor=orange, layer='below',
             line=dict(width=0), ),
        dict(type='rect', xref='x',
             yref='y', x0=-3, x1=-1, y0=-3, y1=-2,
             fillcolor=orange, layer='below',
             line=dict(width=0),
             ),
        ## Low ##
        dict(type='rect', xref='x',
             yref='y', x0=-3, x1=-1, y0=-2, y1=1.75,
             fillcolor=white, layer='below',
             line=dict(width=0), ),
        dict(type='rect', xref='x',
             yref='y', x0=-1, x1=3, y0=1.75, y1=3,
             fillcolor=white, layer='below',
             line=dict(width=0), ),
        dict(type='rect', xref='x',
             yref='y', x0=-1, x1=3, y0=-2, y1=-3,
             fillcolor=white, layer='below',
             line=dict(width=0), ),
        ## Mod ##
        dict(type='rect', xref='x',
             yref='y', x0=-1, x1=1, y0=-2, y1=1.75,
             fillcolor=light_blue, layer='below',
             line=dict(width=0), ),
        dict(type='rect', xref='x',
             yref='y', x0=1, x1=3, y0=-2, y1=-1,
             fillcolor=light_blue, layer='below',
             line=dict(width=0), ),
        dict(type='rect', xref='x',
             yref='y', x0=1, x1=3, y0=1, y1=1.75,
             fillcolor=light_blue, layer='below',
             line=dict(width=0), ),
        ## High ##
        dict(type='rect', xref='x',
             yref='y', x0=1, x1=3, y0=-1, y1=1,
             fillcolor=teal, layer='below',
             line=dict(width=0), ),

    ]

    return html.Div([
        html.H6(className='mb-0', children=[z_desc]),
        dcc.Graph(id='z-score-treemap', className='col-lg-12 mb-2',
                  config={'displayModeBar': False},
                  figure={
                      'data': [
                          # 7 day baselines
                          go.Scatter(
                              x=[hrv7_z_score],
                              y=[hr7_z_score],
                              # text=df['movement_tooltip'],
                              hoverinfo='none',
                              marker={
                                  'color': [dark_blue],
                                  'symbol': 'diamond',
                                  'line_color': white,
                                  'line_width': .5},

                              # orientation='h',
                          ),
                          # Daily values
                          go.Scatter(
                              x=[hrv_z_score],
                              y=[hr_z_score],
                              # text=df['movement_tooltip'],
                              hoverinfo='none',
                              marker={
                                  'color': ['rgb(66,66,66)'],
                                  'line_color': white,
                                  'line_width': .5},
                              # orientation='h',
                          )

                      ],
                      'layout': go.Layout(
                          height=150,
                          # width=100,
                          shapes=shapes,
                          annotations=[go.layout.Annotation(
                              x=hrv_z_score,
                              y=hr_z_score,
                              xref="x",
                              yref="y",
                              text='HRV: {:.0f}<br>HR: {:.0f}'.format(hrv, hr),
                              bgcolor='rgba(66,66,66,.5)',
                              font=dict(
                                  size=10,
                                  color=white
                              ),
                              arrowcolor='rgba(0,0,0,0)',
                              showarrow=True,
                              arrowhead=0,
                              ax=30,
                              ay=0
                          )],
                          # transition=dict(duration=transition),
                          font=dict(
                              size=8,
                              color=white
                          ),
                          xaxis=dict(
                              title='Recovery',
                              range=[-3, 3],
                              showticklabels=False,
                              showgrid=False,
                          ),
                          yaxis=dict(
                              title='<br>Activation',
                              range=[-3, 3],
                              showticklabels=False,
                              showgrid=False,
                          ),
                          showlegend=False,
                          margin={'l': 25, 'b': 12, 't': 12, 'r': 25},
                          hovermode='x'
                      )
                  }
                  )
    ])


def get_hrv_df():
    hrv_df = pd.read_sql(
        sql=app.session.query(ouraSleepSummary.report_date, ouraSleepSummary.summary_date, ouraSleepSummary.rmssd,
                              ouraSleepSummary.hr_average).statement,
        con=engine, index_col='report_date').sort_index(ascending=True)

    # Merge readiness score
    hrv_df = hrv_df.merge(pd.read_sql(
        sql=app.session.query(ouraReadinessSummary.report_date, ouraReadinessSummary.score).statement,
        con=engine, index_col='report_date'), how='left', left_index=True, right_index=True)

    trimp_df = pd.read_sql(sql=app.session.query(stravaSummary.start_day_local, stravaSummary.trimp).statement,
                           con=engine, index_col='start_day_local').sort_index(ascending=True)
    app.session.remove()

    # Calculate ln rmssd
    hrv_df['ln_rmssd'] = np.log(hrv_df['rmssd'])
    # Calculate AVNN
    hrv_df['AVNN'] = 60000 / hrv_df['hr_average']

    trimp_df.index = pd.to_datetime(trimp_df.index)
    hrv_df = pd.merge(hrv_df, trimp_df, how='left', left_index=True, right_index=True)

    # Calculate HRV metrics
    hrv_df.set_index(pd.to_datetime(hrv_df.index), inplace=True)
    hrv_df = hrv_df.resample('D').mean()

    # HRV baseline
    hrv_df['rmssd_7'] = hrv_df['rmssd'].rolling(7).mean()
    # Daily HRV change for KPI
    hrv_df['rmssd_yesterday'] = hrv_df['rmssd'].shift(1)
    # HR baseline
    hrv_df['hr_average_yesterday'] = hrv_df['hr_average'].shift(1)
    hrv_df['hr_average_7'] = hrv_df['hr_average'].rolling(7).mean()

    # Natural Log calculations
    hrv_df['ln_rmssd_7'] = hrv_df['ln_rmssd'].rolling(7).mean()

    # 30/60 day Stdev and means
    hrv_df['ln_rmssd_30'] = hrv_df['ln_rmssd'].rolling(30).mean()
    hrv_df['ln_rmssd_60'] = hrv_df['ln_rmssd'].rolling(60).mean()
    hrv_df['ln_rmssd_30_stdev'] = hrv_df['ln_rmssd'].rolling(30).std()
    hrv_df['ln_rmssd_60_stdev'] = hrv_df['ln_rmssd'].rolling(60).std()

    # Normal value (SWC) thresholds for 7 day hrv baseline trends to analyze physiological changes
    hrv_df['swc_baseline_upper'] = hrv_df['ln_rmssd_60'] + hrv_df['ln_rmssd_60_stdev']
    hrv_df['swc_baseline_lower'] = hrv_df['ln_rmssd_60'] - hrv_df['ln_rmssd_60_stdev']

    # Normal value (SWC) thresholds for 7 day hrv baseline trends to guide workflow steps
    hrv_df['swc_flowchart_upper'] = hrv_df['ln_rmssd_30'] + (hrv_df['ln_rmssd_30_stdev'] * .5)
    hrv_df['swc_flowchart_lower'] = hrv_df['ln_rmssd_30'] - (hrv_df['ln_rmssd_30_stdev'] * .5)
    hrv_df['within_flowchart_swc'] = True
    hrv_df.loc[(hrv_df['ln_rmssd_7'] < hrv_df['swc_flowchart_lower']) | (hrv_df['ln_rmssd_7'] > hrv_df[
        'swc_flowchart_upper']), 'within_flowchart_swc'] = False

    # Normal value thresholds (SWC) for daily rmssd
    hrv_df['swc_daily_upper'] = hrv_df['ln_rmssd_60'] + (hrv_df['ln_rmssd_60_stdev'] * 1.5)
    hrv_df['swc_daily_lower'] = hrv_df['ln_rmssd_60'] - (hrv_df['ln_rmssd_60_stdev'] * 1.5)
    hrv_df['within_daily_swc'] = True
    hrv_df.loc[(hrv_df['ln_rmssd'] < hrv_df['swc_daily_lower']) | (hrv_df['ln_rmssd'] > hrv_df[
        'swc_daily_upper']), 'within_daily_swc'] = False

    # Z Score Method

    # TODO: Update these z scores so be normalized by CV
    hrv_df['hrv_z_score'] = zscore(x=hrv_df['ln_rmssd'], y=hrv_df['ln_rmssd'], window=30)
    hrv_df['hr_z_score'] = zscore(x=hrv_df['hr_average'], y=hrv_df['hr_average'], window=30)
    hrv_df["z_recommendation"] = hrv_df[["hrv_z_score", "hr_z_score"]].apply(lambda x: daily_z_recommendation(*x),
                                                                             axis=1)
    hrv_df["z_desc"] = hrv_df[["hrv_z_score", "hr_z_score"]].apply(lambda x: daily_z_desc(*x), axis=1)

    # ithlete uses daily hr and hrv normalized by CV, use 7 day averages over 30 days instead?
    hrv_df['hrv7_z_score'] = zscore(x=hrv_df['ln_rmssd_7'], y=hrv_df['ln_rmssd'], window=60)
    hrv_df['hr7_z_score'] = zscore(x=hrv_df['hr_average_7'], y=hrv_df['hr_average'], window=60)
    # Detect training adaptations based on 7day z scores
    hrv_df["detected_trend"] = hrv_df[["hrv7_z_score", "hr7_z_score"]].apply(lambda x: z_adaptation(*x), axis=1)

    # Threshold Flags
    # hrv_df['under_low_threshold'] = hrv_df['ln_rmssd_7'] < hrv_df['swc_baseline_lower']
    # hrv_df['under_low_threshold_yesterday'] = hrv_df['under_low_threshold'].shift(1)
    # hrv_df['over_upper_threshold'] = hrv_df['ln_rmssd_7'] > hrv_df['swc_baseline_upper']
    # hrv_df['over_upper_threshold_yesterday'] = hrv_df['over_upper_threshold'].shift(1)
    # for i in hrv_df.index:
    #     if hrv_df.at[i, 'under_low_threshold_yesterday'] == False and hrv_df.at[
    #         i, 'under_low_threshold'] == True:
    #         hrv_df.at[i, 'lower_threshold_crossed'] = True
    #     else:
    #         hrv_df.at[i, 'lower_threshold_crossed'] = False
    #     if hrv_df.at[i, 'over_upper_threshold_yesterday'] == False and hrv_df.at[
    #         i, 'over_upper_threshold'] == True:
    #         hrv_df.at[i, 'upper_threshold_crossed'] = True
    #     else:
    #         hrv_df.at[i, 'upper_threshold_crossed'] = False

    return hrv_df


def get_trend_controls(selected=None, sport='run'):
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_run_power = True if athlete_info.use_run_power else False
    use_cycle_power = True if athlete_info.use_cycle_power else False
    use_power = True if use_run_power or use_cycle_power else False
    app.session.remove()
    metrics = {'average-watts': {'fa fa-bolt': 'Power (w)'},
               'average-heartrate': {'fa fa-heartbeat': 'Heartrate'},
               'tss': {'fa fa-tachometer-alt': 'Stress (tss)'},
               'distance': {'fa fa-arrows-alt-h': 'Distance (mi)'},
               'elapsed-time': {'fa fa-clock': 'Duration (min)'},
               'average-speed': {'fa fa-flag-checkered': 'Pace'},
               'average-ground-time': {'fa fa-road': 'Ground contact time'},
               'average-oscillation': {'fa fa-arrows-alt-v': 'Vertical Oscillation'},
               'average-leg-spring': {'fa fa-frog': 'Leg Spring Stiffness (LSS)'}
               }
    hide = []

    if not selected:
        selected = 'average_heartrate' if not use_power else 'average_watts'

    if sport.lower() == 'run':
        if not use_run_power:
            hide.extend(['average-watts', 'tss', 'average-ground-time', 'average-oscillation', 'average-leg-spring'])
        # if not stryd_credentials_supplied:
        #     hide.extend(['average-ground-time', 'average-oscillation', 'average-leg-spring'])

    elif sport.lower() == 'ride':
        hide.extend(['average-ground-time', 'average-oscillation', 'average-leg-spring'])
        if not use_cycle_power:
            hide.extend(['average-watts', 'tss'])

    controls = []
    for metric in metrics.keys():
        style = {'padding': '0', 'alignSelf': 'center', 'display': 'none'} if metric in hide else {'padding': '0',
                                                                                                   'alignSelf': 'center'}
        is_selected = True if selected.replace('_', '-') == metric else False
        controls.append(
            html.Div(className='col-lg-12 align-items-center',
                     style=style,
                     children=[
                         html.I(id=f'{metric}-trend-button',
                                className=list(metrics[metric].keys())[0],
                                n_clicks_timestamp=1 if is_selected else 0,
                                style={'fontSize': '1rem',
                                       'color': teal if is_selected else white,
                                       'vertical-align': 'middle',
                                       'bgColor': 'rgba(0,0,0,0)',
                                       'border': 'none'}),

                     ]),
        )
        controls.append(dbc.Tooltip(list(metrics[metric].values())[0], target=f'{metric}-trend-button'), )

    return html.Div(className='row', children=controls)


def get_trend_chart(metric, sport='Ride', days=90, intensity='all'):
    date = datetime.now().date() - timedelta(days=days)
    df = pd.read_sql(
        sql=app.session.query(stravaSummary).filter(
            stravaSummary.type.like(sport), stravaSummary.elapsed_time > app.session.query(athlete).filter(
                athlete.athlete_id == 1).first().min_non_warmup_workout_time).statement, con=engine)
    if intensity != 'all':
        df = df[df['workout_intensity'] == intensity]

    stryd_df = pd.read_sql(
        sql=app.session.query(strydSummary).statement, con=engine)
    app.session.remove()
    df = df.merge(stryd_df, how='left', left_on='activity_id', right_on='strava_activity_id')

    # Remove bad data
    df[metric].replace(0, np.nan, inplace=True)

    # Convert duration to minutes
    if metric == 'elapsed_time':
        df['duration'] = df[metric] / 60
        metric = 'duration'
    elif metric == 'average_speed':
        df['average_pace'] = 60 / df[metric]
        metric = 'average_pace'

    # Get all time PR of current metric
    if metric in ['average_pace', 'average_ground_time', 'average_oscillation']:
        pr = df[metric].min()
    else:
        pr = df[metric].max()

    # Filter df to date selection made from dropdown
    df = df[df['start_date_local_x'].dt.date >= date]

    # Resample to accurately plot line of best fit
    df = df.set_index('start_date_local_x')
    df = df[[metric]].resample('D').mean().reset_index()
    # Ignore dates with null values when running our model
    idx = np.isfinite(df[metric])
    if len(idx) > 1:
        slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(df.reset_index().index[idx],
                                                                             df[metric][idx])
        # Color trend line but its strength of fit
        if r_value >= .8 or r_value <= -.8:  # Strong fit
            trend_strength = teal
        elif (r_value < .8 and r_value >= .5) or (r_value > -.8 and r_value <= -.5):  # Medium Fit
            trend_strength = light_blue
        else:  # Weak fit
            trend_strength = white

        df[metric + '_trend'] = (df.index * slope) + intercept
    else:
        df[metric + '_trend'] = np.nan
        trend_strength = white
    # Change index back for the chart
    df = df.set_index('start_date_local_x')

    # Format tooltips
    if metric in ['duration', 'average_pace']:
        text = ['{}: <b>{}'.format(metric.title().replace('_', ' '), str(timedelta(minutes=x)).split(".")[0]) for x in
                df[metric].fillna(0)]
    elif metric in ['distance', 'average_oscillation', 'average_leg_spring']:
        text = ['{}: <b>{:.1f}'.format(metric.title().replace('_', ' '), x) for x in df[metric]]
    else:
        text = ['{}: <b>{:.0f}'.format(metric.title().replace('_', ' '), x) for x in df[metric]]

    data = [
        go.Scatter(
            name=metric.title(),
            x=df.index,
            y=[np.nan if x == pr else x for x in df[metric]],
            yaxis='y',
            text=text,
            hoverinfo='x+text',
            mode='markers',
            line={'dash': 'dot',
                  'color': 'rgba(220,220,220,.25)',
                  'width': 2},
            showlegend=False,
            marker={'size': 5},
        ),
        go.Scatter(
            name='{} Trend'.format(metric.title()),
            x=df.index,
            y=df[metric + '_trend'],
            yaxis='y',
            hoverinfo='none',
            mode='lines',
            line={'color': trend_strength,
                  'width': 3},
            showlegend=False,
        ),
        # go.Scatter(
        #     name='PR',
        #     x=df.index,
        #     y=[pr for x in df.index],
        #     mode='lines+text',
        #     text=[
        #         'PR: <b>{:.0f}'.format(pr) if x == df.index.max() else ''
        #         for x in df.index],
        #     textfont=dict(
        #         size=10,
        #         color=orange
        #     ),
        #     textposition='top left',
        #     hoverinfo='none',
        #     # opacity=0.7,
        #     line={'dash': 'dot', 'color': orange, 'width': 1},
        #     showlegend=False,
        # )
    ]
    if pr in df[metric].values:
        data.append(
            go.Scatter(
                name=metric.title() + ' PR',
                x=df.index,
                y=[np.nan if x != pr else x for x in df[metric]],
                yaxis='y',
                text=text[df.index.get_loc(df.loc[df[metric] == pr].index.values[0])],
                hoverinfo='x+text',
                mode='markers',
                line={'dash': 'dot',
                      'color': orange,
                      'width': 2},
                showlegend=False,
                marker={'size': 5},
            )
        )

    figure = {
        'data': data,
        'layout': go.Layout(
            title=metric.title().replace('_', ' '),
            height=200,
            font=dict(
                size=10,
                color=white
            ),
            xaxis=dict(
                showticklabels=True,
                showgrid=False,
                tickformat='%b %d',
            ),
            yaxis=dict(
                # range=[df[metric].min() - (df[metric].min() * .15), df[metric].max() * 1.15],
                showticklabels=True,
                showgrid=True,
                gridcolor='rgb(73, 73, 73)',
                # tickformat=',d',
            ),
            showlegend=False,
            margin={'l': 25, 'b': 20, 't': 20, 'r': 0},
            autosize=True,
            hovermode='closest'
        )
    }

    return figure


def training_zone(form):
    if form:
        if 25 < form:
            return 'No Fitness'
        elif 5 < form <= 25:
            return 'Performance'
        elif -10 < form <= 5:
            return 'Maintenance'
        elif -25 < form <= -10:
            return 'Productive'
        elif -40 < form < -25:
            return 'Cautionary'
        elif form <= -40:
            return 'Overreaching'
    else:
        return 'Form'


def readiness_score_recommendation(readiness_score):
    try:
        readiness_score = int(readiness_score)
        if readiness_score == 0:
            return ''
        elif readiness_score >= oura_high_threshold:
            return 'High'
        elif readiness_score >= oura_med_threshold:
            return 'Mod'
        elif readiness_score >= oura_low_threshold:
            return 'Low'
        else:
            return 'Rest'
    except:
        return 'N/A'


def recommendation_color(recommendaion_desc):
    if recommendaion_desc == 'High':
        return teal
    elif recommendaion_desc == 'Mod' or recommendaion_desc == 'HIIT':
        return light_blue
    elif recommendaion_desc == 'Low':
        return white
    elif recommendaion_desc == 'Rest':
        return orange
    elif recommendaion_desc == 'N/A':
        return 'rgba(220,220,220,.25)'


def create_daily_recommendations(plan_rec):
    if plan_rec:
        recovery_metric = app.session.query(athlete).filter(athlete.athlete_id == 1).first().recovery_metric
        if recovery_metric == 'hrv':
            recovery_metric_label = 'HRV'
            recovery_metric_tooltip = 'Workflow steps based on daily rmssd changes within 60 day mean +/- 1.5 stdev'
        elif recovery_metric == 'hrv_baseline':
            recovery_metric_label = 'Baseline'
            recovery_metric_tooltip = 'Workflow steps based on 7 day rmssd baseline changes within 30 day mean +/- .5 stdev'
        elif recovery_metric == 'readiness':
            recovery_metric_label = 'Readiness'
            recovery_metric_tooltip = 'Workflow steps based on Oura readiness score > 70'
        elif recovery_metric == 'zscore':
            recovery_metric_label = 'HRV & HR'
            recovery_metric_tooltip = 'Recommendation based on mutli-parameter approach'

        data = plan_rec.replace('rec_', '').split('|')
        plan_step = int(float(data[0]))
        plan_recommendation = data[1]
        plan_rationale = data[2]
        oura_recommendation = data[3]
        readiness_score = int(data[4])
        sleep_score = int(data[5])
        hrv_z_score = float(data[6])
        hr_z_score = float(data[7])
        hrv7_z_score = float(data[8])
        hr7_z_score = float(data[9])
        z_desc = data[10]
        hrv = data[11]
        hrv_yesterday = data[12]
        hrv7 = data[13]
        hr = data[14]
        hr_yesterday = data[15]
        hr7 = data[16]

        hrv = float(hrv) if hrv is not None else 'N/A'
        hrv_yesterday = float(hrv_yesterday) if hrv_yesterday is not None else 'N/A'
        hrv7 = float(hrv7) if hrv7 is not None else 'N/A'
        hr = float(hr) if hr is not None else 'N/A'
        hr_yesterday = float(hr_yesterday) if hr_yesterday is not None else 'N/A'
        hr7 = float(hr7) if hr7 is not None else 'N/A'

        if oura_recommendation == 'Rest':
            oura_rationale = f'Readiness score is < {oura_low_threshold}'
        elif oura_recommendation == 'Low':
            oura_rationale = f'Readiness score is between {oura_low_threshold} and {oura_med_threshold}'
        elif oura_recommendation == 'Mod':
            oura_rationale = f'Readiness score is between {oura_med_threshold} and {oura_high_threshold}'
        elif oura_recommendation == 'High':
            oura_rationale = f'Readiness score is {oura_high_threshold} or higher'
        else:
            oura_recommendation, oura_rationale = 'N/A', 'N/A'

    else:
        hrv, hrv_yesterday, hrv7, hrv7_change, hr, hr_yesterday, hr7, plan_rationale, plan_recommendation, oura_recommendation, recovery_metric, recovery_metric_label = \
            'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'
        sleep_score, readiness_score, oura_rationale, plan_step, hrv_z_score, hr_z_score = None, None, None, None, None, None

    readiness_score = round(readiness_score) if readiness_score else 'N/A'
    sleep_score = round(sleep_score) if sleep_score else 'N/A'

    if hrv_yesterday != 'N/A':
        hrv_yesterday_arrow = 'fa fa-angle-up' if hrv > hrv_yesterday else 'fa fa-angle-down'
        hrv_yesterday_color = teal if hrv > hrv_yesterday else orange
    else:
        hrv_yesterday_arrow = ''
        hrv_yesterday_color = ''

    if hrv != 'N/A' and hrv7 != 'N/A':
        change = hrv - hrv7
        hrv_vs_baseline_arrow = 'fa fa-angle-up' if change > 0 else 'fa fa-angle-down'
        hrv_vs_baseline_color = teal if change > 0 else orange
    else:
        hrv_vs_baseline_arrow, hrv_vs_baseline_color = '', ''

    if hr_yesterday != 'N/A':
        hr_yesterday_arrow = 'fa fa-angle-up' if hr > hr_yesterday else 'fa fa-angle-down'
        hr_yesterday_color = teal if hr < hr_yesterday else orange
    else:
        hr_yesterday_arrow = ''
        hr_yesterday_color = ''

    if hr != 'N/A' and hr7 != 'N/A':
        change = hr - hr7
        hr_vs_baseline_arrow = 'fa fa-angle-up' if change > 0 else 'fa fa-angle-down'
        hr_vs_baseline_color = teal if change < 0 else orange
    else:
        hr_vs_baseline_arrow, hr_vs_baseline_color = '', ''

    workflow_img = html.Div(className='col-lg-12', children=[
        html.Img(src=f'../assets/images/hrv{plan_step}.png', height=200,
                 width=150) if plan_step is not None else html.Div(),
    ])

    hrv_gauge = html.Div(className='col-lg-12', children=[
        dcc.Graph(id='hrv-gauge', className='col-lg-12',
                  config={'displayModeBar': False},
                  figure={
                      'data': [
                          go.Bar(
                              x=[-1.5],
                              y=['test'],
                              hoverinfo='none',
                              marker={
                                  'color': [teal]},
                              orientation='h',
                          ),
                          go.Bar(
                              x=[-.75],
                              y=['test'],
                              hoverinfo='none',
                              marker={
                                  'color': [white]},
                              orientation='h',
                          ),
                          go.Bar(
                              x=[-.75],
                              y=['test'],
                              hoverinfo='none',
                              marker={
                                  'color': [orange]},
                              orientation='h',
                          ),

                          go.Bar(
                              x=[1.5],
                              y=['test'],
                              hoverinfo='none',
                              marker={
                                  'color': [teal]},
                              orientation='h',
                          ),
                          go.Bar(
                              x=[.75],
                              y=['test'],
                              hoverinfo='none',
                              marker={
                                  'color': [light_blue]},
                              orientation='h',
                          ),
                          go.Bar(
                              x=[.75],
                              y=['test'],
                              hoverinfo='none',
                              marker={
                                  'color': [orange]},
                              orientation='h',
                          ),
                      ],
                      'layout': go.Layout(
                          barmode='relative',
                          height=45,
                          # transition=dict(duration=transition),
                          font=dict(
                              size=10,
                              color=white
                          ),
                          xaxis=dict(
                              showticklabels=True,
                              range=[-3, 3],
                              tickvals=[hrv_z_score],
                              ticktext=[hrv],
                          ),
                          yaxis=dict(
                              showticklabels=False,
                              # range=[0, df['met_1min'].max() if df['met_1min'].max() > 7 else 8],
                              # tickvals=[1, 3, 7],
                              # ticktext=['Low ', 'Med ', 'High '],
                              showgrid=False,

                          ),
                          showlegend=False,
                          margin={'l': 0, 'b': 15, 't': 0, 'r': 0},
                          hovermode='x'
                      )
                  }
                  ) if hrv_z_score and hr_z_score else None
    ])

    daily_hrv_kpis = html.Div([html.Div(className='row text-center align-items-center', children=[

        #     html.Div(className='col-lg-12 text-center align-items-center mb-2', children=[
        #         html.H5(hrv, style={'display': 'inline'}),
    ]),

                               html.Div(className='row', children=[
                                   html.Div(className='col-lg-6', children=[
                                       html.H6('Yesterday', className='col-lg-12 mb-0'),
                                       html.Div(className='col-lg-12 text-center align-items-center mb-0', children=[
                                           html.H5('{:.0f}'.format(
                                               hrv_yesterday) if hrv_yesterday != 'N/A' else hrv_yesterday,
                                                   style={'display': 'inline'}),
                                           html.I(className=f'{hrv_yesterday_arrow} text-center align-items-center',
                                                  style={'fontSize': '1rem',
                                                         'display': 'inline',
                                                         'paddingLeft': '.25vw',
                                                         'color': hrv_yesterday_color}),
                                       ]),
                                   ]),
                                   html.Div(className='col-lg-6', children=[
                                       html.H6('Baseline', className='col-lg-12 mb-0'),
                                       html.Div(className='col-lg-12 text-center align-items-center mb-0', children=[
                                           html.H5('{:.0f}'.format(hrv7) if hrv7 != 'N/A' else hrv7,
                                                   style={'display': 'inline'}),
                                           html.I(className=f'{hrv_vs_baseline_arrow} text-center align-items-center',
                                                  style={'fontSize': '1rem',
                                                         'display': 'inline',
                                                         'paddingLeft': '.25vw',
                                                         'color': hrv_vs_baseline_color}),
                                       ]),
                                   ]),
                               ])
                               ])

    daily_hr_kpis = html.Div([html.Div(className='row text-center align-items-center', children=[
        #     html.Div(className='col-lg-12 text-center align-items-center mb-2', children=[
        #         html.H5(hrv, style={'display': 'inline'}),
    ]),

                              html.Div(className='row', children=[
                                  html.Div(className='col-lg-6', children=[
                                      html.H6('Yesterday', className='col-lg-12 mb-0'),
                                      html.Div(className='col-lg-12 text-center align-items-center mb-0', children=[
                                          html.H5(
                                              '{:.0f}'.format(hr_yesterday) if hr_yesterday != 'N/A' else hr_yesterday,
                                              style={'display': 'inline'}),
                                          html.I(className=f'{hr_yesterday_arrow} text-center align-items-center',
                                                 style={'fontSize': '1rem',
                                                        'display': 'inline',
                                                        'paddingLeft': '.25vw',
                                                        'color': hr_yesterday_color}),
                                      ]),
                                  ]),
                                  html.Div(className='col-lg-6', children=[
                                      html.H6('Baseline', className='col-lg-12 mb-0'),
                                      html.Div(className='col-lg-12 text-center align-items-center mb-0', children=[
                                          html.H5('{:.0f}'.format(hr7) if hr7 != 'N/A' else hr7,
                                                  style={'display': 'inline'}),
                                          html.I(className=f'{hr_vs_baseline_arrow} text-center align-items-center',
                                                 style={'fontSize': '1rem',
                                                        'display': 'inline',
                                                        'paddingLeft': '.25vw',
                                                        'color': hr_vs_baseline_color}),
                                      ]),
                                  ]),
                              ])
                              ])

    oura_gauge = html.Div(children=[
        html.H6(f'Oura Ready: {readiness_score} | Sleep: {sleep_score}', className='col-lg-12'),
        # html.H3(oura_recommendation, id='oura-rationale',
        #         style={'color': recommendation_color(oura_recommendation)}),
        # dbc.Tooltip(None if oura_recommendation == 'N/A' else oura_rationale,
        #             target="oura-rationale"),
        html.Div(className='col-lg-12', children=[
            dcc.Graph(id='oura-gauge', className='col-lg-12',
                      config={'displayModeBar': False},
                      figure={
                          'data': [
                              go.Bar(
                                  x=[70, 7, 8, 15],
                                  y=['dummy', 'dummy', 'dummy', 'dummy'],
                                  # text=df['movement_tooltip'],
                                  hoverinfo='none',
                                  marker={
                                      'color': [orange, white, light_blue, teal]},
                                  orientation='h',
                              ),
                          ],
                          'layout': go.Layout(
                              height=45,
                              # transition=dict(duration=transition),
                              font=dict(
                                  size=10,
                                  color=white
                              ),
                              xaxis=dict(
                                  showticklabels=True,
                                  range=[50, 100],
                                  tickvals=[readiness_score, sleep_score],
                                  ticktext=['R', 'S'],

                              ),
                              yaxis=dict(
                                  showticklabels=False,
                                  showgrid=False,
                              ),
                              showlegend=False,
                              margin={'l': 0, 'b': 15, 't': 0, 'r': 0},
                              hovermode='x'
                          )
                      }
                      ) if oura_recommendation != 'N/A' else None
        ]),

    ])
    if recovery_metric == 'N/A':
        recommendation_context = html.Div(html.H3('N/A'))
    if recovery_metric in ['hrv', 'hrv_baseline']:
        recommendation_context = html.Div([
            workflow_img,
            oura_gauge,
            html.H6("Heart Rate Variability", className='col-lg-12'),
            hrv_gauge,
            daily_hrv_kpis,
        ])
    elif recovery_metric == 'readiness':
        recommendation_context = html.Div([
            oura_gauge,
            z_recommendation_chart(hrv_z_score, hr_z_score, hrv7_z_score, hr7_z_score, hrv, hr, z_desc),
            html.H6("Heart Rate Variability", className='col-lg-12'),
            daily_hrv_kpis,
            html.H6("Heart Rate", className='col-lg-12'),
            daily_hr_kpis
        ])
    elif recovery_metric == 'zscore':
        recommendation_context = html.Div([
            z_recommendation_chart(hrv_z_score, hr_z_score, hrv7_z_score, hr7_z_score, hrv, hr, z_desc),
            oura_gauge,
            html.H6("Heart Rate Variability", className='col-lg-12'),
            daily_hrv_kpis,
            html.H6("Heart Rate", className='col-lg-12'),
            daily_hr_kpis
        ])

    return html.Div(id='recommendation', style={'display': 'flex', 'flexDirection': 'column',
                                                'justifyContent': 'space-between'},
                    children=[
                        html.Div(children=[
                            html.H6(f'{recovery_metric_label} Recommendation', id='workflow-recommendation-title',
                                    className='col-lg-12'),
                            dbc.Tooltip(None if plan_recommendation == 'N/A' else recovery_metric_tooltip,
                                        target="workflow-recommendation-title"),
                            html.H3(plan_recommendation, className='col-lg-12', id='hrv-rationale',
                                    style={'color': recommendation_color(plan_recommendation)}),
                            dbc.Tooltip(None if plan_recommendation == 'N/A' else plan_rationale,
                                        target="hrv-rationale", ),
                            recommendation_context,
                            #
                            # ]),

                            # html.Div(className='row text-center align-items-center', children=[
                            #     html.H6('Baseline HRV', className='col-lg-12'),
                            #     html.Div(className='col-lg-4', children=[
                            #         html.P(f'Baseline {hrv7}')
                            #     ]),
                            #     html.Div(className='col-lg-4', children=[
                            #         html.P(f'Yesterday {hrv7_yesterday}')
                            #     ]),
                            #     html.Div(className='col-lg-4', children=[
                            #         html.P(f'Baseline {hrv7}')
                            #     ]),
                            # ])
                            #
                        ]),

                    ])


def create_fitness_kpis(date, ctl, ramp, rr_min_threshold, rr_max_threshold, atl, tsb, hrv7, trend):
    # TODO: Remove ramp rate?
    if atl is not None and ctl is not None:
        ctl = round(ctl, 1)
        tsb = round(tsb, 1)

        if ctl == 0 or ctl == 'N/A':
            atl_ctl_ratio_injury_risk = 'No Fitness'
            atl_ctl_ratio = 'N/A'
            atl_ctl_ratio_injury_risk_color = white
        else:
            atl_ctl_ratio = atl / ctl
            if atl_ctl_ratio > 1.75:
                atl_ctl_ratio_injury_risk = 'High Injury Risk'
                atl_ctl_ratio_injury_risk_color = orange
            elif 1.3 < atl_ctl_ratio <= 1.75:
                atl_ctl_ratio_injury_risk = 'Increased Injury Risk'
                atl_ctl_ratio_injury_risk_color = light_blue
            elif 0.8 < atl_ctl_ratio <= 1.3:
                atl_ctl_ratio_injury_risk = 'Optimal Load'
                atl_ctl_ratio_injury_risk_color = teal
            elif 0.8 >= atl_ctl_ratio:
                atl_ctl_ratio_injury_risk = 'Loss of Fitness'
                atl_ctl_ratio_injury_risk_color = orange

    else:
        atl_ctl_ratio_injury_risk, ctl, atl, atl_ctl_ratio, atl_ctl_ratio_injury_risk_color = 'N/A', 'N/A', 'N/A', 'N/A', white
    # injury_risk = 'High' if ramp >= rr_max_threshold else 'Medium' if ramp >= rr_min_threshold else 'Low'

    detected_trend_color = z_color(trend)

    return [html.Div(className='row', children=[

        ### Date KPI ###
        html.Div(className='col-lg-2', children=[
            html.Div(children=[
                html.H6('{}'.format(datetime.strptime(date, '%Y-%m-%d').strftime("%b %d, %Y")),
                        className='d-inline-block',
                        style={'fontWeight': 'bold', 'color': 'rgb(220, 220, 220)', 'marginTop': '0',
                               'marginBottom': '0'}),
            ]),
        ]),
        ### CTL KPI ###
        html.Div(id='ctl-kpi', className='col-lg-2', children=[
            html.Div(children=[
                html.H6('Fitness {}'.format(ctl),
                        className='d-inline-block',
                        style={'color': ctl_color, 'marginTop': '0', 'marginBottom': '0'}),
            ]),
        ]),
        dbc.Tooltip(
            'Fitness (CTL) is an exponentially weighted average of your last 42 days of training stress scores (TSS) and reflects the training you have done over the last 6 weeks. Fatigue is sport specific.',
            target="ctl-kpi"),

        ### ATL KPI ###
        html.Div(id='atl-kpi', className='col-lg-2', children=[
            html.Div(children=[
                html.H6('Fatigue {}'.format(round(atl, 1) if atl != 'N/A' else 'N/A'),
                        className='d-inline-block',
                        style={'color': atl_color, 'marginTop': '0', 'marginBottom': '0'}),
            ]),
        ]),
        dbc.Tooltip(
            'Fatigue (ATL) is an exponentially weighted average of your last 7 days of training stress scores which provides an estimate of your fatigue accounting for the workouts you have done recently. Fatigue is not sport specific.',
            target="atl-kpi"),

        ### TSB KPI ###
        html.Div(id='tsb-kpi', className='col-lg-2', children=[
            html.Div(children=[
                html.H6('{} {}'.format('Form' if type(tsb) == type(str()) else training_zone(tsb), tsb),
                        className='d-inline-block',
                        style={'color': tsb_color, 'marginTop': '0', 'marginBottom': '0'}),
            ]),
        ]),
        dbc.Tooltip(
            "Training Stress Balance (TSB) or Form represents the balance of training stress. A positive TSB number means that you would have a good chance of performing well during those 'positive' days, and would suggest that you are both fit and fresh.",
            target="tsb-kpi", ),

        ### Injury Risk ###
        html.Div(id='injury-risk', className='col-lg-2', children=[
            html.Div(children=[
                # html.H6('Injury Risk: {}'.format(injury_risk),
                html.H6('{}'.format(atl_ctl_ratio_injury_risk),
                        className='d-inline-block',
                        style={'color': atl_ctl_ratio_injury_risk_color, 'marginTop': '0', 'marginBottom': '0'})
            ]),
        ]),
        # dbc.Tooltip('7 day CTL △ = {:.1f}'.format(ramp), target='injury-risk'),
        dbc.Tooltip(
            'ATL to CTL ratio = {}'.format(round(atl_ctl_ratio, 1) if atl_ctl_ratio != 'N/A' else 'N/A'),
            target='injury-risk'),

        ### Detected Trend ###
        html.Div(id='detected-trend-kpi', className='col-lg-2', children=[
            html.Div(children=[
                html.H6(trend if trend else 'No Trend Detected',
                        className='d-inline-block',
                        style={'color': detected_trend_color, 'marginTop': '0', 'marginBottom': '0'})
            ]),
        ] if oura_credentials_supplied else []),
        dbc.Tooltip(
            "Identified training adaption from physiological trends",
            target="detected-trend-kpi"
        )

        # ### HRV 7 Day Average ###
        # html.Div(id='hrv7-kpi', className='col-lg-2', children=[
        #     html.Div(children=[
        #         html.H6('7 Day HRV {}'.format(hrv7),
        #                 className='d-inline-block',
        #                 style={'color': teal, 'marginTop': '0', 'marginBottom': '0'})
        #     ]),
        # ] if oura_credentials_supplied else []),
        # dbc.Tooltip(
        #     "Rolling 7 Day HRV Average. Falling below the baseline threshold indicates you are not recovered and should hold back on intense training. Staying within the thresholds indicates you should stay on course, and exceeding the thresholds indicates a positive adaptation and workout intensity can be increased.",
        #     target="hrv7-kpi"
        # )

    ]),

            ]


def create_activity_table(date=None):
    df_summary_table_columns = ['name', 'type', 'time', 'distance', 'tss', 'hrss', 'trimp', 'weighted_average_power',
                                'relative_intensity', 'efficiency_factor', 'variability_index', 'ftp', 'activity_id']

    # Covert date to datetime object if read from clickData

    if date is not None:
        df_table = pd.read_sql(
            sql=app.session.query(stravaSummary.start_day_local, stravaSummary.name, stravaSummary.type,
                                  stravaSummary.elapsed_time,
                                  stravaSummary.distance, stravaSummary.tss, stravaSummary.hrss,
                                  stravaSummary.trimp, stravaSummary.weighted_average_power,
                                  stravaSummary.relative_intensity, stravaSummary.efficiency_factor,
                                  stravaSummary.variability_index, stravaSummary.ftp,
                                  stravaSummary.activity_id)
                .filter(stravaSummary.start_day_local == date)
                .statement,
            con=engine)

    else:
        df_table = pd.read_sql(
            sql=app.session.query(stravaSummary.start_day_local, stravaSummary.name, stravaSummary.type,
                                  stravaSummary.elapsed_time,
                                  stravaSummary.distance, stravaSummary.tss, stravaSummary.hrss,
                                  stravaSummary.trimp, stravaSummary.weighted_average_power,
                                  stravaSummary.relative_intensity, stravaSummary.efficiency_factor,
                                  stravaSummary.variability_index, stravaSummary.ftp,
                                  stravaSummary.activity_id)
                .statement, con=engine)

    app.session.remove()

    df_table['distance'] = df_table['distance'].replace({0: np.nan})
    # Filter df to columns we want for the table
    # If data was returned for date passed
    if len(df_table) > 0:
        # Add date column
        df_table['date'] = df_table['start_day_local'].apply(lambda x: x.strftime('%a, %b %d, %Y'))

        df_table['time'] = df_table['elapsed_time'].apply(lambda x: str(timedelta(seconds=x)))

        # Add id column and sort to selecting row from dash data table still works when filtering
        df_table.sort_values(by='start_day_local', ascending=False, inplace=True)
        df_table.reset_index(inplace=True)
        df_table['id'] = df_table.index
        df_summary_table_columns = ['id', 'date'] + df_summary_table_columns

        # Reorder columns
        df_table = df_table[df_summary_table_columns]

        # Table Rounding
        round_0_cols = ['tss', 'hrss', 'trimp', 'weighted_average_power', 'ftp']
        df_table[round_0_cols] = df_table[round_0_cols].round(0)

        round_2_cols = ['distance', 'relative_intensity', 'efficiency_factor', 'variability_index']
        df_table[round_2_cols] = df_table[round_2_cols].round(2)

        return df_table[df_summary_table_columns].sort_index(ascending=True).to_dict('records')

    else:
        return [{}]
        # return html.H3('No workouts found for {}'.format(date.strftime("%b %d, %Y")), style={'textAlign': 'center'})


def create_growth_kpis(date, cy, cy_metric, ly, ly_metric, metric):
    cy_title, ly_title = f'{cy}: N/A', f'{ly}: N/A'
    if cy_metric and metric in ['elapsed_time', 'high_intensity_seconds', 'low_intensity_seconds',
                                'mod_intensity_seconds']:
        cy_title = '{}: {}'.format(cy, timedelta(seconds=cy_metric))
    if ly_metric and metric in ['elapsed_time', 'high_intensity_seconds', 'low_intensity_seconds',
                                'mod_intensity_seconds']:
        ly_title = '{}: {}'.format(ly, timedelta(seconds=ly_metric))
    if cy_metric and metric == 'distance':
        cy_title = '{}: {:.1f} mi.'.format(cy, cy_metric)
    if ly_metric and metric == 'distance':
        ly_title = '{}: {:.1f} mi.'.format(ly, ly_metric)

    if cy_metric and metric in ['hrss', 'trimp', 'tss']:
        cy_title = '{}: {:.0f}'.format(cy, cy_metric)
    if ly_metric and metric in ['hrss', 'trimp', 'tss']:
        ly_title = '{}: {:.0f}'.format(ly, ly_metric)
    if cy_metric and ly_metric:
        cy_color = orange if cy_metric < ly_metric else teal
    else:
        cy_color = white
    return html.Div(className='row text-center align-items-center', children=[

        ### Title ###
        html.Div(id='yoy-title', className='col-lg-4', children=[
            html.Div(children=[
                html.H6('YOY Performance', className='mt-0 mb-0 d-inline-block'),
            ]),
        ]),

        ### Current Year ###
        html.Div(id='target-change-kpi', className='col-lg-4', children=[
            html.Div(children=[
                html.H6(cy_title, className='mt-0 mb-0 d-inline-block',
                        style={'color': cy_color}),
            ]),
        ]),
        ### Last Year ###
        html.Div(id='atl-kpi', className='col-lg-4', children=[
            html.Div(children=[
                html.H6(ly_title, className='mt-0 mb-0 d-inline-block',
                        style={'color': white}),
            ]),
        ])
    ])


def create_yoy_chart(metric, sport='all'):
    '''

    :param metric: Allowed values from strava summary table [hrss, tss, trimp, distance, elapsed_time, high_intensity_seconds, mod_intensity_seconds, low_intensity_seconds]
    :return:
    '''

    # weekly_tss_goal = app.session.query(athlete).filter(athlete.athlete_id == 1).first().weekly_tss_goal

    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False

    if sport != 'all':
        df = pd.read_sql(
            sql=app.session.query(stravaSummary).filter(
                stravaSummary.elapsed_time > athlete_info.min_non_warmup_workout_time,
                stravaSummary.type.like(sport),
            ).statement, con=engine, index_col='start_date_utc').sort_index(ascending=True)
    else:
        df = pd.read_sql(
            sql=app.session.query(stravaSummary).filter(
                stravaSummary.elapsed_time > athlete_info.min_non_warmup_workout_time,
                # or_(
                #     extract('year', stravaSummary.start_date_utc) == datetime.utcnow().year,
                #     extract('year', stravaSummary.start_date_utc) == (datetime.utcnow().year - 1))
            ).statement, con=engine, index_col='start_date_utc').sort_index(ascending=True)

    app.session.remove()

    df['year'] = df.index.year
    df['day'] = df.index.dayofyear

    df = df.pivot_table(index='day', columns='year', values=metric, aggfunc=np.sum).fillna(0)
    df = df.set_index(pd.to_datetime(datetime(1970, 1, 1) + pd.to_timedelta(df.index - 1, 'd')))

    # If new year and no workouts yet, add column
    if datetime.now().year not in df.columns:
        df[datetime.now().year] = np.nan

    # Resample so every day of year is shown on x axis and for yearly goal
    df.at[pd.to_datetime(datetime(1970, 1, 1)), df.columns[0]] = None
    df = df.resample('D').sum()
    df = df[:-1]

    # Remove future days of current year
    df[df.columns[-1]] = np.where(df.index.dayofyear > datetime.now().timetuple().tm_yday, np.nan, df[df.columns[-1]])

    data = []
    colors = [teal, white, light_blue, dark_blue, ctl_color, atl_color, tsb_color, orange, 'rgba(250, 47, 76,.7)',
              orange]

    # Plot latest line first for most recent 10 years
    index, current_date, cy_metric, ly_metric, target = 0, None, None, None, None
    for year in list(df.columns)[9:-12:-1]:
        if metric in ['elapsed_time', 'high_intensity_seconds', 'low_intensity_seconds', 'mod_intensity_seconds']:
            text = ['{}: <b>{}'.format(str(year), timedelta(seconds=x)) for x in df[year].cumsum().fillna(0)]
        elif metric == 'distance':
            text = ['{}: <b>{:.1f} mi'.format(str(year), x) for x in df[year].cumsum().fillna(0)]
        elif metric in ['hrss', 'trimp', 'tss']:
            text = ['{}: <b>{:.0f}'.format(str(year), x) for x in df[year].cumsum().fillna(0)]

        data.append(
            go.Scatter(
                name=str(year),
                x=df.index,
                y=df[year].cumsum(),
                mode='lines',
                text=text,
                hoverinfo='x+text',
                customdata=[
                    '{}'.format(f'cy|{metric}|{year}' if index == 0 else f'ly|{metric}|{year}' if index == 1 else None)
                    for x in df.index],
                line={'shape': 'spline', 'color': colors[index]},
                # Default to only CY and PY shown
                visible=True if index < 2 else 'legendonly'
            )
        )
        # Store current data points for hoverdata kpi initial values
        if index == 0:
            temp_df = df[~np.isnan(df[year])]
            temp_df[year] = temp_df[year].cumsum()
            current_date = temp_df.index.max()
            cy_metric = temp_df.loc[current_date][year]
            cy = year
        if index == 1:
            temp_df[year] = temp_df[year].cumsum()
            ly_metric = temp_df.loc[current_date][year]
            ly = year
        index += 1

    # Multiply by 40 weeks in the year (roughly 3 week on 1 off)
    # df['daily_tss_goal'] = (weekly_tss_goal * 52) / 365
    # temp_df['daily_tss_goal'] = df['daily_tss_goal'].cumsum()
    # target = temp_df.loc[current_date]['daily_tss_goal']

    # data.append(
    #     go.Scatter(
    #         name='SS Goal',
    #         x=df.index,
    #         y=df['daily_tss_goal'].cumsum(),
    #         mode='lines',
    #         customdata=['target' for x in df.index],
    #         hoverinfo='x',
    #         line={'dash': 'dot',
    #               'color': 'rgba(127, 127, 127, .35)',
    #               'width': 2},
    #         # showlegend=False
    #     )
    # )

    hoverData = dict(points=[
        {'x': current_date, 'y': cy_metric, 'customdata': f'cy|{metric}|{cy}'},
        {'x': current_date, 'y': ly_metric, 'customdata': f'ly|{metric}|{ly}'},
        # {'x': current_date, 'y': target, 'customdata': 'target'}
    ])

    figure = {
        'data': data,
        'layout': go.Layout(
            # transition=dict(duration=transition),
            font=dict(
                size=10,
                color=white
            ),
            height=416,
            xaxis=dict(
                showgrid=False,
                showticklabels=True,
                tickformat='%b %d',
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgb(73, 73, 73)',
                gridwidth=.5,
            ),
            # Set margins to 0, style div sets padding
            margin={'l': 40, 'b': 25, 't': 10, 'r': 20},
            showlegend=True,
            legend=dict(
                x=.5,
                y=1,
                bgcolor='rgba(0,0,0,0)',
                xanchor='center',
                orientation='h',
            ),
            autosize=True,
            hovermode='x'
        )
    }
    return figure, hoverData


def get_workout_types(df_summary, run_status, ride_status, all_status):
    df_summary['type'] = df_summary['type'].fillna('REMOVE')
    df_summary = df_summary[df_summary['type'] != 'REMOVE']
    # Generate list of all workout types for when the 'all' boolean is selected
    other_workout_types = [x for x in df_summary['type'].unique() if 'ride' not in x.lower() and 'run' not in x.lower()]
    run_workout_types = [x for x in df_summary['type'].unique() if 'run' in x.lower()]
    ride_workout_types = [x for x in df_summary['type'].unique() if 'ride' in x.lower()]
    # Concat all types into 1 list based of switches selected
    workout_types = []
    workout_types = workout_types + other_workout_types if all_status else workout_types
    workout_types = workout_types + ride_workout_types if ride_status else workout_types
    workout_types = workout_types + run_workout_types if run_status else workout_types
    return workout_types


def create_fitness_chart(run_status, ride_status, all_status, power_status, hr_status, atl_status):
    df_summary = pd.read_sql(sql=app.session.query(stravaSummary).statement, con=engine,
                             index_col='start_date_local').sort_index(ascending=True)

    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    rr_max_threshold = athlete_info.rr_max_goal
    rr_min_threshold = athlete_info.rr_min_goal

    use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False

    ## Readiness score now exists in get_hrv_df()
    # df_readiness = pd.read_sql(
    #     sql=app.session.query(ouraReadinessSummary.report_date, ouraReadinessSummary.score).statement,
    #     con=engine,
    #     index_col='report_date').sort_index(ascending=True)

    df_sleep = pd.read_sql(
        sql=app.session.query(ouraSleepSummary.report_date, ouraSleepSummary.score).statement,
        con=engine,
        index_col='report_date').sort_index(ascending=True)
    df_sleep = df_sleep.rename(columns={'score': 'sleep_score'})

    df_plan = pd.read_sql(
        sql=app.session.query(workoutStepLog.date, workoutStepLog.workout_step,
                              workoutStepLog.workout_step_desc, workoutStepLog.rationale).statement,
        con=engine,
        index_col='date').sort_index(ascending=True)

    df_annotations = pd.read_sql(
        sql=app.session.query(annotations.athlete_id, annotations.date, annotations.annotation).filter(
            athlete.athlete_id == 1).statement,
        con=engine,
        index_col='date').sort_index(ascending=False)

    app.session.remove()

    chart_annotations = [go.layout.Annotation(
        x=pd.to_datetime(x),
        y=0,
        xref="x",
        yref="y",
        text=y,
        arrowcolor=white,
        showarrow=True,
        arrowhead=3,
        # ax=0,
        # ay=-100
    ) for (x, y) in zip(df_annotations.index, df_annotations.annotation)
    ]

    if oura_credentials_supplied:
        hrv_df = get_hrv_df()

    # Create flag to color tss bars when ftp test - use number so column remains through resample
    df_new_run_ftp = df_summary[df_summary['type'].str.lower().str.contains('run')]
    df_new_run_ftp['new_run_ftp_flag'] = 0
    if len(df_new_run_ftp) > 0:
        df_new_run_ftp['previous_ftp'] = df_new_run_ftp['ftp'].shift(1)
        df_new_run_ftp = df_new_run_ftp[~np.isnan(df_new_run_ftp['previous_ftp'])]
        df_new_run_ftp.loc[df_new_run_ftp['previous_ftp'] > df_new_run_ftp['ftp'], 'new_run_ftp_flag'] = -1
        df_new_run_ftp.loc[df_new_run_ftp['previous_ftp'] < df_new_run_ftp['ftp'], 'new_run_ftp_flag'] = 1
        # Highlight the workout which caused the new FTP to be set
        df_new_run_ftp['new_run_ftp_flag'] = df_new_run_ftp['new_run_ftp_flag'].shift(-1)

    df_new_ride_ftp = df_summary[df_summary['type'].str.lower().str.contains('ride')]
    df_new_ride_ftp['new_ride_ftp_flag'] = 0
    if len(df_new_ride_ftp) > 0:
        df_new_ride_ftp['previous_ftp'] = df_new_ride_ftp['ftp'].shift(1)
        df_new_ride_ftp = df_new_ride_ftp[~np.isnan(df_new_ride_ftp['previous_ftp'])]
        df_new_ride_ftp.loc[df_new_ride_ftp['previous_ftp'] > df_new_ride_ftp['ftp'], 'new_ride_ftp_flag'] = -1
        df_new_ride_ftp.loc[df_new_ride_ftp['previous_ftp'] < df_new_ride_ftp['ftp'], 'new_ride_ftp_flag'] = 1
        # Highlight the workout which caused the new FTP to be set
        df_new_ride_ftp['new_ride_ftp_flag'] = df_new_ride_ftp['new_ride_ftp_flag'].shift(-1)

    # Add flags back to main df
    df_summary = df_summary.merge(df_new_run_ftp['new_run_ftp_flag'].to_frame(), how='left', left_index=True,
                                  right_index=True)
    df_summary = df_summary.merge(df_new_ride_ftp['new_ride_ftp_flag'].to_frame(), how='left', left_index=True,
                                  right_index=True)

    df_summary.loc[df_summary['new_run_ftp_flag'] == 1, 'tss_flag'] = 1
    df_summary.loc[df_summary['new_run_ftp_flag'] == -1, 'tss_flag'] = -1
    df_summary.loc[df_summary['new_ride_ftp_flag'] == 1, 'tss_flag'] = 1
    df_summary.loc[df_summary['new_ride_ftp_flag'] == -1, 'tss_flag'] = -1

    # Create df of ftp tests to plot
    forecast_days = 13
    atl_days = 7
    initial_atl = 0
    atl_exp = np.exp(-1 / atl_days)
    ctl_days = 42
    initial_ctl = 0
    ctl_exp = np.exp(-1 / ctl_days)

    # Insert dummy row with current date+forecast_days to ensure resample gets all dates
    df_summary.loc[utc_to_local(datetime.utcnow()) + timedelta(days=forecast_days)] = None

    if power_status and hr_status:
        # If tss not available, use hrss
        df_summary['stress_score'] = df_summary.apply(lambda row: row['hrss'] if np.isnan(row['tss']) else row['tss'],
                                                      axis=1).fillna(0)
    elif power_status:
        df_summary['stress_score'] = df_summary['tss']
    elif hr_status:
        df_summary['stress_score'] = df_summary['hrss']
    else:
        df_summary['stress_score'] = 0

    # Calculate Metrics
    # Fitness and Form will change based off booleans that are selected
    # ATL should always be based off of ALL sports so toggle defaults to true
    # However if user wants to just see ATL for toggled sports they can disable toggle
    workout_types = get_workout_types(df_summary, run_status, ride_status, all_status)

    # Sample to daily level and sum stress scores to aggregate multiple workouts per day
    if not atl_status:
        atl_df = df_summary
        atl_df.at[~atl_df['type'].isin(workout_types), 'stress_score'] = 0
        atl_df.at[~atl_df['type'].isin(workout_types), 'tss'] = 0
        atl_df.at[~atl_df['type'].isin(workout_types), 'hrss'] = 0
        atl_df = atl_df[['stress_score', 'tss', 'hrss']].resample('D').sum()
    else:
        atl_df = df_summary[['stress_score', 'tss', 'hrss']].resample('D').sum()

    atl_df['ATL'] = np.nan
    atl_df['ATL'].iloc[0] = (atl_df['stress_score'].iloc[0] * (1 - atl_exp)) + (initial_atl * atl_exp)
    for i in range(1, len(atl_df)):
        atl_df['ATL'].iloc[i] = (atl_df['stress_score'].iloc[i] * (1 - atl_exp)) + (atl_df['ATL'].iloc[i - 1] * atl_exp)
    atl_df['atl_tooltip'] = ['Fatigue: <b>{:.1f} ({}{:.1f})</b>'.format(x, '+' if x - y > 0 else '', x - y) for (x, y)
                             in zip(atl_df['ATL'], atl_df['ATL'].shift(1))]

    atl_df = atl_df.drop(columns=['stress_score', 'tss', 'hrss'])

    # Sample to daily level and sum stress scores to aggregate multiple workouts per day

    pmd = df_summary[df_summary['type'].isin(workout_types)]
    # Make sure df goes to same max date as ATL df
    pmd.at[atl_df.index.max(), 'name'] = None

    pmd = pmd[
        ['stress_score', 'tss', 'hrss', 'low_intensity_seconds', 'mod_intensity_seconds', 'high_intensity_seconds',
         'tss_flag']].resample('D').sum()

    pmd['CTL'] = np.nan
    pmd['CTL'].iloc[0] = (pmd['stress_score'].iloc[0] * (1 - ctl_exp)) + (initial_ctl * ctl_exp)
    for i in range(1, len(pmd)):
        pmd['CTL'].iloc[i] = (pmd['stress_score'].iloc[i] * (1 - ctl_exp)) + (pmd['CTL'].iloc[i - 1] * ctl_exp)

    # Merge pmd into ATL df
    pmd = pmd.merge(atl_df, how='right', right_index=True, left_index=True)

    pmd['l90d_low_intensity'] = pmd['low_intensity_seconds'].rolling(90).sum()
    pmd['l90d_high_intensity'] = (pmd['mod_intensity_seconds'] + pmd['high_intensity_seconds']).rolling(90).sum()

    pmd['l90d_percent_high_intensity'] = pmd['l90d_high_intensity'] / (
            pmd['l90d_high_intensity'] + pmd['l90d_low_intensity'])

    pmd['TSB'] = pmd['CTL'].shift(1) - pmd['ATL'].shift(1)
    pmd['Ramp_Rate'] = pmd['CTL'] - pmd['CTL'].shift(7)

    # Tooltips
    pmd['ctl_tooltip'] = ['Fitness: <b>{:.1f} ({}{:.1f})</b>'.format(x, '+' if x - y > 0 else '', x - y) for (x, y)
                          in
                          zip(pmd['CTL'], pmd['CTL'].shift(1))]

    pmd['tsb_tooltip'] = ['Form: <b>{} {:.1f} ({}{:.1f})</b>'.format(x, y, '+' if y - z > 0 else '', y - z) for
                          (x, y, z) in
                          zip(pmd['TSB'].map(training_zone), pmd['TSB'], pmd['TSB'].shift(1))]

    if not use_power:
        pmd['stress_tooltip'] = ['TRIMP:  <b>{:.1f}</b>'.format(x) for x in pmd['stress_score']]
    else:
        pmd['stress_tooltip'] = [
            'Stress: <b>{:.1f}</b><br><br>PSS: <b>{:.1f}</b><br>HRSS: <b>{:.1f}</b>'.format(x, y, z)
            for
            (x, y, z) in zip(pmd['stress_score'], pmd['tss'], pmd['hrss'])]

    # split actuals and forecasts into separata dataframes to plot lines
    actual = pmd[:len(pmd) - forecast_days]
    forecast = pmd[-forecast_days:]
    # Start chart at first point where CTL exists (Start+42 days)
    pmd = pmd[42:]
    actual = actual[42:]
    if oura_credentials_supplied:
        # Merge hrv data into actual df
        actual = actual.merge(hrv_df, how='left', left_index=True, right_index=True)
        # Merge hrv plan redommendation
        actual = actual.merge(df_plan, how='left', left_index=True, right_index=True)
        # Merge readiness and sleep for kpis
        # actual = actual.merge(df_readiness, how='left', left_index=True, right_index=True)
        actual = actual.merge(df_sleep, how='left', left_index=True, right_index=True)

        actual['workout_plan'] = 'rec_' + actual['workout_step'].astype('str') + '|' + \
                                 actual['workout_step_desc'] + '|' + \
                                 actual['rationale'] + '|' + \
                                 actual['score'].fillna(0).apply(readiness_score_recommendation) + '|' + \
                                 actual['score'].fillna(0).astype('int').astype('str') + '|' + \
                                 actual['sleep_score'].fillna(0).astype('int').astype('str') + '|' + \
                                 actual['hrv_z_score'].astype('str') + '|' + \
                                 actual['hr_z_score'].astype('str') + '|' + \
                                 actual['hrv7_z_score'].astype('str') + '|' + \
                                 actual['hr7_z_score'].astype('str') + '|' + \
                                 actual['z_desc'].astype('str') + '|' + \
                                 actual['rmssd'].astype('str') + '|' + \
                                 actual['rmssd_yesterday'].astype('str') + '|' + \
                                 actual['rmssd_7'].astype('str') + '|' + \
                                 actual['hr_average'].astype('str') + '|' + \
                                 actual['hr_average_yesterday'].astype('str') + '|' + \
                                 actual['hr_average_7'].astype('str') + '|'
        hover_rec = actual['workout_plan'].tail(1).values[0]

    stress_bar_colors = []
    for i in actual.index:
        if use_power:
            stress_bar_colors.append('green' if actual.at[i, 'tss_flag'] == 1 else 'red' if actual.at[
                                                                                                i, 'tss_flag'] == -1 else 'rgba(127, 127, 127, 1)')
        else:
            stress_bar_colors.append('rgba(127, 127, 127, 1)')

    latest = actual.loc[actual.index.max()]
    yesterday = actual.loc[actual.index.max() - timedelta(days=1)]

    ### Start Graph ###
    hoverData = {'points': [{'x': actual.index.max().date(),
                             'y': latest['CTL'].max(),
                             'text': 'Fitness'},
                            {'y': latest['Ramp_Rate'].max(), 'text': 'Ramp'},
                            {'y': rr_max_threshold, 'text': 'RR High'},
                            {'y': rr_min_threshold, 'text': 'RR Low'},
                            {'y': latest['ATL'].max(), 'text': 'Fatigue'},
                            {'y': latest['TSB'].max(), 'text': 'Form'},
                            ]
                 }

    if oura_credentials_supplied:
        hoverData['points'].extend([{'text': 'HRV: <b>{:.0f} ({}{:.0f})'.format(latest['rmssd'].max(),
                                                                                '+' if latest['rmssd'].max() -
                                                                                       yesterday[
                                                                                           'rmssd'].max() > 0 else '',
                                                                                latest['rmssd'].max() - yesterday[
                                                                                    'rmssd'].max())},
                                    {'text': '7 Day HRV Avg: <b>{:.2f} ({}{:.2f})'.format(latest['rmssd_7'].max(),
                                                                                          '+' if latest[
                                                                                                     'rmssd_7'].max() -
                                                                                                 yesterday[
                                                                                                     'rmssd_7'].max() > 0 else '',
                                                                                          latest['rmssd_7'].max() -
                                                                                          yesterday[
                                                                                              'rmssd_7'].max())},
                                    {'y': latest['detected_trend'],
                                     'text': f'Detected Trend: <b>{latest["detected_trend"]}'}])

    figure = {
        'data': [
            go.Scatter(
                name='Fitness (CTL)',
                x=actual.index,
                y=round(actual['CTL'], 1),
                mode='lines',
                text=actual['ctl_tooltip'],
                hoverinfo='text',
                opacity=0.7,
                line={'shape': 'spline', 'color': ctl_color},
            ),
            go.Scatter(
                name='Fitness (CTL) Forecast',
                x=forecast.index,
                y=round(forecast['CTL'], 1),
                mode='lines',
                text=forecast['ctl_tooltip'],
                hoverinfo='text',
                opacity=0.7,
                line={'shape': 'spline', 'color': ctl_color, 'dash': 'dot'},
                showlegend=False,
            ),
            go.Scatter(
                name='Fatigue (ATL)',
                x=actual.index,
                y=round(actual['ATL'], 1),
                mode='lines',
                text=actual['atl_tooltip'],
                hoverinfo='text',
                line={'color': atl_color},
            ),
            go.Scatter(
                name='Fatigue (ATL) Forecast',
                x=forecast.index,
                y=round(forecast['ATL'], 1),
                mode='lines',
                text=forecast['atl_tooltip'],
                hoverinfo='text',
                line={'color': atl_color, 'dash': 'dot'},
                showlegend=False,
            ),
            go.Scatter(
                name='Form (TSB)',
                x=actual.index,
                y=round(actual['TSB'], 1),
                mode='lines',
                text=actual['tsb_tooltip'],
                hoverinfo='text',
                opacity=0.7,
                line={'color': tsb_color},
                fill='tozeroy',
                fillcolor=tsb_fill_color,
            ),
            go.Scatter(
                name='Form (TSB) Forecast',
                x=forecast.index,
                y=round(forecast['TSB'], 1),
                mode='lines',
                text=forecast['tsb_tooltip'],
                hoverinfo='text',
                opacity=0.7,
                line={'color': tsb_color, 'dash': 'dot'},
                showlegend=False,
            ),
            go.Bar(
                name='Stress',
                x=actual.index,
                y=actual['stress_score'],
                # mode='markers',
                yaxis='y2',
                text=actual['stress_tooltip'],
                hoverinfo='text',
                marker={
                    'color': stress_bar_colors}
            ),

            go.Scatter(
                name='High Intensity',
                x=actual.index,
                y=actual['l90d_percent_high_intensity'],
                mode='markers',
                yaxis='y4',
                text=['L90D % High Intensity:<b> {:.0f}%'.format(x * 100) for x in
                      actual['l90d_percent_high_intensity']],
                hoverinfo='text',
                marker=dict(
                    color=['rgba(250, 47, 76,.7)' if actual.at[
                                                         i, 'l90d_percent_high_intensity'] > .2 else light_blue
                           for i in actual.index],
                )

            ),

            go.Scatter(
                name='80/20 Threshold',
                text=['80/20 Threshold' if x == pmd.index.max() else '' for x in
                      pmd.index],
                textposition='top left',
                x=pmd.index,
                y=[.2 for x in pmd.index],
                yaxis='y4',
                mode='lines+text',
                hoverinfo='none',
                line={'dash': 'dashdot',
                      'color': 'rgba(250, 47, 76,.5)'},
                showlegend=False,
            ),

            go.Scatter(
                name='Ramp Rate',
                x=pmd.index,
                y=pmd['Ramp_Rate'],
                text=['Ramp Rate: {:.1f}'.format(x) for x in pmd['Ramp_Rate']],
                mode='lines',
                hoverinfo='none',
                line={'color': 'rgba(220,220,220,0)'},
                # visible='legendonly',
            ),

            go.Scatter(
                name='Ramp Rate (High)',
                x=pmd.index,
                y=[rr_max_threshold for x in pmd.index],
                text=['RR High' for x in pmd['Ramp_Rate']],
                mode='lines',
                hoverinfo='none',
                line={'color': 'rgba(220,220,220,0)'},
                # visible='legendonly',
            ),
            go.Scatter(
                name='Ramp Rate (Low)',
                x=pmd.index,
                y=[rr_min_threshold for x in pmd.index],
                text=['RR Low' for x in pmd['Ramp_Rate']],
                mode='lines',
                hoverinfo='none',
                line={'color': 'rgba(220,220,220,0)'},
                # visible='legendonly',
            ),

            go.Scatter(
                name='No Fitness',
                text=['No Fitness' if x == pmd.index.max() else '' for x in
                      pmd.index],
                textposition='top left',
                x=pmd.index,
                y=[25 for x in pmd.index],
                mode='lines+text',
                hoverinfo='none',
                line={'dash': 'dashdot',
                      'color': 'rgba(127, 127, 127, .35)'},
                showlegend=False,
            ),
            go.Scatter(
                name='Performance',
                text=['Performance' if x == pmd.index.max() else '' for x in
                      pmd.index],
                textposition='top left',
                x=pmd.index,
                y=[5 for x in pmd.index],
                mode='lines+text',
                hoverinfo='none',
                line={'dash': 'dashdot',
                      'color': 'rgba(127, 127, 127, .35)'},
                showlegend=False,
            ),
            go.Scatter(
                name='Maintenance',
                text=['Maintenance' if x == pmd.index.max() else '' for x in
                      pmd.index],
                textposition='top left',
                x=pmd.index,
                y=[-10 for x in pmd.index],
                mode='lines+text',
                hoverinfo='none',
                line={'dash': 'dashdot',
                      'color': 'rgba(127, 127, 127, .35)'},
                showlegend=False,
            ),
            go.Scatter(
                name='Productive',
                text=['Productive' if x == pmd.index.max() else '' for x in
                      pmd.index],
                textposition='top left',
                x=pmd.index,
                y=[-25 for x in pmd.index],
                mode='lines+text',
                hoverinfo='none',
                line={'dash': 'dashdot',
                      'color': 'rgba(127, 127, 127, .35)'},
                showlegend=False,
            ),
            go.Scatter(
                name='Cautionary',
                text=['Cautionary' if x == pmd.index.max() else '' for x in
                      pmd.index],
                textposition='top left',
                x=pmd.index,
                y=[-40 for x in pmd.index],
                mode='lines+text',
                hoverinfo='none',
                line={'dash': 'dashdot',
                      'color': 'rgba(127, 127, 127, .35)'},
                showlegend=False,
            ),
            go.Scatter(
                name='Overreaching',
                text=['Overreaching' if x == pmd.index.max() else '' for x in
                      pmd.index],
                textposition='top left',
                x=pmd.index,
                y=[-45 for x in pmd.index],
                mode='lines+text',
                hoverinfo='none',
                line={'dash': 'dashdot',
                      'color': 'rgba(127, 127, 127, .35)'},
                showlegend=False,
            ),
        ],
        'layout': go.Layout(
            # transition=dict(duration=transition),
            font=dict(
                size=10,
                color=white
            ),
            annotations=chart_annotations,
            xaxis=dict(
                showgrid=False,
                showticklabels=True,
                tickformat='%b %d',
                # Specify range to get rid of auto x-axis padding when using scatter markers
                range=[pmd.index.max() - timedelta(days=89 + forecast_days),
                       pmd.index.max()],
                # default L6W
                rangeselector=dict(
                    bgcolor='rgb(66, 66, 66)',
                    bordercolor='#d4d4d4',
                    borderwidth=.5,
                    buttons=list([
                        # Specify row count to get rid of auto x-axis padding when using scatter markers
                        dict(count=(len(pmd) + 1),
                             label='ALL',
                             step='day',
                             stepmode='backward'),
                        # Forecast goes into next year, so in December end of year, using 'year' shows the next year
                        # Count the number of days in year instead
                        dict(count=actual.index.max().timetuple().tm_yday + forecast_days,
                             label='YTD',
                             step='day',
                             stepmode='backward'),
                        dict(count=89 + forecast_days,
                             label='L90D',
                             step='day',
                             stepmode='backward'),
                        dict(count=41 + forecast_days,
                             label='L6W',
                             step='day',
                             stepmode='backward'),
                        dict(count=29 + forecast_days,
                             label='L30D',
                             step='day',
                             stepmode='backward'),

                    ]),
                    xanchor='center',
                    font=dict(
                        size=10,
                    ),
                    x=.5,
                    y=1,
                ),
            ),
            yaxis=dict(
                # domain=[0, .85],
                showticklabels=False,
                range=[actual['TSB'].min() * 1.05, actual['ATL'].max() * 1.25],
                showgrid=True,
                gridcolor='rgb(73, 73, 73)',
                gridwidth=.5,
            ),
            yaxis2=dict(
                # domain=[0, .85],
                showticklabels=False,
                range=[0, pmd['stress_score'].max() * 4],
                showgrid=False,
                type='linear',
                side='right',
                anchor='x',
                overlaying='y',
                # layer='above traces'
            ),
            yaxis4=dict(
                # domain=[.85, 1],
                range=[0, 3],
                showgrid=False,
                showticklabels=False,
                anchor='x',
                side='right',
                overlaying='y',
            ),
            margin={'l': 0, 'b': 25, 't': 0, 'r': 0},
            showlegend=False,
            autosize=True,
            bargap=.75,
        )
    }

    # If Oura data supplied, incorporate data into performance management chart
    if oura_credentials_supplied:
        hoverData['points'].extend([{'text': hover_rec},
                                    {'y': hrv_df.tail(1)['rmssd_7'].values[0], 'text': '7 Day'}])
        figure['data'].extend([
            go.Scatter(
                name='SWC Threshold',
                x=actual.index.append(actual.index[::-1]),
                y=pd.concat([actual['swc_baseline_upper'], actual['swc_baseline_lower'][::-1]]),
                text='swc lower',
                yaxis='y3',
                mode='lines',
                hoverinfo='none',
                fill='tonexty',
                line={'color': dark_blue},
            ),
            go.Scatter(
                name='HRV',
                x=actual.index,
                y=actual['ln_rmssd'],
                yaxis='y3',
                mode='lines',
                text=['HRV: <b>{:.0f} ({}{:.0f})'.format(x, '+' if x - y > 0 else '', x - y)
                      for (x, y) in zip(actual['rmssd'], actual['rmssd'].shift(1))],
                hoverinfo='text',
                line={'color': 'rgba(220,220,220,.20)'},
            ),
            go.Scatter(
                name='HRV 7 Day Avg',
                x=actual.index,
                y=actual['ln_rmssd_7'],
                yaxis='y3',
                mode='lines',
                text=['7 Day HRV Avg: <b>{:.2f} ({}{:.2f})'.format(x, '+' if x - y > 0 else '', x - y)
                      for (x, y) in zip(actual['rmssd_7'], actual['rmssd_7'].shift(1))],
                hoverinfo='text',
                line={'color': teal, 'shape': 'spline'},
            ),
            # Dummy scatter to store hrv plan recommendation so hovering data can be stored in hoverdata
            go.Scatter(
                name='Workout Plan Recommendation',
                x=actual.index,
                y=[0 for x in actual.index],
                text=actual['workout_plan'],
                hoverinfo='none',
                marker={'color': 'rgba(0, 0, 0, 0)'}
            ),
        ])

        # Only show workflow hrv thresholds if recovery metric is hrv based
        if athlete_info.recovery_metric in ['hrv_baseline', 'hrv']:
            figure['data'].extend([
                go.Scatter(
                    name='HRV SWC Flowchart (Lower)',
                    x=actual.index,
                    y=actual[
                        'swc_flowchart_lower' if athlete_info.recovery_metric == 'hrv_baseline' else 'swc_daily_lower'],
                    yaxis='y3',
                    mode='lines',
                    hoverinfo='none',
                    line={
                        'color': 'rgba(100, 217, 236,.5)' if athlete_info.recovery_metric == 'hrv_baseline' else 'rgba(220,220,220,.20)',
                        'shape': 'spline', 'dash': 'dot'},
                ),
                go.Scatter(
                    name='HRV SWC Flowchart (Upper)',
                    x=actual.index,
                    y=actual[
                        'swc_flowchart_upper' if athlete_info.recovery_metric == 'hrv_baseline' else 'swc_daily_upper'],
                    yaxis='y3',
                    mode='lines',
                    hoverinfo='none',
                    line={
                        'color': 'rgba(100, 217, 236,.5)' if athlete_info.recovery_metric == 'hrv_baseline' else 'rgba(220,220,220,.20)',
                        'shape': 'spline', 'dash': 'dot'},
                )
            ])

        # ### Trends ###
        #
        # # Automated trend detection: https://www.hrv4training.com/blog/interpreting-hrv-trends
        # actual['ln_rmssd_7'] = actual['ln_rmssd'].rolling(7).mean()
        # # HR baseline
        # actual['hr_average_7'] = actual['hr_average'].rolling(7).mean()
        # # Coefficient of Variation baseline
        # actual['cv_rmssd_7'] = (actual['ln_rmssd'].rolling(7).std() / actual['ln_rmssd'].rolling(7).mean()) * 100
        # # HRV Normalized baseline
        # actual['ln_rmssd_normalized_7'] = actual['ln_rmssd_7'] / actual['AVNN'].rolling(7).mean()
        #
        # # Calculate 2 Week Slopes
        # actual['ln_rmssd_7_slope'] = actual['ln_rmssd_7'].rolling(14).apply(
        #     lambda x: scipy.stats.linregress(range(14), x).slope)
        # actual['hr_average_7_slope'] = actual['hr_average_7'].rolling(14).apply(
        #     lambda x: scipy.stats.linregress(range(14), x).slope)
        # actual['cv_rmssd_7_slope'] = actual['cv_rmssd_7'].rolling(14).apply(
        #     lambda x: scipy.stats.linregress(range(14), x).slope)
        # actual['ln_rmssd_normalized_7_slope'] = actual['ln_rmssd_normalized_7'].rolling(14).apply(
        #     lambda x: scipy.stats.linregress(range(14), x).slope)
        #
        # # Get Stdev and mean for last 60 days worth of slopes
        #
        # # Remove trivial changes
        #
        # # actual.loc[(
        # #                    (actual['ln_rmssd_7'] > (
        # #                            actual['ln_rmssd'].rolling(60, min_periods=0).mean() + actual['ln_rmssd'].rolling(60,
        # #                                                                                                        min_periods=0).std())
        # #                     ) |
        # #                    actual['ln_rmssd_7'] < (
        # #                            actual['ln_rmssd'].rolling(60, min_periods=0).mean() - actual['ln_rmssd'].rolling(60,
        # #                                                                                                        min_periods=0).std())
        # #            ),
        # #            'ln_rmssd_7_slope_trivial'] = actual['ln_rmssd_7_slope']
        #
        # actual.loc[
        #     (
        #             (actual['ln_rmssd_7_slope'] >
        #              (actual['ln_rmssd_7_slope'].rolling(60).mean() + actual['ln_rmssd_7_slope'].rolling(60).std())) |
        #             (actual['ln_rmssd_7_slope'] <
        #              (actual['ln_rmssd_7_slope'].rolling(60).mean() - actual['ln_rmssd_7_slope'].rolling(60).std()))
        #     ), 'ln_rmssd_7_slope_trivial'] = actual['ln_rmssd_7_slope']
        # actual.loc[
        #     (
        #             (actual['hr_average_7_slope'] >
        #              (actual['hr_average_7_slope'].rolling(60).mean() + actual['hr_average_7_slope'].rolling(
        #                  60).std())) |
        #             (actual['hr_average_7_slope'] <
        #              (actual['hr_average_7_slope'].rolling(60).mean() - actual['hr_average_7_slope'].rolling(60).std()))
        #     ), 'hr_average_7_slope_trivial'] = actual['hr_average_7_slope']
        #
        # actual.loc[
        #     (
        #             (actual['cv_rmssd_7_slope'] >
        #              (actual['cv_rmssd_7_slope'].rolling(60).mean() + actual['cv_rmssd_7_slope'].rolling(60).std())) |
        #             (actual['cv_rmssd_7_slope'] <
        #              (actual['cv_rmssd_7_slope'].rolling(60).mean() - actual['cv_rmssd_7_slope'].rolling(60).std()))
        #     ), 'cv_rmssd_7_slope_trivial'] = actual['cv_rmssd_7_slope']
        #
        # actual.loc[
        #     (
        #             (actual['ln_rmssd_normalized_7_slope'] >
        #              (actual['ln_rmssd_normalized_7_slope'].rolling(60).mean() + actual[
        #                  'ln_rmssd_normalized_7_slope'].rolling(60).std())) |
        #             (actual['ln_rmssd_normalized_7_slope'] <
        #              (actual['ln_rmssd_normalized_7_slope'].rolling(60).mean() - actual[
        #                  'ln_rmssd_normalized_7_slope'].rolling(60).std()))
        #     ), 'ln_rmssd_normalized_7_slope_trivial'] = actual['ln_rmssd_normalized_7_slope']
        #
        # # E.O Customization
        # # ATL Normalized baseline
        # actual['atl_7'] = actual['ATL'].rolling(7).mean().fillna(0)
        # actual['atl_7_slope'] = actual['atl_7'].rolling(14).apply(
        #     lambda x: scipy.stats.linregress(range(14), x).slope)
        #
        # actual.loc[
        #     (
        #             (actual['atl_7_slope'] >
        #              (actual['atl_7_slope'].rolling(60).mean() + actual['atl_7_slope'].rolling(60).std())) |
        #             (actual['atl_7_slope'] <
        #              (actual['atl_7_slope'].rolling(60).mean() - actual['atl_7_slope'].rolling(60).std()))
        #     ), 'atl_7_slope_trivial'] = actual['atl_7_slope']
        #
        # # Fill slopes with 0 when non trivial for trend detection
        # for col in actual.columns:
        #     if 'trivial' in col:
        #         actual[col] = actual[col].fillna(0)
        #
        # # Check for trend
        # actual["detected_trend"] = actual[
        #     ["ln_rmssd_7_slope_trivial", "hr_average_7_slope_trivial", "cv_rmssd_7_slope_trivial",
        #      "ln_rmssd_normalized_7_slope_trivial", "atl_7_slope_trivial"]].apply(lambda x: detect_trend(*x), axis=1)
        #
        # ### Depricated: This overwrites any other trends identified within the rolling 14 days
        # # Highlight the 14 days that the trend is actually calculated on
        # # For every trend that has been detected, highlight the 14 days prior to that day with the trend
        # # for i in actual.index:
        # #     for d in range(0, 14):
        # #         if actual.loc[i]['detected_trend'] != 'No Relevant Trends':
        # #             actual.at[i - timedelta(days=d + 1), 'detected_trend'] = actual.loc[i]['detected_trend']
        #
        # # Debugging
        # # actual[
        # #     ["ln_rmssd_7_slope_trivial", "hr_average_7_slope_trivial", "cv_rmssd_7_slope_trivial",
        # #      "ln_rmssd_normalized_7_slope_trivial"]].to_csv('actual.csv', sep=',')
        #

        # Plot training adaptation on the hrv 7 day average line
        for trend in actual['detected_trend'].unique():
            if trend not in ['No Trend Detected']:
                actual.loc[actual['detected_trend'] == trend, trend] = actual['ln_rmssd_7']

                color = z_color(trend)

                ### Detected Trends ###
                figure['data'].append(
                    go.Scatter(
                        name=trend,
                        x=actual.index,
                        y=actual[trend],
                        text=[f'Detected Trend: <b>{trend}' for x in actual['detected_trend']],
                        yaxis='y3',
                        mode='markers',
                        hoverinfo='none',
                        marker=dict(
                            color=color,
                            line=dict(
                                color='rgba(66,66,66,.75)',
                                width=1
                            )
                        ),
                    )
                )

            figure['layout']['yaxis3'] = dict(
                # domain=[.85, 1],
                range=[actual['ln_rmssd_7'].min() * .3, actual['ln_rmssd_7'].max() * 1.05],
                showgrid=False,
                showticklabels=False,
                anchor='x',
                side='right',
                overlaying='y',
            )

    return figure, hoverData


def workout_distribution(sport='Ride', days=90, intensity='all'):
    min_non_warmup_workout_time = app.session.query(athlete).filter(
        athlete.athlete_id == 1).first().min_non_warmup_workout_time

    df_summary = pd.read_sql(
        sql=app.session.query(stravaSummary).filter(
            stravaSummary.start_date_utc >= datetime.utcnow() - timedelta(days=days),
            stravaSummary.type.like(sport),
            stravaSummary.elapsed_time > min_non_warmup_workout_time,
            or_(stravaSummary.low_intensity_seconds > 0, stravaSummary.mod_intensity_seconds > 0,
                stravaSummary.high_intensity_seconds > 0)
        ).statement,
        con=engine, index_col='start_date_utc')

    if intensity != 'all':
        df_summary = df_summary[df_summary['workout_intensity'] == intensity]

    athlete_bookmarks = json.loads(app.session.query(athlete.peloton_auto_bookmark_ids).filter(
        athlete.athlete_id == 1).first().peloton_auto_bookmark_ids)

    app.session.remove()

    # Clean up workout names for training discribution table (% of total)
    df_summary['workout'] = 'Other'

    class_names = []
    for x in athlete_bookmarks.keys():
        for y in athlete_bookmarks[x].keys():
            for class_type in json.loads(athlete_bookmarks[x][y]):
                try:
                    new_class = re.findall(r'min\s(.*)\s', class_type)[0]
                except:
                    new_class = None
                if new_class and new_class not in class_names:
                    class_names.append(new_class)

    # class_names = ['Power Zone Max', 'Power Zone Endurance', 'Power Zone', 'Endurance', 'Recovery', 'Speed',
    #                'Intervals', 'HIIT',
    #                'Progression', 'Race Prep', 'Tabata', 'Hills', 'Long', 'Fun', 'Tempo']  # , '5k', '10k', 'Marathon']
    for name in class_names:
        for i in df_summary.index:
            if name.lower() in df_summary.loc[i]['name'].lower():
                df_summary.at[i, 'workout'] = name
                continue

    # Categorize 5k, 10k half and marathon as 'Race'
    df_summary['workout'] = df_summary['workout'].replace({'5k': 'Race', '10k': 'Race', 'Marathon': 'Race'})

    # Shorten 'Power Zone' to 'PZ'
    df_summary['workout'] = df_summary['workout'].str.replace('Power Zone', 'PZ')
    # Categorize Free runs at zone pace
    df_summary.loc[df_summary['name'].str.lower().str.contains('zone') & df_summary['name'].str.lower().str.contains(
        'pace'), 'workout'] = 'Z Pace'
    # Categorize all yoga as 'Yoga'
    df_summary.loc[df_summary['type'] == 'Yoga', 'workout'] = 'Yoga'
    # Categorize all WeightTraining as 'Weights'
    df_summary.loc[df_summary['type'] == 'WeightTraining', 'workout'] = 'Weights'
    # Categorize all hikes as 'Hike'
    df_summary.loc[df_summary['type'] == 'Hike', 'workout'] = 'Hike'

    # # Split into intensity subsets workout as low/med/high
    # df_summary['high_intensity_seconds'] = df_summary['high_intensity_seconds'] + df_summary['mod_intensity_seconds']
    # df_summary['intensity'] = df_summary[
    #     ['low_intensity_seconds', 'mod_intensity_seconds', 'high_intensity_seconds']].idxmax(axis=1)

    # df_summary['total_intensity_seconds'] = df_summary['high_intensity_seconds'].fillna(0) + df_summary[
    #     'mod_intensity_seconds'].fillna(0) + \
    #                                         df_summary['low_intensity_seconds'].fillna(0)

    df_summary['total_intensity_seconds'] = df_summary['moving_time']  # Replacing different intensity groups for now
    df_summary['intensity'] = 'total_intensity_seconds'

    # Set up columns for table
    col_names = ['Activity', '%']  # , 'Time']

    # for intensity in ['high_intensity_seconds', 'low_intensity_seconds']:
    df_temp = df_summary[df_summary['intensity'] == 'total_intensity_seconds']
    df_temp = df_temp.groupby('workout')[['total_intensity_seconds', 'elapsed_time']].sum()
    df_temp['workout'] = df_temp.index
    # Format time (seconds) as time intervals
    df_temp['time'] = df_temp['total_intensity_seconds'].apply(
        lambda x: '{}'.format(timedelta(seconds=int(x))))

    # df_temp['elapsed_time'] = df_temp['elapsed_time'].apply(
    #     lambda x: '{}'.format(timedelta(seconds=int(x))))

    df_temp['Percent of Total'] = (df_temp['total_intensity_seconds'] / df_temp[
        'total_intensity_seconds'].sum()) * 100
    df_temp['Percent of Total'] = df_temp['Percent of Total'].apply(lambda x: '{:.0f}%'.format(x))

    return df_temp.sort_values(ascending=False, by=['total_intensity_seconds']).to_dict('records')


def workout_summary_kpi(df_samples):
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False
    app.session.remove()
    height = '25%' if use_power else '33%'

    data = [
        html.Div(className='align-items-center text-center', style={'height': height}, children=[
            html.H5('Power', className=' mb-0'),
            html.P('Max: {:.0f}'.format(df_samples['watts'].max()), className='mb-0'),
            html.P('Avg: {:.0f}'.format(df_samples['watts'].mean()), className='mb-0'),
            html.P('Min: {:.0f}'.format(df_samples['watts'].min()), className='mb-0')
        ]),
        html.Div(className='align-items-center text-center', style={'height': height}, children=[
            html.H5('Heartrate', className='mb-0'),
            html.P('Max: {:.0f}'.format(df_samples['heartrate'].max()), className='mb-0'),
            html.P('Avg: {:.0f}'.format(df_samples['heartrate'].mean()), className=' mb-0'),
            html.P('Min: {:.0f}'.format(df_samples['heartrate'].min()), className=' mb-0')
        ]),
        html.Div(className='align-items-center text-center', style={'height': height}, children=[
            html.H5('Speed', className=' mb-0'),
            html.P('Max: {:.1f}'.format(df_samples['velocity_smooth'].max()), className=' mb-0'),
            html.P('Avg: {:.1f}'.format(df_samples['velocity_smooth'].mean()), className=' mb-0'),
            html.P('Min: {:.1f}'.format(df_samples['velocity_smooth'].min()), className='mb-0')
        ]),
        html.Div(className='align-items-center text-center', style={'height': height}, children=[
            html.H5('Cadence', className=' mb-0'),
            html.P('Max: {:.0f}'.format(df_samples['cadence'].max()), className=' mb-0'),
            html.P('Avg: {:.0f}'.format(df_samples['cadence'].mean()), className=' mb-0'),
            html.P('Min: {:.0f}'.format(df_samples['cadence'].min()), className=' mb-0')
        ])
    ]
    if not use_power:
        data = data[1:]
    return data


def workout_details(df_samples, start_seconds=None, end_seconds=None):
    '''
    :param df_samples filtered on 1 activity
    :return: metric trend charts
    '''
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False
    app.session.remove()

    df_samples['watts'] = df_samples['watts'].fillna(0)
    df_samples['heartrate'] = df_samples['heartrate'].fillna(0)
    df_samples['velocity_smooth'] = df_samples['velocity_smooth'].fillna(0)
    df_samples['cadence'] = df_samples['cadence'].fillna(0)

    # Create df of records to highlight if clickData present from callback
    if start_seconds is not None and end_seconds is not None:
        highlight_df = df_samples[(df_samples['time'] >= int(start_seconds)) & (df_samples['time'] <= int(end_seconds))]

    else:
        highlight_df = df_samples[df_samples['activity_id'] == 0]  # Dummy

    # Remove best points from main df_samples so lines do not overlap nor show 2 hoverinfos
    for idx, row in df_samples.iterrows():
        if idx in highlight_df.index:
            df_samples.loc[idx, 'velocity_smooth'] = np.nan
            df_samples.loc[idx, 'cadence'] = np.nan
            df_samples.loc[idx, 'heartrate'] = np.nan
            df_samples.loc[idx, 'watts'] = np.nan

    data = [
        go.Scatter(
            name='Speed',
            x=df_samples['time_interval'],
            y=round(df_samples['velocity_smooth'], 1),
            # hoverinfo='x+y',
            yaxis='y2',
            mode='lines',
            line={'color': teal}
        ),
        go.Scatter(
            name='Speed',
            x=highlight_df['time_interval'],
            y=round(highlight_df['velocity_smooth'], 1),
            # hoverinfo='x+y',
            yaxis='y2',
            mode='lines',
            line={'color': orange}
        ),
        go.Scatter(
            name='Cadence',
            x=df_samples['time_interval'],
            y=round(df_samples['cadence']),
            # hoverinfo='x+y',
            yaxis='y',
            mode='lines',
            line={'color': teal}
        ),
        go.Scatter(
            name='Cadence',
            x=highlight_df['time_interval'],
            y=round(highlight_df['cadence']),
            # hoverinfo='x+y',
            yaxis='y',
            mode='lines',
            line={'color': orange}
        ),
        go.Scatter(
            name='Heart Rate',
            x=df_samples['time_interval'],
            y=round(df_samples['heartrate']),
            # hoverinfo='x+y',
            yaxis='y3',
            mode='lines',
            line={'color': teal}
        ),
        go.Scatter(
            name='Heart Rate',
            x=highlight_df['time_interval'],
            y=round(highlight_df['heartrate']),
            # hoverinfo='x+y',
            yaxis='y3',
            mode='lines',
            line={'color': orange}
        ),
    ]

    if use_power:
        data.extend([
            go.Scatter(
                name='Power',
                x=df_samples['time_interval'],
                y=round(df_samples['watts']),
                # hoverinfo='x+y',
                yaxis='y4',
                mode='lines',
                line={'color': teal}
            ),
            go.Scatter(
                name='Power',
                x=highlight_df['time_interval'],
                y=round(highlight_df['watts']),
                # hoverinfo='x+y',
                yaxis='y4',
                mode='lines',
                line={'color': orange}
            )
        ])

    return html.Div([
        dcc.Graph(
            id='trends', style={'height': '100%'},
            config={
                'displayModeBar': False,
            },
            # figure= fig

            figure={
                'data': data,
                'layout': go.Layout(
                    # transition=dict(duration=transition),

                    font=dict(
                        size=10,
                        color=white
                    ),
                    # TODO: Subplot unified tooltip not yet supported https://github.com/plotly/plotly.js/issues/4755
                    # hovermode='x unified',
                    hovermode='x',
                    paper_bgcolor='rgb(66,66,66)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin={'l': 40, 'b': 25, 't': 5, 'r': 40},
                    showlegend=False,
                    # legend={'x': .5, 'y': 1.05, 'xanchor': 'center', 'orientation': 'h',
                    #         'traceorder': 'normal', 'bgcolor': 'rgba(127, 127, 127, 0)'},
                    xaxis=dict(
                        showticklabels=True,
                        showgrid=False,
                        showline=True,
                        tickformat="%Mm",
                        hoverformat="%H:%M:%S",
                        # spikemode='across',
                        # showspikes=True,
                        # spikesnap='cursor',
                        zeroline=False,
                        # tickvals=[1, 2, 5, 10, 30, 60, 120, 5 * 60, 10 * 60, 20 * 60, 60 * 60, 60 * 90],
                        # ticktext=['1s', '2s', '5s', '10s', '30s', '1m',
                        #           '2m', '5m', '10m', '20m', '60m', '90m'],
                    ),
                    yaxis=dict(
                        color=white,
                        showticklabels=True,
                        tickvals=[df_samples['cadence'].min(),
                                  # round(df_samples['cadence'].mean()),
                                  df_samples['cadence'].max()],
                        zeroline=False,
                        domain=[0, 0.24] if use_power else [0, 0.32],
                        anchor='x'
                    ),
                    yaxis2=dict(
                        color=white,
                        showticklabels=True,
                        tickvals=[round(df_samples['velocity_smooth'].min()),
                                  # round(df_samples['velocity_smooth'].mean()),
                                  round(df_samples['velocity_smooth'].max())],
                        zeroline=False,
                        domain=[0.26, 0.49] if use_power else [.34, 0.66],
                        anchor='x'
                    ),
                    yaxis3=dict(
                        color=white,
                        showticklabels=True,
                        tickvals=[df_samples['heartrate'].min(),
                                  # round(df_samples['heartrate'].mean()),
                                  df_samples['heartrate'].max()],
                        zeroline=False,
                        domain=[0.51, 0.74] if use_power else [0.68, 1],
                        anchor='x'
                    ),
                    yaxis4=dict(
                        color=white,
                        showticklabels=True,
                        tickvals=[df_samples['watts'].min(),
                                  # round(df_samples['watts'].mean()),
                                  df_samples['watts'].max()],
                        zeroline=False,
                        domain=[0.76, 1],
                        anchor='x'
                    ) if use_power else None

                )
            }
        )])


def calculate_splits(df_samples):
    if np.isnan(df_samples['distance'].max()):
        return None
    else:
        df_samples['miles'] = df_samples['distance'] * 0.000189394
        df_samples['mile_marker'] = df_samples['miles'].apply(np.floor)
        df_samples['mile_marker_previous'] = df_samples['mile_marker'].shift(1)

        df_samples = df_samples[(df_samples['mile_marker'] != df_samples['mile_marker_previous']) |
                                (df_samples.index == df_samples.index.max())]
        df_samples = df_samples.iloc[1:]

        df_samples['time_prev'] = df_samples['time'].shift(1).fillna(0)

        df_samples['time'] = df_samples['time'] - df_samples['time_prev']

        # Get remainder of miles for final mile_marker and normalize final time for non full mile to get accurate pace if remaining mileage at end of ride exists
        max_index = df_samples.index.max()
        if df_samples.at[max_index, 'mile_marker'] == df_samples.at[max_index, 'mile_marker_previous']:
            df_samples.at[max_index, 'mile_marker'] = df_samples.at[max_index, 'miles'] % 1
            df_samples.at[max_index, 'time'] = df_samples.at[max_index, 'time'] / df_samples.at[
                max_index, 'mile_marker']
            # Format as 2 decimal places after calculation is done for pace so table looks nice
            df_samples.at[max_index, 'mile_marker'] = round(df_samples.at[max_index, 'miles'] % 1, 2)

        df_samples['time_str'] = ['{:02.0f}:{:02.0f} /mi'.format(x // 60, (x % 60)) for x in df_samples['time']]

        df_samples_table_columns = ['mile_marker', 'time_str']
        col_names = ['Mile', 'Pace']

        return html.Div(className='table', style={'height': '100%'}, children=[
            dash_table.DataTable(
                columns=[{"name": x, "id": y} for (x, y) in
                         zip(col_names, df_samples[df_samples_table_columns].columns)],
                data=df_samples[df_samples_table_columns].sort_index(ascending=True).to_dict('records'),
                style_as_list_view=True,
                fixed_rows={'headers': True, 'data': 0},
                style_table={'height': '100%'},
                style_header={'backgroundColor': 'rgba(0, 0, 0, 0)',
                              # 'borderBottom': '1px solid rgb(220, 220, 220)',
                              'textAlign': 'center',
                              'borderTop': '0px',
                              # 'fontWeight': 'bold',
                              'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                              },
                style_cell={
                    'backgroundColor': 'rgba(0, 0, 0, 0)',
                    'textAlign': 'center',
                    # 'borderBottom': '1px solid rgb(73, 73, 73)',
                    'maxWidth': 100,
                    'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                },
                style_cell_conditional=[
                    {
                        'if': {'column_id': c},
                        'display': 'none'
                    } for c in ['activity_id']
                ],
                filter_action="none",
                page_action="none",
                # page_current=0,
                # page_size=10,
            )
        ])


def create_annotation_table():
    df_annotations = pd.read_sql(
        sql=app.session.query(annotations.athlete_id, annotations.date, annotations.annotation).filter(
            athlete.athlete_id == 1).statement,
        con=engine).sort_index(ascending=False)

    app.session.remove()

    return dash_table.DataTable(id='annotation-table',
                                columns=[{"name": x, "id": y} for (x, y) in
                                         zip(['Date', 'Annotation'], ['date', 'annotation'])],
                                data=df_annotations[['date', 'annotation']].sort_index(ascending=False).to_dict(
                                    'records'),
                                style_as_list_view=True,
                                fixed_rows={'headers': True, 'data': 0},
                                style_table={'height': '100%'},
                                style_header={'backgroundColor': 'rgba(0,0,0,0)',
                                              'borderBottom': '1px solid rgb(220, 220, 220)',
                                              'borderTop': '0px',
                                              'textAlign': 'left',
                                              'fontWeight': 'bold',
                                              'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                                              },
                                style_cell={
                                    'backgroundColor': 'rgba(0,0,0,0)',
                                    # 'color': 'rgb(220, 220, 220)',
                                    'borderBottom': '1px solid rgb(73, 73, 73)',
                                    'textAlign': 'center',
                                    # 'maxWidth': 175,
                                    'fontFamily': '"Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif',
                                },
                                style_cell_conditional=[
                                    {
                                        'if': {'column_id': 'activity_id'},
                                        'display': 'none'
                                    }
                                ],
                                filter_action="none",
                                editable=True,
                                row_deletable=True,
                                page_action="none",
                                )


# PMC KPIs
@app.callback(
    [Output('daily-recommendations', 'children'),
     Output('pmd-kpi', 'children')],
    [Input('pm-chart', 'hoverData')])
def update_fitness_kpis(hoverData):
    date, fitness, ramp, fatigue, form, hrv, hrv_change, hrv7, hrv7_change, plan_rec, trend = None, None, None, None, None, None, None, None, None, None, None
    if hoverData is not None:
        if len(hoverData['points']) > 3:
            date = hoverData['points'][0]['x']
            for point in hoverData['points']:
                try:
                    if 'Fitness' in point['text']:
                        fitness = point['y']
                    if 'Ramp' in point['text']:
                        ramp = point['y']
                    if 'RR High' in point['text']:
                        rr_max_threshold = point['y']
                    if 'RR Low' in point['text']:
                        rr_min_threshold = point['y']
                    if 'Fatigue' in point['text']:
                        fatigue = point['y']
                    if 'Form' in point['text']:
                        form = point['y']
                    if '7 Day' in point['text']:
                        hrv7 = float(re.findall(r'(?<=\>)(.*?)(?=\s)', point['text'])[0])
                    if 'rec_' in point['text']:
                        plan_rec = point['text']
                    if 'Trend:' in point['text']:
                        trend = point['text'].replace("Detected Trend: <b>", '')
                except:
                    continue

            return create_daily_recommendations(plan_rec) if oura_credentials_supplied else [], \
                   create_fitness_kpis(date, fitness, ramp, rr_max_threshold, rr_min_threshold, fatigue, form, hrv7,
                                       trend)


# PMD Boolean Switches
@app.callback(
    [Output('pm-chart', 'figure'),
     Output('pm-chart', 'hoverData')],
    [Input('ride-pmc-switch', 'on'),
     Input('run-pmc-switch', 'on'),
     Input('all-pmc-switch', 'on'),
     Input('power-pmc-switch', 'on'),
     Input('hr-pmc-switch', 'on'),
     Input('atl-pmc-switch', 'on')],
    [State('ride-pmc-switch', 'on'),
     State('run-pmc-switch', 'on'),
     State('all-pmc-switch', 'on'),
     State('power-pmc-switch', 'on'),
     State('hr-pmc-switch', 'on'),
     State('atl-pmc-switch', 'on')
     ]
)
def refresh_fitness_chart(ride_switch, run_switch, all_switch, power_switch, hr_switch, atl_pmc_switch, ride_status,
                          run_status, all_status, power_status, hr_status, atl_status):
    pmc_switch_settings = {'ride_status': ride_status, 'run_status': run_status, 'all_status': all_status,
                           'power_status': power_status, 'hr_status': hr_status, 'atl_status': atl_status}
    ### Save Switch settings in DB ###
    app.session.query(athlete).filter(athlete.athlete_id == 1).update(
        {athlete.pmc_switch_settings: json.dumps(pmc_switch_settings)})
    app.session.commit()
    app.session.remove()

    pmc_figure, hoverData = create_fitness_chart(ride_status=ride_status, run_status=run_status,
                                                 all_status=all_status, power_status=power_status, hr_status=hr_status,
                                                 atl_status=atl_status)

    return pmc_figure, hoverData


# Zone and distribution callback for sport/date fitlers. Also update date label/card header with callback here
@app.callback(
    [Output('trend-chart', 'figure'),
     Output('trend-controls', 'children'), ],
    [Input('average-watts-trend-button', 'n_clicks_timestamp'),
     Input('average-heartrate-trend-button', 'n_clicks_timestamp'),
     Input('tss-trend-button', 'n_clicks_timestamp'),
     Input('distance-trend-button', 'n_clicks_timestamp'),
     Input('elapsed-time-trend-button', 'n_clicks_timestamp'),
     Input('average-speed-trend-button', 'n_clicks_timestamp'),
     Input('average-ground-time-trend-button', 'n_clicks_timestamp'),
     Input('average-oscillation-trend-button', 'n_clicks_timestamp'),
     Input('average-leg-spring-trend-button', 'n_clicks_timestamp'),
     Input('performance-activity-type-toggle', 'value'),
     Input('performance-time-selector-all', 'n_clicks_timestamp'),
     Input('performance-time-selector-ytd', 'n_clicks_timestamp'),
     Input('performance-time-selector-l90d', 'n_clicks_timestamp'),
     Input('performance-time-selector-l6w', 'n_clicks_timestamp'),
     Input('performance-time-selector-l30d', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-all', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-high', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-mod', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-low', 'n_clicks_timestamp')
     ],
    [State('average-watts-trend-button', 'n_clicks_timestamp'),
     State('average-heartrate-trend-button', 'n_clicks_timestamp'),
     State('tss-trend-button', 'n_clicks_timestamp'),
     State('distance-trend-button', 'n_clicks_timestamp'),
     State('elapsed-time-trend-button', 'n_clicks_timestamp'),
     State('average-speed-trend-button', 'n_clicks_timestamp'),
     State('average-ground-time-trend-button', 'n_clicks_timestamp'),
     State('average-oscillation-trend-button', 'n_clicks_timestamp'),
     State('average-leg-spring-trend-button', 'n_clicks_timestamp'),
     State('performance-activity-type-toggle', 'value'),
     State('performance-time-selector-all', 'n_clicks_timestamp'),
     State('performance-time-selector-ytd', 'n_clicks_timestamp'),
     State('performance-time-selector-l90d', 'n_clicks_timestamp'),
     State('performance-time-selector-l6w', 'n_clicks_timestamp'),
     State('performance-time-selector-l30d', 'n_clicks_timestamp'),
     State('performance-intensity-selector-all', 'n_clicks_timestamp'),
     State('performance-intensity-selector-high', 'n_clicks_timestamp'),
     State('performance-intensity-selector-mod', 'n_clicks_timestamp'),
     State('performance-intensity-selector-low', 'n_clicks_timestamp')
     ]
)
def update_trend_chart(*args):
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_run_power = True if athlete_info.use_run_power else False
    use_cycle_power = True if athlete_info.use_cycle_power else False
    use_power = True if use_run_power or use_cycle_power else False
    app.session.remove()
    ctx = dash.callback_context
    sport = 'run' if ctx.states['performance-activity-type-toggle.value'] == False else 'ride'

    # Since the sport/date toggle can be the last trigger, we need to look at timestamp of date buttons and value of sport toggle to determine which date/sport to be using

    states = ctx.states
    # Create dict of just date buttons
    date_buttons = states.copy()
    [date_buttons.pop(x) for x in list(date_buttons.keys()) if 'performance-time-selector' not in x]
    date_days = {'all': 99999, 'ytd': int(datetime.now().strftime('%j')), 'l90d': 90, 'l6w': 42, 'l30d': 30}
    days = date_days[max(date_buttons.items(), key=operator.itemgetter(1))[0].split('.')[0].replace(
        'performance-time-selector-', '')]

    # Create dict of just intensity buttons
    state_buttons = states.copy()
    [state_buttons.pop(x) for x in list(state_buttons.keys()) if 'performance-intensity-selector' not in x]
    last_intensity_click = max(state_buttons.items(), key=operator.itemgetter(1))[0].split('.')[0].replace(
        'performance-intensity-selector-', '')

    if ctx.triggered:
        # Pop date buttons from main dict
        [ctx.states.pop(x) for x in list(ctx.states.keys()) if
         'performance-time-selector' in x or 'performance-intensity-selector' in x]
        # Remove sport toggle from dict, then get max of all timestamps
        ctx.states.pop('performance-activity-type-toggle.value')
        metric = max(ctx.states.items(), key=operator.itemgetter(1))[0].split(".")[0].replace('-trend-button',
                                                                                              '').replace('-', '_')
    else:
        metric = 'average_heartrate' if not use_power else 'average_watts'

    figure = get_trend_chart(metric=metric, sport=sport, days=days, intensity=last_intensity_click)
    return figure, get_trend_controls(sport=sport, selected=metric)


@app.callback(
    [Output('performance-time-selector', 'label'),
     Output('performance-intensity-selector', 'label'),
     Output('performance-title', 'children'),
     Output('performance-trend-running-icon', 'style'),
     Output('performance-trend-bicycle-icon', 'style'),
     Output('performance-trend-zones', 'children'),
     Output('workout-type-distributions', 'data'),
     Output('performance-power-curve', 'figure'),
     Output('performance-power-curve-container', 'style')],
    [Input('performance-activity-type-toggle', 'value'),
     Input('performance-time-selector-all', 'n_clicks_timestamp'),
     Input('performance-time-selector-ytd', 'n_clicks_timestamp'),
     Input('performance-time-selector-l90d', 'n_clicks_timestamp'),
     Input('performance-time-selector-l6w', 'n_clicks_timestamp'),
     Input('performance-time-selector-l30d', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-all', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-high', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-mod', 'n_clicks_timestamp'),
     Input('performance-intensity-selector-low', 'n_clicks_timestamp')]
)
def update_icon(*args):
    athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
    use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False
    app.session.remove()

    inputs = dash.callback_context.inputs
    sport = 'run' if not inputs['performance-activity-type-toggle.value'] else 'ride'
    if sport == 'run':
        run_style = {'fontSize': '1.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}
        ride_style = {'fontSize': '1.5rem', 'display': 'inline-block', 'vertical-align': 'middle'}
    else:
        run_style = {'fontSize': '1.5rem', 'display': 'inline-block', 'vertical-align': 'middle'}
        ride_style = {'fontSize': '1.5rem', 'display': 'inline-block', 'vertical-align': 'middle', 'color': teal}

    # Create dict of just date buttons
    time_inputs = inputs.copy()
    [time_inputs.pop(x) for x in list(time_inputs.keys()) if 'performance-time-selector' not in x]
    date_days = {'all': 99999, 'ytd': int(datetime.now().strftime('%j')), 'l90d': 90, 'l6w': 42, 'l30d': 30}
    last_time_click = max(time_inputs.items(), key=operator.itemgetter(1))[0].split('.')[0].replace(
        'performance-time-selector-', '')
    days = date_days[last_time_click]
    time_label = last_time_click.upper()

    # Create dict of just intensity buttons
    intensity_inputs = inputs.copy()
    [intensity_inputs.pop(x) for x in list(intensity_inputs.keys()) if 'performance-intensity-selector' not in x]
    last_intensity_click = max(intensity_inputs.items(), key=operator.itemgetter(1))[0].split('.')[0].replace(
        'performance-intensity-selector-', '')
    intensity_label = last_intensity_click.title() + ' Intensity'

    return time_label, intensity_label, html.H6(time_label + ' Performance', className='mb-0'), run_style, ride_style, \
           zone_chart(days=days, sport=sport, height=200, intensity=last_intensity_click), workout_distribution(
        sport=sport, days=days, intensity=last_intensity_click), power_curve(
        activity_type=sport, height=200, time_comparison=days, intensity=last_intensity_click) if use_power else {}, {
               'display': 'normal'} if use_power else {'display': 'none'}


# Trend chart callback for sport/date fitlers


# Create YOY Chart
@app.callback(
    [Output('growth-chart', 'figure'),
     Output('growth-chart', 'hoverData'),
     Output('growth-chart-metric-select', 'label')],
    [Input('run|distance', 'n_clicks'),
     Input('run|elapsed_time', 'n_clicks'),
     Input('run|hrss', 'n_clicks'),
     Input('run|trimp', 'n_clicks'),
     Input('run|tss', 'n_clicks'),
     Input('ride|distance', 'n_clicks'),
     Input('ride|elapsed_time', 'n_clicks'),
     Input('ride|hrss', 'n_clicks'),
     Input('ride|trimp', 'n_clicks'),
     Input('ride|tss', 'n_clicks')]
)
def update_yoy_chart(*args):
    ctx = dash.callback_context
    if not ctx.triggered:
        sport = "run"
        metric = 'distance'
    else:
        select = ctx.triggered[0]["prop_id"].split(".")[0].split('|')
        sport = select[0]
        metric = select[1]

    label = (sport + ' ' + metric.replace('elapsed_time', 'duration')).title().replace('_', ' ').replace('Cycling',
                                                                                                         'Ride')
    figure, hoverData = create_yoy_chart(sport=sport, metric=metric)
    return figure, hoverData, label


# Growth Chart KPIs
@app.callback(
    Output('growth-header', 'children'),
    [Input('growth-chart', 'hoverData')])
def update_growth_kpis(hoverData):
    cy, cy_metric, ly, ly_metric, cy_date, metric = None, None, None, None, None, None
    if hoverData is not None:
        for point in hoverData['points']:
            if 'cy' in point['customdata']:
                metric = point['customdata'].split('|')[1]
                cy = point['customdata'].split('|')[2]
                cy_metric = point['y']
                cy_date = point['x']
            elif 'ly' in point['customdata']:
                metric = point['customdata'].split('|')[1]
                ly = point['customdata'].split('|')[2]
                ly_metric = point['y']

        return create_growth_kpis(date=hoverData['points'][0]['x'], cy=cy, cy_metric=cy_metric, ly=ly,
                                  ly_metric=ly_metric, metric=metric)


@app.callback(
    Output('activity-table', 'data'),
    [Input('pm-chart', 'clickData')]
)
def update_fitness_table(clickData):
    if clickData:
        if len(clickData['points']) >= 3:
            date = clickData['points'][0]['x']
            return create_activity_table(date)
    else:
        return create_activity_table()


# Activity Modal Toggle - store activity id clicked from table into div for other callbacks to use for generating charts in modal
@app.callback(
    [Output("activity-modal", "is_open"),
     Output("activity-modal-header", "children"),
     Output("modal-activity-id-type-metric", 'children')],
    [Input('activity-table', 'active_cell'),
     Input("close-activity-modal-button", "n_clicks")],
    [State('activity-table', 'data'),
     State("activity-modal", "is_open")]
)
def toggle_activity_modal(active_cell, n2, data, is_open):
    if active_cell or n2:
        try:
            activity_id = data[active_cell['row_id']]['activity_id']
        except:
            activity_id = None
        if activity_id:
            # if open, populate charts
            if not is_open:

                activity = app.session.query(stravaSummary).filter(stravaSummary.activity_id == activity_id).first()

                app.session.remove()
                # return activity_id
                return not is_open, html.H5(
                    '{} - {}'.format(datetime.strftime(activity.start_day_local, '%A %b %d, %Y'),
                                     activity.name)), '{}|{}|{}'.format(activity_id,
                                                                        'ride' if 'ride' in activity.type else 'run' if 'run' in activity.type else activity.type,
                                                                        'power_zone' if activity.max_watts and activity.ftp else 'hr_zone')
            else:
                return not is_open, None, None
    return is_open, None, None


# Activity modal power curve callback
@app.callback(
    [Output("modal-power-curve-chart", "figure"),
     Output("modal-power-curve-card", "style")],
    [Input("modal-activity-id-type-metric", "children")],
    [State("activity-modal", "is_open")]
)
def modal_power_curve(activity, is_open):
    if activity and is_open:
        activity_id = activity.split('|')[0]
        activity_type = activity.split('|')[1]
        metric = activity.split('|')[2]
        # Only show power zone chart if power data exists
        if metric == 'power_zone':
            figure = power_curve(last_id=activity_id, activity_type=activity_type)
            return figure, {'height': '100%'}
        else:
            return {}, {'display': 'None'}
    else:
        return {}, {'display': 'None'}


# Activity modal power zone callback
@app.callback(
    [Output("modal-zones", "children"),
     Output("modal-zone-title", "children")],
    [Input("modal-activity-id-type-metric", "children")],
    [State("activity-modal", "is_open")]
)
def modal_power_zone(activity, is_open):
    if activity and is_open:
        activity_id = activity.split('|')[0]
        return zone_chart(activity_id=activity_id, chart_id='modal-zone-chart'), html.H4('Training Zones')
    else:
        return None, None


# Activity modal workout details callback
@app.callback(
    [Output("modal-workout-summary", "children"),
     Output("modal-workout-trends", "children"),
     Output("modal-workout-stats", "children")],
    [Input("modal-activity-id-type-metric", "children")],
    [State("activity-modal", "is_open")]
)
def modal_workout_trends(activity, is_open):
    if activity and is_open:
        activity_id = activity.split('|')[0]

        df_samples = pd.read_sql(
            sql=app.session.query(stravaSamples).filter(stravaSamples.activity_id == activity_id).statement,
            con=engine,
            index_col=['timestamp_local'])

        app.session.remove()
        return workout_summary_kpi(df_samples), workout_details(df_samples), calculate_splits(df_samples)
    else:
        return None, None, None


# # Annotation Modal Toggle
@app.callback(
    Output("annotation-modal", "is_open"),
    [Input('open-annotation-modal-button', 'n_clicks')],
    [State("annotation-modal", "is_open")],
)
def toggle_annotation_modal(n1, is_open):
    if n1:
        return not is_open
    return is_open


# Annotation Load table Toggle
@app.callback(
    Output("annotation-table-container", "children"),
    [Input("annotation-modal", "is_open")],
)
def annotation_table(is_open):
    if is_open:
        return create_annotation_table()


# Annotation Table Add Row
@app.callback(
    Output('annotation-table', 'data'),
    [Input('annotation-add-rows-button', 'n_clicks')],
    [State('annotation-table', 'data'),
     State('annotation-table', 'columns')])
def add_row(n_clicks, rows, columns):
    if n_clicks > 0:
        rows.append({c['id']: '' for c in columns})
    return rows


# Annotation Save & Close table Toggle
@app.callback(
    Output("annotation-save-status", "children"),
    [Input("save-close-annotation-modal-button", "n_clicks")],
    [State("annotation-password", "value"),
     State('annotation-table', 'data')]
)
def annotation_table_save(n_clicks, password, data):
    if n_clicks > 0 and password == config.get('settings', 'password'):

        try:
            df = pd.DataFrame(data).set_index('date')
            df['athlete_id'] = 1
            # Truncate annotations for current athlete
            app.session.execute(delete(annotations).where(annotations.athlete_id == 1))
            app.session.commit()
            # Add annotations
            df.to_sql('annotations', engine, if_exists='append', index=True)
        except BaseException as e:
            app.server.logger.error('Error with annotations DB transactions'.format(e))
            app.session.rollback()

        app.session.remove()

        return html.I(className='fa fa-check',
                      style={'display': 'inline-block', 'color': 'green', 'paddingLeft': '1vw',
                             'fontSize': '150%'})
    elif n_clicks > 0 and password != config.get('settings', 'password'):
        return html.I(className='fa fa-times',
                      style={'display': 'inline-block', 'color': 'red', 'paddingLeft': '1vw', 'fontSize': '150%'})

# Cycling
# Low: PZ Endurance and Yoga / Weights
# Med: PZ
# High: PZ Max

# Running
# Low: HR Endurance / Fun Run and Yoga / Weights
# Med: HR Power / Long Run
# High: Speed (Tempo) / Intervals
