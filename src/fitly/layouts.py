"""Contains layouts suitable for being the value of the 'layout' attribute of
Dash app instances.
"""

from flask import current_app as server
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

from .components import make_header, make_sidebar


def main_layout_header():
    """Dash layout with a top-header"""
    return html.Div(
        [
            make_header(),
            dbc.Container(
                dbc.Row(dbc.Col(id=server.config["CONTENT_CONTAINER_ID"])), fluid=True
            ),
            dcc.Location(id=server.config["LOCATION_COMPONENT_ID"], refresh=False),

            dbc.Toast(
                id="db-refresh-toast",
                header="Fit.ly",
                is_open=False,
                dismissable=False,
                icon="danger",
                # top: 66 positions the toast below the navbar
                style={"position": "fixed", "top": 66, "right": 10, "width": 350},
                children=[
                    dbc.Row(className='align-items-center text-center', children=[
                        dbc.Col(className='col-2', children=[dbc.Spinner(size='md', color="danger")]),
                        dbc.Col(className='col-8 text-center', children=['Database Refresh in Progress'])
                    ])
                ],
            ),
            dcc.Interval(id='db-refresh-toast-interval', interval=3 * 1000, n_intervals=0),
        ]
    )


def main_layout_sidebar():
    """Dash layout with a sidebar"""
    return html.Div(
        [
            dbc.Container(
                fluid=True,
                children=dbc.Row(
                    [
                        dbc.Col(
                            make_sidebar(className="px-2"), width=2, className="px-0"
                        ),
                        dbc.Col(id=server.config["CONTENT_CONTAINER_ID"], width=10),
                    ]
                ),
            ),
            dcc.Location(id=server.config["LOCATION_COMPONENT_ID"], refresh=False),
        ]
    )
