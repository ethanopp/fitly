from . import create_flask, create_dash
from .layouts import main_layout_header, main_layout_sidebar

# The Flask instance
server = create_flask()

# The Dash instance
app = create_dash(server)


# Logging
import logging
from logging.handlers import RotatingFileHandler
import configparser
config = configparser.ConfigParser()
config.read('./config.ini')

# Can also use %(pathname)s for full pathname for file instead of %(module)s
handler = RotatingFileHandler('./log.log', maxBytes=10000000, backupCount=5)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s from %(module)s line %(lineno)d - %(message)s")
handler.setFormatter(formatter)
app.server.logger.setLevel(config.get('logger', 'level'))
app.server.logger.addHandler(handler)
# Suppress WSGI info logs
logging.getLogger('werkzeug').setLevel(logging.ERROR)


# Push an application context so we can use Flask's 'current_app'
with server.app_context():
    # load the rest of our Dash app
    from . import index

    # configure the Dash instance's layout
    app.layout = main_layout_header()
