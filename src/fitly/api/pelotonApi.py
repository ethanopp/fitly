#! /usr/bin/env python3.6
# -*- coding: latin-1 -*-

import requests
import decimal

from datetime import datetime, timezone, date, timedelta
from ..utils import config
import pandas as pd
from .sqlalchemy_declarative import workoutStepLog, athlete, stravaSummary
from ..app import app
import json
import os

# Pulled from
# https://github.com/geudrik/peloton-api

# Set our base URL location
_BASE_URL = 'https://api.onepeloton.com'

# Mandatory credentials
PELOTON_USERNAME = config.get('peloton', 'username')
PELOTON_PASSWORD = config.get('peloton', 'password')

_USER_AGENT = "Mozilla/5.0"


# Whether or not to verify SSL connections (defaults to True)
# try:
#     SSL_VERIFY = parser.getboolean("peloton", "ssl_verify")
# except:
#     SSL_VERIFY = True
#
# # If set, we'll use this cert to verify against. Useful when you're stuck behind SSL MITM
# try:
#     SSL_CERT = parser.get("peloton", "ssl_cert")
# except:
#     SSL_CERT = None


class NotLoaded:
    """ In an effort to avoid pissing Peloton off, we lazy load as often as possible. This class
    is utitilzed frequently within this module to indicate when data can be retrieved, as requested"""
    pass


class DataMissing:
    """ Used to indicate that data is missing (eg: no h/r monitor used)
    """
    pass


class PelotonException(Exception):
    """ This is our base exception class, that all other exceptions inherit from
    """
    pass


class PelotonClientError(PelotonException):
    """ Client exception class
    """

    def __init__(self, message, response):
        super(PelotonException, self).__init__(self, message)
        self.message = message
        self.response = response


class PelotonServerError(PelotonException):
    """ Server exception class
    """

    def __init__(self, message, response):
        super(PelotonException, self).__init__(self, message)
        self.message = message
        self.response = response


class PelotonRedirectError(PelotonException):
    """ Maybe we'll see weird unexpected redirects?
    """

    def __init__(self, message, response):
        super(PelotonException, self).__init__(self, message)
        self.message = message
        self.response = response


class PelotonObject:
    """ Base class for all Peloton data
    """

    def serialize(self, depth=1, load_all=True):
        """Ensures that everything has a .serialize() method so that all data is serializable

        Args:
            depth: level of nesting to include when serializing
            load_all: whether or not to include lazy loaded data (eg: NotLoaded() instances)
        """

        # Dict to hold our returnable data
        ret = {}

        # Dict to hold the attributes of $.this object
        obj_attrs = {}

        # If we hit our depth limit, return
        if depth == 0:
            return None

        # List of keys that we will not be included in our serailizable output based on load_all
        dont_load = []

        # Load our NotLoaded() (lazy loading) instances if we're requesting to do so
        for k in self.__dict__:
            if load_all:
                obj_attrs[k] = getattr(self, k)
                continue

            # Don't include lazy loaded attrs
            raw_value = super(PelotonObject, self).__getattribute__(k)
            if isinstance(raw_value, NotLoaded):
                dont_load.append(k)

        # We've gone through our pre-flight prep, now lets actually serailize our data
        for k, v in obj_attrs.items():

            # Ignore this key if it's in our dont_load list or is private
            if k.startswith('_') or k in dont_load:
                continue

            if isinstance(v, PelotonObject):
                if depth > 1:
                    ret[k] = v.serialize(depth=depth - 1)

            elif isinstance(v, list):
                serialized_list = []

                for val in v:
                    if isinstance(val, PelotonObject):
                        if depth > 1:
                            serialized_list.append(val.serialize(depth=depth - 1))

                    elif isinstance(val, (datetime, date)):
                        serialized_list.append(val.isoformat())

                    elif isinstance(val, decimal.Decimal):
                        serialized_list.append("%.1f" % val)

                    elif isinstance(val, (str, int, dict)):
                        serialized_list.append(val)

                # Only add if we have data (this _can_ be an empty list in the event that our list is noting but
                #   PelotonObject's and we're at/past our recursion depth)
                if serialized_list:
                    ret[k] = serialized_list

                # If v is empty, return an empty list
                elif not v:
                    ret[k] = []

            else:
                if isinstance(v, (datetime, date)):
                    ret[k] = v.isoformat()

                elif isinstance(v, decimal.Decimal):
                    ret[k] = "%.1f" % v

                else:
                    ret[k] = v

        # We've got a python dict now, so lets return it
        return ret


