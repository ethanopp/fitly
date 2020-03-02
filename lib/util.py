#
# Author: Bailey Belvis (https://github.com/philosowaffle)
#
import json
from .constants import A_OK_HTTP_CODES, A_ERROR_HTTP_CODES
from datetime import timedelta
from dash_app import dash_app
import configparser
import pytz

config = configparser.ConfigParser()
config.read('./config.ini')

local_tz = pytz.timezone(config.get('timezone', 'timezone'))

##############################
# Main
##############################
def parse_response(response):
    """Parse JSON API response, return object."""
    dash_app.server.logger.debug("parse_response - input: {}".format(response.text))
    parsed_response = json.loads(response.text)
    dash_app.server.logger.debug("parse_response - parsed: {}".format(parsed_response))
    return parsed_response


def handle_error(response):
    """Raise appropriate exceptions if necessary."""
    status_code = response.status_code

    if status_code not in A_OK_HTTP_CODES:
        logError(response)
        error_explanation = A_ERROR_HTTP_CODES.get(status_code)
        raise_error = "{}: {}".format(status_code, error_explanation)
        raise Exception(raise_error)
    else:
        return True


def full_url(base, suffix):
    return base + suffix


def getResponse(session, url, payload, cookieDict):
    response = session.get(url, json=payload, cookies=cookieDict)
    parsed_response = parse_response(response)
    handle_error(response)

    return parsed_response


def logError(response):
    request = response.request
    url = request.url
    headers = request.headers
    dash_app.server.logger.debug("handle_error - Url: {}".format(url))
    dash_app.server.logger.debug("handle_error - Headers: {}".format(headers))


def calc_next_saturday(d):
    return d.date() + timedelta((12 - d.weekday()) % 7)


def calc_prev_sunday(d):
    return calc_next_saturday(d) - timedelta(days=6)


def update_config(section, parameter, value):
    config.set(section, parameter, value)
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

def utc_to_local(utc_dt):
    local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)
    return local_tz.normalize(local_dt).replace(tzinfo=None)#.tz_localize(None)  # .normalize might be unnecessary