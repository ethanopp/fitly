from . import create_flask, create_dash, db_startup
from .layouts import main_layout_header, main_layout_sidebar
from apscheduler.schedulers.background import BackgroundScheduler
from .utils import spotify_credentials_supplied

# The Flask instance
server = create_flask()

# The Dash instance
app = create_dash(server)

# New DB startup tasks
db_startup(app)

# Logging
import logging
from logging.handlers import RotatingFileHandler
from .utils import config
from .api.sqlalchemy_declarative import dbRefreshStatus

# Can also use %(pathname)s for full pathname for file instead of %(module)s
handler = RotatingFileHandler('./config/log.log', maxBytes=10000000, backupCount=5)
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

    # Enable refresh cron
    if config.get('cron', 'hourly_pull').lower() == 'true':
        try:
            from .api.datapull import refresh_database

            scheduler = BackgroundScheduler()
            scheduler.add_job(func=refresh_database, trigger="cron", hour='*')

            # Add spotify job on 20 min schedule since API only allows grabbing the last 50 songs
            if spotify_credentials_supplied:
                from .api.spotifyAPI import stream, get_spotify_client, spotify_connected

                if spotify_connected():
                    app.server.logger.debug("Listening to Spotify stream...")
                    # Use this job to pull 'last 50' songs from spotify every 20 mins
                    # scheduler.add_job(func=save_spotify_play_history, trigger="cron", minute='*/20')

                    # Use this job for polling every second (much more precise data with this method can detect skips, etc.)
                    scheduler.add_job(stream, "interval", seconds=float(config.get('spotify', 'poll_interval_seconds')),
                                      max_instances=2)
                else:
                    app.server.logger.debug('Spotify not connected. Not listening to stream.')
            app.server.logger.info('Starting cron jobs')
            scheduler.start()
        except BaseException as e:
            app.server.logger.error(f'Error starting cron jobs: {e}')

    # Delete any audit logs for running processes, since restarting server would stop any processes
    app.session.query(dbRefreshStatus).filter(dbRefreshStatus.refresh_method == 'processing').delete()
    app.session.commit()
    app.session.remove()
    # configure the Dash instance's layout
    app.layout = main_layout_header()
    # app.layout = main_layout_sidebar()