class PelotonAPI:
    """ Base class that factory classes within this module inherit from.
    This class is _not_ meant to be utilized directly, so don't do it.

    Core "working" class of the Peolton API Module
    """

    peloton_username = None
    peloton_password = None

    # Hold a request.Session instance that we're going to rely on to make API calls
    peloton_session = None

    # Being friendly (by default), use the same page size that the Peloton website uses
    page_size = 10

    # Hold our user ID (pulled when we authenticate to the API)
    user_id = None

    # Headers we'll be using for each request
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT
    }

    @classmethod
    def _api_request(cls, uri, params={}, call='get'):
        """ Base function that everything will use under the hood to interact with the API

        Returns a requests response instance, or raises an exception on error
        """

        # Create a session if we don't have one yet
        if cls.peloton_session is None:
            cls._create_api_session()

        # app.server.logger.debug("Request {} [{}]".format(_BASE_URL + uri, params))
        if call == 'get':
            resp = cls.peloton_session.get(_BASE_URL + uri, headers=cls.headers, params=params)
        elif call == 'post':
            resp = cls.peloton_session.post(_BASE_URL + uri, headers=cls.headers, json=params)

        # app.server.logger.debug("Response {}: [{}]".format(resp.status_code, resp._content))

        # If we don't have a 200 code
        if not (200 >= resp.status_code < 300):

            message = resp._content

            if 300 <= resp.status_code < 400:
                raise PelotonRedirectError("Unexpected Redirect", resp)

            elif 400 <= resp.status_code < 500:
                raise PelotonClientError(message, resp)

            elif 500 <= resp.status_code < 600:
                raise PelotonServerError(message, resp)

        return resp

    @classmethod
    def _create_api_session(cls):
        """ Create a session instance for communicating with the API
        """

        if cls.peloton_username is None:
            cls.peloton_username = PELOTON_USERNAME

        if cls.peloton_password is None:
            cls.peloton_password = PELOTON_PASSWORD

        if cls.peloton_username is None or cls.peloton_password is None:
            raise PelotonClientError("The Peloton Client Library requires a `username` and `password` be set in "
                                     "`/.config/config.ini, under section `peloton`")

        payload = {
            'username_or_email': cls.peloton_username,
            'password': cls.peloton_password
        }

        cls.peloton_session = requests.Session()
        resp = cls.peloton_session.post(_BASE_URL + '/auth/login', json=payload, headers=cls.headers)
        message = resp._content

        if 300 <= resp.status_code < 400:
            raise PelotonRedirectError("Unexpected Redirect", resp)

        elif 400 <= resp.status_code < 500:
            raise PelotonClientError(message, resp)

        elif 500 <= resp.status_code < 600:
            raise PelotonServerError(message, resp)

        # Set our User ID on our class
        cls.user_id = resp.json()['user_id']


class PelotonUser(PelotonObject):
    """ Read-Only class that describes a Peloton User

    This class should never be invoked directly

    """

    def __init__(self, **kwargs):
        self.username = kwargs.get('username')
        self.id = kwargs.get('id')

    def __str__(self):
        return self.username


