import dash_html_components as html

from .app import app
from .utils import DashRouter, DashNavBar
from .pages import character_counter, home, lifting, performance, power, settings
from .components import fa


# Ordered iterable of routes: tuples of (route, layout), where 'route' is a
# string corresponding to path of the route (will be prefixed with Dash's
# 'routes_pathname_prefix' and 'layout' is a Dash Component.
urls = (
    ("", character_counter.get_layout),
    ("character-counter", character_counter.get_layout),
    ("home", home.get_layout),
    ("performance", performance.get_layout),
    ("power", power.get_layout),
    ("lifting", lifting.get_layout),
    ("settings", settings.get_layout),

)

# Ordered iterable of navbar items: tuples of `(route, display)`, where `route`
# is a string corresponding to path of the route (will be prefixed with
# 'routes_pathname_prefix') and 'display' is a valid value for the `children`
# keyword argument for a Dash component (ie a Dash Component or a string).
nav_items = (
    ("character-counter", html.Div([fa("fas fa-keyboard"), "Character Counter"])),
    ("home", html.Div([fa("fas fa-heart"), "Home"])),
    ("performance", html.Div([fa("fas fa-seedling"), "Performance"])),
    ("power", html.Div([fa("fas fa-bolt"), "Power"])),
    ("lifting", html.Div([fa("fas fa-dumbbell"), "Lifting"])),
    ("settings", html.Div([fa("fa fa-sliders-h"), "Settings"])),
)

router = DashRouter(app, urls)
navbar = DashNavBar(app, nav_items)
