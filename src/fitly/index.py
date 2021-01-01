import dash_html_components as html

from .app import app
from .utils import DashRouter, DashNavBar
from .pages import home, lifting, performance, power, music, settings
from .components import fa
from dash.dependencies import Input, Output, State
from .api.sqlalchemy_declarative import dbRefreshStatus, athlete

athlete_info = app.session.query(athlete).filter(athlete.athlete_id == 1).first()
use_power = True if athlete_info.use_run_power or athlete_info.use_cycle_power else False
app.session.remove()

# Ordered iterable of routes: tuples of (route, layout), where 'route' is a
# string corresponding to path of the route (will be prefixed with Dash's
# 'routes_pathname_prefix' and 'layout' is a Dash Component.
urls = (
    ("", home.get_layout),
    ("home", home.get_layout),
    ("performance", performance.get_layout),
    ("power", power.get_layout),
    ("lifting", lifting.get_layout),
    ("music", music.get_layout),
    ("settings", settings.get_layout),

)

# Ordered iterable of navbar items: tuples of `(route, display)`, where `route`
# is a string corresponding to path of the route (will be prefixed with
# 'routes_pathname_prefix') and 'display' is a valid value for the `children`
# keyword argument for a Dash component (ie a Dash Component or a string).
nav_items = (
    ("home", html.Div([fa("fas fa-home"), "Home"])),
    ("performance", html.Div([fa("fas fa-seedling"), "Performance"])),
    ("power", html.Div([fa("fas fa-bolt"), "Power"])),
    ("lifting", html.Div([fa("fas fa-dumbbell"), "Lifting"])),
    ("music", html.Div([fa("fas fa-music"), "Music"])),
    ("settings", html.Div([fa("fa fa-sliders-h"), "Settings"])),
)

router = DashRouter(app, urls)
navbar = DashNavBar(app, nav_items)


# add callback for toggling the collapse on small screens
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open


@app.callback(
    Output('db-refresh-toast', 'is_open'),
    [Input('db-refresh-toast-interval', 'n_intervals')]
)
def truncate_and_refresh(interval):
    processing = app.session.query(dbRefreshStatus).filter(dbRefreshStatus.refresh_method == 'processing').first()
    app.session.remove()
    if processing:
        return True
    else:
        return False