class PelotonWorkout(PelotonObject):
    """ A read-only class that defines a workout instance/object

    This class should never be instantiated directly!
    """

    def __init__(self, **kwargs):
        """ This class is instantiated by
        PelotonWorkout.get()
        PelotonWorkout.list()
        """

        self.id = kwargs.get('id')

        # This is a bit weird, we can only get ride details if they come up from a users workout list via a join
        self.ride = NotLoaded()
        if kwargs.get('ride') is not None:
            self.ride = PelotonRide(**kwargs.get('ride'))

        # Not entirely certain what the difference is between these two fields
        self.created = datetime.fromtimestamp(kwargs.get('created', 0), timezone.utc)
        self.created_at = datetime.fromtimestamp(kwargs.get('created_at', 0), timezone.utc)

        # Time duration of this ride
        self.start_time = datetime.fromtimestamp(kwargs.get('start_time', 0), timezone.utc)
        self.end_time = datetime.fromtimestamp(kwargs.get('end_time', 0), timezone.utc)

        # What exercise type is this?
        self.fitness_discipline = kwargs.get('fitness_discipline')

        # Workout status (complete, in progress, etc)
        self.status = kwargs.get('status')

        # Load up our metrics (since we're joining for them anyway)
        self.metrics_type = kwargs.get('metrics_type')
        self.metrics = kwargs.get('metrics', NotLoaded())

        # Leaderboard stats need to call PelotonWorkoutFactory to get these two bits
        self.leaderboard_rank = kwargs.get('leaderboard_rank', NotLoaded())
        self.leaderboard_users = kwargs.get('total_leaderboard_users', NotLoaded())
        self.personal_record = kwargs.get('is_total_work_personal_record', NotLoaded())

        # List of achievements that were obtained during this workout
        achievements = kwargs.get('achievement_templates', NotLoaded())
        if not isinstance(achievements, NotLoaded):
            self.achievements = []
            for achievement in achievements:
                self.achievements.append(PelotonWorkoutAchievement(**achievement))

    def __str__(self):
        return self.fitness_discipline

    def __getattribute__(self, attr):

        value = object.__getattribute__(self, attr)

        # Handle accessing NotLoaded attributes (yay lazy loading)
        if attr in ['leaderboard_rank', 'leaderboard_users', 'achievements', 'metrics'] and type(value) is NotLoaded:

            if attr.startswith('leaderboard_') or attr == 'achievements': \
                    # Yes, this gets a fuckload of duplicate date, but the endpoints don't return consistent info!
                workout = PelotonWorkoutFactory.get(self.id)

                # Load leaderboard stats
                self.leaderboard_rank = workout.leaderboard_rank
                self.leaderboard_users = workout.leaderboard_users
                self.personal_record = workout.personal_record

                # Load our achievements
                self.achievements = workout.achievements

                # Return the value of the requested attribute
                return getattr(self, attr)

            # Metrics gets a dedicated conditional because it's a different endpoint
            elif attr == "metrics":
                metrics = PelotonWorkoutMetricsFactory.get(self.id)
                self.metrics = metrics
                return metrics

        return value

    @classmethod
    def get(cls, workout_id):
        """ Get a specific workout
        """
        return PelotonWorkoutFactory.get(workout_id)

    @classmethod
    def list(cls):
        """ Return a list of all workouts
        """
        return PelotonWorkoutFactory.list()

    @classmethod
    def latest(cls):
        """ Returns the lastest workout object
        """
        return PelotonWorkoutFactory.latest()


class PelotonRide(PelotonObject):
    """ A read-only class that defines a ride (workout class)

    This class should never be invoked directly!
    """

    def __init__(self, **kwargs):
        self.title = kwargs.get('title')
        self.id = kwargs.get('id')
        self.description = kwargs.get('description')
        self.duration = kwargs.get('duration')

        # When we make this Ride call from the workout factory, there is no instructor data
        if kwargs.get('instructor') is not None:
            self.instructor = PelotonInstructor(**kwargs.get('instructor'))

    def __str__(self):
        return self.title

    @classmethod
    def get(cls, ride_id):
        raise NotImplementedError()


