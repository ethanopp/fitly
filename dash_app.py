import dash
import logging
from logging.handlers import RotatingFileHandler
import configparser
import flask

config = configparser.ConfigParser()
config.read('./config.ini')

app = flask.Flask(__name__)
dash_app = dash.Dash(__name__, server=app, url_base_pathname='/',
                     meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
                     external_stylesheets=['https://use.fontawesome.com/releases/v5.7.2/css/all.css']
                     )

dash_app.title = 'Fit.ly'

dash_app.config.suppress_callback_exceptions = True
# Dash CSS
# app.css.append_css({"external_url": "https://codepen.io/chriddyp/pen/bWLwgP.css"})

# Can also use %(pathname)s for full pathname for file instead of %(module)s
handler = RotatingFileHandler('./log.log', maxBytes=10000000, backupCount=5)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s from %(module)s line %(lineno)d - %(message)s")
handler.setFormatter(formatter)
dash_app.server.logger.setLevel(config.get('logger', 'level'))
dash_app.server.logger.addHandler(handler)
# Suppress WSGI info logs
logging.getLogger('werkzeug').setLevel(logging.ERROR)