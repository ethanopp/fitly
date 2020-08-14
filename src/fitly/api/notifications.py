from ..api.sqlalchemy_declarative import withings, stravaSummary, athlete
from sqlalchemy import func
from datetime import datetime, timedelta
import dash_bootstrap_components as dbc
from ..app import app


def last_body_measurement_notification():
    last_measurement_date = app.session.query(func.max(withings.date_utc))[0][0]

    app.session.remove()

    if last_measurement_date:
        days_since_last_measurement = datetime.utcnow().date() - last_measurement_date.date()

        if days_since_last_measurement >= timedelta(days=7):
            return dbc.Alert(
                "It's been {:.0f} days since your last body measurement".format(days_since_last_measurement.days),
                color='primary',
                style={'borderRadius': '4px'})


def last_ftp_test_notification(ftp_type):
    last_ftp_test_date = \
        app.session.query(func.max(stravaSummary.start_date_utc)).filter(
            (stravaSummary.name.ilike('%ftp test%')) & (stravaSummary.type.ilike(ftp_type))
        )[0][0]
    ftp_week_threshold = app.session.query(athlete).filter(
        athlete.athlete_id == 1).first().ftp_test_notification_week_threshold

    app.session.remove()

    if last_ftp_test_date:
        weeks_since_ftp_test = ((datetime.utcnow() - last_ftp_test_date).days) / 7.0
        if weeks_since_ftp_test >= ftp_week_threshold:
            return dbc.Alert(
                "It's been {:.1f} weeks since your last {} FTP test".format(weeks_since_ftp_test, ftp_type),
                color='primary',
                style={'borderRadius': '4px'})