class PelotonMetric(PelotonObject):
    """ A read-only class that outlines some simple metric information about the workout
    """

    def __init__(self, **kwargs):
        self.values = kwargs.get('values')
        self.average = kwargs.get('average_value')
        self.name = kwargs.get('display_name')
        self.unit = kwargs.get('display_unit')
        self.max = kwargs.get('max_value')
        self.slug = kwargs.get('slug')

    def __str__(self):
        return "{} ({})".format(self.name, self.unit)


class PelotonMetricSummary(PelotonObject):
    """ An object that describes a summary of a metric set
    """

    def __init__(self, **kwargs):
        self.name = kwargs.get('display_name')
        self.value = kwargs.get('value')
        self.unit = kwargs.get('display_unit')
        self.slug = kwargs.get('slug')

    def __str__(self):
        return "{} ({})".format(self.name, self.unit)


class PelotonWorkoutMetrics(PelotonObject):
    """ An object that describes all of the metrics of a given workout
    """

    def __init__(self, **kwargs):
        """ Take a metrics set and objectify it
        """

        self.workout_duration = kwargs.get('duration')
        self.fitness_discipline = kwargs.get('segment_list')[0]['metrics_type']

        # Build summary attributes
        metric_summaries = ['total_output', 'distance', 'calories']
        for metric in kwargs.get('summaries'):
            if metric['slug'] not in metric_summaries:
                # app.server.logger.warning("Unknown metric summary {} found".format(metric['slug']))
                continue

            attr_name = metric['slug'] + '_summary'
            if metric['slug'] == "total_output":
                attr_name = "output_summary"

            setattr(self, attr_name, PelotonMetricSummary(**metric))

        # Build metric details
        metric_categories = ['output', 'cadence', 'resistance', 'speed', 'heart_rate']
        for metric in kwargs.get('metrics'):

            if metric['slug'] not in metric_categories:
                # app.server.logger.warning("Unknown metric category {} found".format(metric['slug']))
                continue

            setattr(self, metric['slug'], PelotonMetric(**metric))

    def __str__(self):
        return self.fitness_discipline


class PelotonInstructor(PelotonObject):
    """ A read-only class that outlines instructor details

    This class should never be invoked directly"""

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.first_name = kwargs.get('first_name')
        self.last_name = kwargs.get('last_name')
        self.music_bio = kwargs.get('music_bio')
        self.spotify_playlist_uri = kwargs.get('spotify_playlist_uri')
        self.bio = kwargs.get('bio')
        self.quote = kwargs.get('quote')
        self.background = kwargs.get('background')
        self.short_bio = kwargs.get('short_bio')

    def __str__(self):
        return self.name


class PelotonWorkoutSegment(PelotonObject):
    """ A read-only class that outlines instructor details

        This class should never be invoked directly"""

    def __init__(self):
        raise NotImplementedError()


class PelotonWorkoutAchievement(PelotonObject):
    """ Class that represents a single achievement that a user earned during the workout
    """

    def __init__(self, **kwargs):
        self.slug = kwargs.get('slug')
        self.description = kwargs.get('description')
        self.image_url = kwargs.get('image_url')
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')


class PelotonWorkoutFactory(PelotonAPI):
    """ Class that handles fetching data and instantiating objects

    See PelotonWorkout for details
    """

    @classmethod
    def list(cls, results_per_page=10):
        """ Return a list of PelotonWorkout instances that describe each workout
        """

        # We need a user ID to list all workouts. @pelotoncycle, please don't do this :(
        if cls.user_id is None:
            cls._create_api_session()

        uri = '/api/user/{}/workouts'.format(cls.user_id)
        params = {
            'page': 0,
            'limit': results_per_page,
            'joins': 'ride,ride.instructor'
        }

        # Get our first page, which includes number of successive pages
        res = cls._api_request(uri, params).json()

        # Add this pages data to our return list
        ret = [PelotonWorkout(**workout) for workout in res['data']]

        # We've got page 0, so start with page 1
        for i in range(1, res['page_count']):
            params['page'] += 1
            res = cls._api_request(uri, params).json()
            [ret.append(PelotonWorkout(**workout)) for workout in res['data']]

        return ret

    @classmethod
    def get(cls, workout_id):
        """ Get workout details by workout_id
        """

        uri = '/api/workout/{}'.format(workout_id)
        workout = PelotonAPI._api_request(uri).json()
        return PelotonWorkout(**workout)

    @classmethod
    def latest(cls):
        """ Returns an instance of PelotonWorkout that represents the latest workout
        """

        # We need a user ID to list all workouts. @pelotoncycle, please don't do this :(
        if cls.user_id is None:
            cls._create_api_session()

        uri = '/api/user/{}/workouts'.format(cls.user_id)
        params = {
            'page': 0,
            'limit': 1,
            'joins': 'ride,ride.instructor'
        }

        # Get our first page, which includes number of successive pages
        res = cls._api_request(uri, params).json()

        # Return our single workout, without having to get a bunch of extra data from the API
        return PelotonWorkout(**res['data'][0])


class PelotonWorkoutMetricsFactory(PelotonAPI):
    """ Class to handle fetching and transformation of metric data
    """

    @classmethod
    def get(cls, workout_id):
        """ Returns a list of PelotonMetric instances for each metric type
        """

        uri = '/api/workout/{}/performance_graph'.format(workout_id)
        params = {
            'every_n': 1
        }

        res = cls._api_request(uri, params).json()
        return PelotonWorkoutMetrics(**res)


def roundTime(dt=None, roundTo=60):
    """Round a datetime object to any time lapse in seconds
    dt : datetime.datetime object, default now.
    roundTo : Closest number of seconds to round to, default 1 minute.
    Author: Thierry Husson 2012 - Use it as you want but don't blame me.
    """
    seconds = (dt.replace(tzinfo=None) - dt.replace(tzinfo=None, hour=0, minute=0, second=0)).seconds
    rounding = (seconds + roundTo / 2) // roundTo * roundTo
    return (dt + timedelta(0, rounding - seconds, -dt.microsecond)).replace(tzinfo=None)


def peloton_mapping_df():
    workouts = PelotonWorkout.list()
    df = pd.DataFrame()
    for workout in workouts:
        try:
            instructor = ' with {}'.format(workout.ride.instructor)
        except:
            instructor = ''
        # Round activity to nerest minute to then align with strava data rounded to nearest minute
        df = df.append({
            'created_at': roundTime(pd.to_datetime(workout.created_at)),
            'start': roundTime(pd.to_datetime(workout.start_time)),
            'end': roundTime(pd.to_datetime(workout.end_time)),
            'type': workout.fitness_discipline,
            'name': workout.ride.title + instructor
        }, ignore_index=True)
    return df


def get_schedule(fitness_discipline, class_names=['all'], taken_class_ids=[], limit=10, is_favorite_ride=False,
                 genre=None, difficulty=None):
    """ Returns list of on-demand workouts"""
    # Genre and difficulty not currently being automatically used

    music_dict = {'Alternative': '85ca9f28a03e4bdc970447de368b0219',
                  'Electronic': '3ee05f39e1dd477facbb9ac8c27c89c3',
                  'Pop': '6bb65ad0b1f64a639ab91e179f969e7d',
                  'Hip Hop': 'c9d4dee696b04477afc88aa22285025f',
                  'Indie': '531baed4112042ee98ea72f1030c40d0',
                  'Classic Rock': '7afdd1462d474005841e9a6a403229f1',
                  'Country': '5ab996597f564959afcc0c24a90e28e5',
                  'R&B': '3c04c80b103043ebb5c9d23e1ad68c52',
                  'Rock': 'c06217bbe61f485094cfe62d098b3bf8',
                  'Latin': 'a6620457f6fe48439fb746e5b0731f79'}

    uri = '/api/v2/ride/archived'
    params = {
        'browse_category': fitness_discipline.lower(),
        'content_format': 'audio,video',
        'limit': 10,
        'page': 0,
        'sort_by': 'original_air_time',
        'desc': 'true'
    }

    # If more than 1 class name for specified fitness discipline and effort recommendation, use the 'next' class in list
    # from whatever the most previous completed class was
    next_workout, last_workout = None, 0
    if class_names != ['all']:
        # Query workouts for last workout completed in the list of class_names passed
        workouts = app.session.query(stravaSummary.name).all()
        for workout in workouts:
            for class_name in class_names:
                if class_name in workout[0]:
                    last_workout = class_names.index(class_name)
                    break

        # If we are at the final value in list, revert to first value
        if len(class_names) == last_workout + 1:
            next_workout = class_names[0]
        else:
            next_workout = class_names[last_workout + 1]

    if fitness_discipline == 'outdoor':
        params['content_format'] = 'audio'
    # Filtering on already bookmarked rides to delete and make room for new bookmarks, so all other parameters should be ignored
    if is_favorite_ride:
        params['is_favorite_ride'] = 'true'
    else:
        if genre:
            params['super_genre_id'] = music_dict[genre]
        if difficulty:
            params['difficulty'] = difficulty

    # Get our first page, which includes number of successive pages
    res = PelotonAPI._api_request(uri=uri, params=params).json()

    # if there are workouts to parse through...
    if len(res['data']) > 0:
        # If is_favorite_ride was passed, we are getting all bookmarked classes to delete, so ignore limit and loop through all pages
        if is_favorite_ride:
            ret = [workout for workout in res['data']]
            for i in range(1, res['page_count']):
                params['page'] += 1
                res = PelotonAPI._api_request(uri=uri, params=params).json()
                [ret.append(workout) for workout in res['data']]

        else:
            # Add the first page data to our return list, only add classes if not already taken
            ret = [workout for workout in res['data'] if
                   workout['id'] not in taken_class_ids and (
                           workout['title'] == next_workout or class_names == ['all'])]
            taken_classes = []
            # If there are not enough workouts in our list, go to next page
            while len(ret) < limit and params['page'] < res['page_count']:
                # We've got page 0, so add page at beginning of loop
                params['page'] += 1
                res = PelotonAPI._api_request(uri=uri, params=params).json()
                [taken_classes.append(workout) for workout in res['data'] if
                 workout['id'] in taken_class_ids and workout['title'] == next_workout]
                [ret.append(workout) for workout in res['data'] if
                 workout['id'] not in taken_class_ids and (workout['title'] == next_workout or class_names == ['all'])]
            # Only take up to limit when adding new bookmarks
            ret = ret[:limit]
            # If limit is not met, add classes that may have already been taken to hit limit
            while len(ret) < limit and len(taken_classes) > 0:
                ret.append(taken_classes.pop(0))

        workouts = pd.DataFrame(ret)

        return workouts
    else:
        return pd.DataFrame()


def get_peloton_class_names():
    """ Returns dict of class types """

    peloton_class_names_file = os.path.join(os.path.join(os.getcwd(), 'config'), 'peloton_class_dict.json')

    # If file exists, read it's last refresh time
    if os.path.isfile(peloton_class_names_file):
        with open(peloton_class_names_file, 'r') as file:
            peloton_class_dict = json.load(file)
        if pd.to_datetime(peloton_class_dict['last_refresh']).date() > (datetime.today() - timedelta(days=30)).date():
            app.server.logger.debug('Peloton class type json not older than 30 days, skipping refresh')

    else:
        app.server.logger.info('Refreshing peloton class type dict...')
        uri = '/api/v2/ride/archived'
        params = {
            'content_format': 'audio,video',
            'limit': 10,
            'page': 0,
            'sort_by': 'original_air_time',
            'desc': 'true'
        }

        # Get our first page, which includes number of successive pages
        res = PelotonAPI._api_request(uri=uri, params=params).json()

        fitness_disciplines = res['fitness_disciplines']
        fitness_disciplines.append({'id': 'outdoor', 'name': 'Outdoor'})
        peloton_class_dict = {}

        # for x in fitness_disciplines:
        for x in fitness_disciplines:
            fitness_discipline = x['id']
            # api still returning 'circuit' for Tread bootcamp when it should be 'bootcamp' so override value from response
            if fitness_discipline == 'circuit':
                fitness_discipline = 'bootcamp'

            # If fitness_discipline node not already in dict, add it
            if not peloton_class_dict.get(fitness_discipline):
                peloton_class_dict[fitness_discipline] = {}

            # Try to grab series id's from each fitness_discipline and add to sub_dict
            try:
                # Query schedule to get all types of classes within respective fitness discipline
                df = get_schedule(fitness_discipline, limit=500)[['title']]
                df = df.sort_values(by='title')
                df = df.drop_duplicates()

                if len(df) > 0:
                    for index, row in df.iterrows():
                        peloton_class_dict[fitness_discipline][row['title']] = fitness_discipline
            except:
                pass

        with open(peloton_class_names_file, 'w') as file:
            peloton_class_dict['last_refresh'] = str(datetime.today().date())
            file.write(json.dumps(peloton_class_dict))

        app.server.logger.info('Peloton class type dict refresh complete')

    del peloton_class_dict['last_refresh']
    return peloton_class_dict


def add_bookmark(ride_id):
    """ Bookmarks an on-demand class"""
    uri = '/api/favorites/create'
    params = {'ride_id': ride_id}
    PelotonAPI._api_request(uri=uri, params=params, call='post')


def remove_bookmark(ride_id):
    """ Removes a bookmarked class"""
    uri = '/api/favorites/delete'
    params = {'ride_id': ride_id}
    PelotonAPI._api_request(uri=uri, params=params, call='post')


def get_bookmarks():
    uri = '/api/favorites'
    return PelotonAPI._api_request(uri=uri).json()


def set_peloton_workout_recommendations():
    app.server.logger.info('Bookmarking peloton recommendations...')
    # Query worktypes by effort level settings
    athlete_bookmarks = json.loads(app.session.query(athlete.peloton_auto_bookmark_ids).filter(
        athlete.athlete_id == 1).first().peloton_auto_bookmark_ids)
    # Get recommended effort based on workflow
    effort_recommendation = app.session.query(workoutStepLog.workout_step_desc).order_by(
        workoutStepLog.date.desc()).first().workout_step_desc

    app.session.remove()

    fitness_disciplines = athlete_bookmarks.keys()
    taken_class_ids = [x.ride.id for x in PelotonWorkout.list()]

    # Loop through each workout type to delete all current bookmarks
    for fitness_discipline in fitness_disciplines:
        current_bookmarks = get_schedule(fitness_discipline=fitness_discipline, is_favorite_ride=True)
        if len(current_bookmarks) > 0:
            [remove_bookmark(x) for x in current_bookmarks['id']]
        # Be sure to delete outdoor as well since 'outdoor' is not returned by peloton api as a fitness discipline
        if fitness_discipline == 'running':
            current_bookmarks = get_schedule(fitness_discipline='outdoor', is_favorite_ride=True)
            if len(current_bookmarks) > 0:
                [remove_bookmark(x) for x in current_bookmarks['id']]

    # Loop through each workout type to add new bookmarks
    for fitness_discipline in fitness_disciplines:
        class_name_recommendations = athlete_bookmarks.get(fitness_discipline).get(effort_recommendation)
        # If no class types for given HRV step, do not add bookmarks
        if class_name_recommendations:
            class_name_recommendations = json.loads(class_name_recommendations)
            for d in class_name_recommendations:
                # Allow for outdoor workout bookmarks
                fitness_discipline_outdoor_toggle = 'outdoor' if 'outdoor' in d.lower() else fitness_discipline

                new_bookmarks = get_schedule(fitness_discipline=fitness_discipline_outdoor_toggle,
                                             class_names=class_name_recommendations, taken_class_ids=taken_class_ids)
                if len(new_bookmarks) > 0:
                    [add_bookmark(x) for x in new_bookmarks['id']]
