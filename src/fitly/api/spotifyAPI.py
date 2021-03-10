import tekore as tk
import pandas as pd
import json
from ..utils import config
from ..app import app
from ..api.database import engine
from ..api.sqlalchemy_declarative import apiTokens, spotifyPlayHistory, stravaSummary
from sqlalchemy import delete, func, extract
from datetime import datetime, timedelta
import ast
import time
import math
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import GridSearchCV
from sklearn import metrics
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, classification_report, confusion_matrix,
                             roc_auc_score, roc_curve, matthews_corrcoef)
from sklearn.utils import resample
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
import numpy as np
import random
import threading
import queue
import pickle

client_id = config.get('spotify', 'client_id')
client_secret = config.get('spotify', 'client_secret')
redirect_uri = config.get('spotify', 'redirect_uri')
min_secs_listened = int(config.get('spotify', 'min_secs_listened'))
skip_min_threshold = float(config.get('spotify', 'skip_min_threshold'))
skip_max_threshold = float(config.get('spotify', 'skip_max_threshold'))
poll_interval_seconds = float(config.get('spotify', 'poll_interval_seconds'))

# Main queue that stream will add playback feeds to
q = queue.Queue(maxsize=0)
current_state = None
last_state = None
playback_feed = []


# Retrieve current tokens from db
def current_token_dict():
    try:
        token_dict = app.session.query(apiTokens.tokens).filter(apiTokens.service == 'Spotify').first().tokens
        token_pickle = pickle.loads(token_dict)
        app.session.remove()
    except BaseException as e:
        app.server.logger.error(e)
        token_pickle = {}
    return token_pickle


# Function for auto saving spotify token_dict to db
def save_spotify_token(token_dict):
    token_dict = {
        'access_token': token_dict.access_token,
        'expires_at': token_dict.expires_at,
        'refresh_token': token_dict.refresh_token,
        'token_type': token_dict.token_type
    }
    # Delete current key
    app.server.logger.debug('Deleting current spotify tokens')
    app.session.execute(delete(apiTokens).where(apiTokens.service == 'Spotify'))
    # Insert new key
    app.server.logger.debug('Inserting new strava tokens')
    app.session.add(apiTokens(date_utc=datetime.utcnow(), service='Spotify', tokens=pickle.dumps(token_dict)))
    app.session.commit()
    app.session.remove()


def spotify_connected():
    try:
        client = get_spotify_client()
        test = client.current_user_top_tracks(limit=10)
        app.server.logger.debug('Spotify connected')
        return True
    except BaseException as e:
        app.server.logger.error('Spotify not connected')
        app.server.logger.error(e)
        return False


## Provide link for button on settings page
def connect_spotify_link(auth_client):
    return auth_client.url


def get_spotify_client():
    token_dict = current_token_dict()
    if token_dict:
        # If token has expired, refresh it
        if int(time.time()) > token_dict['expires_at']:
            app.server.logger.debug('Spotify tokens expired, refreshing...')
            new_token = tk.Credentials(client_id=client_id, client_secret=client_secret,
                                       redirect_uri=redirect_uri).refresh_user_token(token_dict['refresh_token'])
            # Save to DB
            save_spotify_token(new_token)
            # Query the new tokens into a dict
            token_dict = current_token_dict()

        client = tk.Spotify(token_dict['access_token'])
    else:
        client = tk.Spotify()

    return client


# def save_spotify_play_history():
### Replaced with live stream() function
#     '''
#     Function that we be polled every refresh to populate spotify_play_history table
#     :return:
#     '''
#     if spotify_connected():
#         app.server.logger.info('Pulling spotify play history...')
#         spotify = get_spotify_client()
#         # Get latest tracks
#         tracks = spotify.playback_recently_played(limit=50).items
#         # Get features of all the tracks to join in with track information
#         track_features = pd.DataFrame(json.loads(spotify.tracks_audio_features([x.track.id for x in tracks]).json()))
#         # Get track information
#         track_information = []
#         for x in tracks:
#             x = json.loads(x.track.json())
#             if x['type'] == 'track':  # Only add tracks (no podcasts, etc.)
#                 track_information.append({
#                     "timestamp_utc": datetime.utcfromtimestamp(float(x.timestamp_utc) / 1000),
#                     "track_id": x["id"],
#                     "track_name": x["name"],
#                     "explicit": x["explicit"],
#                     "artist_id": ', '.join([y["id"] for y in x["artists"]]),
#                     "artist_name": ', '.join([y["name"] for y in x["artists"]]),
#                     # URLs do not need to be stored, can be generated with
#                     # # https://open.spotify.com/track/<track_id>
#                     # https://open.spotify.com/artist/<artist_id>
#                     # https://open.spotify.com/album/<album_id>
#                     "album_id": x["album"]["id"],
#                     "album_name": x["album"]["name"]
#                 })
#
#         # Convert trackinfo into df
#         track_info_df = pd.DataFrame(track_information)
#         # Merge trackinfo with track features
#         track_table = pd.merge(track_info_df, track_features, how='left', left_on='track_id', right_on='id').set_index(
#             'timestamp_utc')
#         track_table.drop_duplicates(inplace=True)
#         track_table = track_table.drop(columns=['id', 'type', 'uri', 'track_href'])
#
#         # Filter to only new records and insert into DB
#         latest = app.session.query(func.max(spotifyPlayHistory.timestamp_utc)).first()[0]
#         app.session.remove()
#         if latest:
#             track_table = track_table[track_table.index > latest]
#
#         if len(track_table) > 0:
#             app.server.logger.debug(f'{len(track_table)} new songs found!')
#             track_table.to_sql('spotify_play_history', engine, if_exists='append', index=True)


def get_played_tracks(workout_intensity='all', sport='all', pop_time_period='all'):
    '''

    :param workout_intensity: (Optional) Filters the spotify tracks by the intensity of the workout that was done
    :return: df of spotify tracks that were done during a workout
    '''

    # Query tracks
    if pop_time_period == 'all':
        df_tracks = pd.read_sql(sql=app.session.query(spotifyPlayHistory).statement, con=engine)
        df_tracks['Period'] = 'Current'

    elif pop_time_period == 'ytd':
        df_tracks = pd.read_sql(sql=app.session.query(spotifyPlayHistory).filter(
            extract('year', spotifyPlayHistory.timestamp_utc) >= (datetime.utcnow().year - 1)).statement, con=engine)

        df_tracks['Period'] = 'Current'
        df_tracks.at[df_tracks['timestamp_utc'].dt.year == (datetime.utcnow().date().year - 1), 'Period'] = 'Previous'

    elif pop_time_period in ['l90d', 'l6w', 'l30d']:
        days = {'l90d': 180, 'l6w': 84, 'l30d': 60}
        df_tracks = pd.read_sql(sql=app.session.query(spotifyPlayHistory).filter(
            spotifyPlayHistory.timestamp_utc >= (
                    datetime.utcnow().date() - timedelta(days=days[pop_time_period]))).statement,
                                con=engine)
        df_tracks['Period'] = 'Current'
        df_tracks.at[
            df_tracks['timestamp_utc'].dt.date <= (
                    datetime.utcnow().date() - timedelta(days=days[pop_time_period] / 2)), 'Period'] = 'Previous'

    # Query workouts
    df_summary = pd.read_sql(
        sql=app.session.query(stravaSummary.start_date_utc, stravaSummary.activity_id, stravaSummary.name,
                              stravaSummary.elapsed_time, stravaSummary.type,
                              stravaSummary.workout_intensity).statement, con=engine)
    df_summary['end_date_utc'] = df_summary['start_date_utc'] + pd.to_timedelta(df_summary['elapsed_time'], 's')
    df_summary.drop(columns=['elapsed_time'], inplace=True)

    # Full Cross Join
    df_tracks = df_tracks.assign(join_key=1)
    df_summary = df_summary.assign(join_key=1)
    df_merge = pd.merge(df_summary, df_tracks, on='join_key').drop('join_key', axis=1)
    # Filter only on tracks performed during workout times
    df_merge = df_merge.query('timestamp_utc >= start_date_utc and timestamp_utc <= end_date_utc')
    # Join back to original date range table and drop key column
    df = df_tracks.merge(df_merge, on=['timestamp_utc'], how='left').fillna('').drop('join_key', axis=1)
    # Days with no workout_intensity are rest days
    df.at[df['start_date_utc'] == '', 'workout_intensity'] = 'rest'
    # Cleanup the end resulting df
    df = df[[c for c in df.columns if '_y' not in c]]
    df.columns = [c.replace('_x', '') for c in df.columns]
    df = df.rename(columns={'type': 'workout_type', 'name': 'workout_name'})
    # Filter on workout intensity/rest day
    if workout_intensity == 'workout':
        df = df[df['workout_intensity'] != 'rest']
    elif workout_intensity != 'all':
        df = df[df['workout_intensity'] == workout_intensity]
    # Filter on workout type
    if sport != 'all':
        df = df[df['workout_type'] == sport]

    df.drop(columns=['start_date_utc', 'end_date_utc'], inplace=True)

    df.set_index('timestamp_utc', inplace=True)

    return df


### Predictive Modeling ###
def generate_recommendation_playlists(workout_intensity='all', sport='all', normalize=True,
                                      num_clusters=8,  # TODO: Create dynamic approach to calculation best num_clusters
                                      num_playlists=3, time_period='l90d'):
    '''
    KMeans to cluster types of music detected in history
    Filter music in each cluster that was 'liked' (not skipped per thresholds in config.ini)
    Uses resulting tracks as seeds for spotifys recommend api

    :param workout_intensity: specify intensity for querying seeds
    :param sport: specify workout type for querying seeds
    :param normalize: boolean for normalizing audio features
    :param num_clusters: number of clusters K-Means will use
    :param num_playlists: number of spotify playlists to be generated
    :param time_period: time period for querying seeds
    :return: None; generates spotify playlists
    '''
    # Inspired by http://ben-tanen.com/notebooks/kmeans-music.html

    # Clear all Fitly playlists
    spotify = get_spotify_client()
    user_id = spotify.current_user().id

    playlists = {}
    for x in spotify.playlists(user_id).items:
        playlists[x.name] = x.id
        if 'Fitly' in x.name:
            spotify.playlist_clear(x.id)

    # Query tracks to use as seeds for generating recommendations
    df = get_played_tracks(workout_intensity=workout_intensity, sport=sport, pop_time_period=time_period).reset_index()

    # Filter on correct dates
    df = df[df['Period'] == 'Current']

    if len(df) >= num_clusters:

        _audiofeat_df = df[['track_id', 'time_signature', 'duration_ms', 'acousticness', 'danceability',
                            'energy', 'instrumentalness', 'key', 'liveness', 'loudness', 'mode', 'speechiness',
                            'tempo', 'valence']]

        # scale audio features (if desired)
        if normalize:
            scaler = StandardScaler()
            audiofeat = scaler.fit_transform(_audiofeat_df.drop(['track_id'], axis=1))
            audiofeat_df = pd.DataFrame(audiofeat, columns=_audiofeat_df.drop('track_id', axis=1).columns)
            audiofeat_df['track_id'] = _audiofeat_df['track_id']
        else:
            audiofeat_df = _audiofeat_df

        # Run the K-Means to cluster all tracks
        kmeans = KMeans(n_clusters=num_clusters).fit(audiofeat_df.drop(['track_id'], axis=1))
        audiofeat_df['cluster'] = pd.Series(kmeans.labels_) + 1

        # Join cluster back to main track df
        df = df.merge(audiofeat_df[['track_id', 'cluster']], how='left', left_on='track_id', right_on='track_id')

        # drop clusters that don't have both likes and dislikes
        df = df[df['cluster'].isin(
            df.groupby('cluster').filter(lambda x: x['skipped'].nunique() == 2)['cluster'].unique().tolist())]

        # Start with largest cluster and work through all until num_playlists have been generated
        rand_clusters = df.groupby('cluster').size().sort_values(ascending=False).index.tolist()
        # Create the playlists!
        playlist_number = 1
        for cluster in rand_clusters:
            if playlist_number < num_playlists + 1:

                # Keep looping through cluster passing different tracks into spotify recommendation api
                # Once enough tracks recived from spotify pass our prediction model, move to next cluster
                # We want at least 50 tracks in each playlist
                # If we hit recommendation api 10 times and still don't have enough good results, move on as to not overload spotify api
                attempts = 0
                predict_df = pd.DataFrame()
                # Only choose tracks that were 'liked' in the cluster for seeds
                track_uris = df[(df['cluster'] == cluster) & (df['skipped'] == 0)]['track_id'].unique().tolist()
                # artist_uris = df[df['cluster'] == i]['artist_id'].unique().tolist()
                while len(predict_df) < 50 and attempts < 20:
                    # Get 5 random tracks from the cluster to use as seeds for recommendation (spotify api can only take up to 5 seeds)
                    seed_tracks = random.sample(track_uris, 5 if len(track_uris) > 5 else len(track_uris))
                    # seed_artists = random.sample(artist_uris, 5 if len(artist_uris) > 5 else len(artist_uris))

                    # Get recommendations from spotify
                    recommendations = spotify.recommendations(track_ids=seed_tracks, limit=50).tracks
                    # recommendations = spotify.recommendations(artist_ids=artist_uris, limit=50).tracks

                    # Predict if you will like the songs spotify recommends, and if true add them to playlist
                    try:
                        rec_track_features = pd.DataFrame(
                            json.loads(spotify.tracks_audio_features([x.id for x in recommendations]).json()))
                        # Use all tracks in the same cluster (likes/dislikes) as train data set
                        _predict_df = predict_songs(df_tracks=rec_track_features, df_train=df[df['cluster'] == cluster])
                        if len(_predict_df) > 0:
                            # Only take predictions that are positive
                            _predict_df = _predict_df[_predict_df['predictions'] == 1]
                            # add to predict dataframe and repeat loop until > 50 tracks to insert into the playlist
                            predict_df = pd.concat([predict_df, _predict_df]).drop_duplicates()
                    except Exception as e:
                        app.server.logger.error(f'ERROR Creating Playlist: {e}')

                    # time.sleep(1)  # Avoid spotify api limit
                    attempts += 1

                if len(predict_df) > 0:
                    # Grab playlist id if it already exists otherwise create the playlist
                    playlist_id = playlists.get(f'Fitly Playlist {playlist_number}')
                    if not playlist_id:
                        playlist_id = spotify.playlist_create(user_id=user_id, name=f'Fitly Playlist {playlist_number}',
                                                              public=False).id
                    predict_df['track_uri'] = 'spotify:track:' + predict_df['id']
                    # Add recommended tracks to the playlist
                    app.server.logger.debug(f'Refreshing Fitly Playlist {playlist_number}...')
                    spotify.playlist_add(playlist_id=playlist_id, uris=predict_df['track_uri'].tolist())
                    app.server.logger.debug(f'Fitly Playlist {playlist_number} refreshed')
                    playlist_number += 1
                else:
                    continue

    else:
        app.server.logger.debug(
            f'Not enough tracks found for "{workout_intensity}" intensity and "{sport}" workout types to generate playlist recommendations. Skipping playlist generation.')


#### Models to predict if you will actually like the recommend songs ####

class PModel(object):
    def __init__(self, X_train, X_test, y_train, y_test):
        self.X_train = X_train
        self.X_test = X_test
        self.y_train = y_train
        self.y_test = y_test

    def get_best_model(self):
        # Run all models and return best
        self.model_scores = {}
        self.best_model = None
        self.best_model_name = None
        try:
            self.knn()
            self.model_scores['knn'] = self.knn_roc
        except BaseException as e:
            app.server.logger.error('Error running kNN model: {}'.format(e))
        try:
            self.logreg()
            self.model_scores['logreg'] = self.logreg_roc
        except BaseException as e:
            app.server.logger.error('Error running logreg model: {}'.format(e))
        try:
            self.rf()
            self.model_scores['rf'] = self.rf_roc
        except BaseException as e:
            app.server.logger.error('Error running rf model: {}'.format(e))
        try:
            self.mlp()
            self.model_scores['mlp'] = self.mlp_roc
        except BaseException as e:
            app.server.logger.error('Error running mlp model: {}'.format(e))

        if len(self.model_scores) > 0:
            self.best_model_name = [k for k, v in self.model_scores.items() if v == max(self.model_scores.values())][0]

            if self.best_model_name == 'kkn':
                self.best_model = self.knn
                self.best_model_score = self.knn_roc

            elif self.best_model_name == 'logreg':
                self.best_model = self.logreg
                self.best_model_score = self.logreg_roc

            elif self.best_model_name == 'rf':
                self.best_model = self.rf
                self.best_model_score = self.rf_roc

            elif self.best_model_name == 'mlp':
                self.best_model = self.mlp
                self.best_model_score = self.mlp_roc

    def knn(self):
        self.knn = KNeighborsClassifier()
        self.knn.fit(self.X_train, self.y_train)
        y_pred_knn = self.knn.predict(self.X_test)
        y_pred_prob_knn = self.knn.predict_proba(self.X_test)[:, 1]
        self.knn_roc = roc_auc_score(self.y_test, y_pred_prob_knn)

    def logreg(self):
        """
        Implements Logistic Regression algorithm
        """
        self.logreg = LogisticRegression()
        self.logreg.fit(self.X_train, self.y_train)
        y_pred_logreg = self.logreg.predict(self.X_test)
        y_pred_prob_logreg = self.logreg.predict_proba(self.X_test)[:, 1]
        self.logreg_roc = roc_auc_score(self.y_test, y_pred_prob_logreg)

    def rf(self):
        """
        Implements Random Forest algorithm
        """
        self.rf = RandomForestClassifier()
        self.rf.fit(self.X_train, self.y_train)
        y_pred_rf = self.rf.predict(self.X_test)
        y_pred_prob_rf = self.rf.predict_proba(self.X_test)[:, 1]
        self.rf_roc = roc_auc_score(self.y_test, y_pred_prob_rf)

    def mlp(self):
        """
        Implements Multilayer Perceptron (Neural Net) algorithm
        """
        self.mlp = MLPClassifier()
        self.mlp.fit(self.X_train, self.y_train)
        y_pred_mlp = self.mlp.predict(self.X_test)
        y_pred_prob_mlp = self.mlp.predict_proba(self.X_test)[:, 1]
        self.mlp_roc = roc_auc_score(self.y_test, y_pred_prob_mlp)


def predict_songs(df_tracks, df_train):
    '''
    Queiries spotify_play_history to train models on what songs you 'like'
    then predicts if user will like songs passed as an argument through 'df_tracks'

    :param df_tracks: dataframe of tracks to do predictions on
    :param df_train: dataframe of tracks to train model on
    :return: df_tracks with 'predictions'
    '''
    run_time = datetime.utcnow()

    # Preprocess data to get a "target" column. If song is not skipped (within thresholds), 'liked'
    # df_train['explicit'] = df_train['explicit'].apply(lambda x: 1 if x == True else 0)
    df_train['target'] = 0
    df_train.at[df_train['skipped'] == 0, 'target'] = 1

    # Seperate features into features and labels dataset
    X = df_train[['energy', 'liveness', 'tempo', 'speechiness', 'acousticness', 'instrumentalness', 'time_signature',
                  'danceability', 'key', 'duration_ms', 'loudness', 'valence', 'mode',
                  # 'explicit'
                  ]]
    y = df_train[['target']]

    # Split data into training and test dataset
    X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=42)

    # Reshape dimensions of labels (y)
    y_train = np.ravel(y_train)
    y_test = np.ravel(y_test)

    # print(len(like_final))
    # print(len(dislike_final))
    # print(X_train.shape)
    # print(X_test.shape)

    # Create a model object
    model = PModel(X_train, X_test, y_train, y_test)
    # Run all models and set best one
    model.get_best_model()

    if model.best_model is not None:
        app.server.logger.info('Predicting songs with the {} model with {} accuracy'.format(model.best_model_name,
                                                                                            model.best_model_score))
        # Make predictions on df of songs
        df_tracks['predictions'] = df_tracks[[
            'energy', 'liveness', 'tempo', 'speechiness', 'acousticness', 'instrumentalness', 'time_signature',
            'danceability', 'key', 'duration_ms', 'loudness', 'valence', 'mode',
            # 'explicit'
        ]].apply(
            lambda x: model.best_model.predict([x])[0], axis=1)

        df_tracks['model_name'] = model.best_model_name
        df_tracks['model_score'] = model.best_model_score
        df_tracks['mode_run_date'] = run_time

        return df_tracks

    else:
        app.server.logger.info('Could not run prediction with any models')
        return pd.DataFrame()


### Spotify Stream ###
def stream():
    '''
    Captures live activity of spotify web player and adds list of states (playback feed) to queue after each song finishes
    :param tekoreClient: tekoreClient obejct
    :return: none
    '''
    global current_state
    global last_state
    global playback_feed
    tekoreClient = get_spotify_client()
    # current_state = tekoreClient.playback()

    try:
        # Do not overwrite last_state until next state that is pulled below is not none
        if hasattr(current_state, 'item'):
            last_state = current_state

        current_state = tekoreClient.playback_currently_playing()

        if hasattr(current_state, 'item'):
            try:
                last_song = last_state.item.id
            except:
                last_song = 'No Stream Detected'
            current_song = current_state.item.id

            # If song changed add feed to queue for parsing, otherwise continue appending feed
            # If song is on repeat will show as 'rewind'
            if last_song != current_song and len(playback_feed) > 0:
                # app.server.logger.debug(
                #     'Song changed from "{}" to "{}"'.format(last_state.item.name, current_state.item.name))
                # Add to queue for parsing
                q.put(playback_feed)
                # Clear out feed for next track
                playback_feed = []
            elif current_state.item.type == 'track':
                playback_feed.append(current_state)

                # If the song has not been changed for longer than 5x the length of current song, listening
                # session is probably over. Clear out current/last state
                if len(playback_feed) > 5 * (float(current_state.item.duration_ms / 1000)):
                    current_state, last_state = None, None
    except BaseException as e:
        app.server.logger.error(f'Error with spotify stream: {e}')


class Parser(threading.Thread):
    def __init__(self, queue):
        app.server.logger.debug('Parser thread started')
        threading.Thread.__init__(self)
        self.q = queue

    def run(self):
        while True:
            playback_feed = self.q.get()
            # Parse feed
            parse_stream(playback_feed)
            # Mark task complete
            self.q.task_done()


# Thread for parsing into db while stream is running
parser = Parser(queue=q)
parser.daemon = True
parser.start()


def parse_stream(playback_feed):
    # Check that song was listened to for longer than threshold
    secs_playing, secs_paused = 0, 0
    for x in playback_feed:
        if x.is_playing:
            secs_playing += 1
        else:
            secs_paused += 1

    secs_playing *= poll_interval_seconds
    secs_paused *= poll_interval_seconds

    # Check if song was listened to for longer than config threshold
    if int(secs_playing) >= int(min_secs_listened):
        track_name = playback_feed[0].item.name
        app.server.logger.info(
            '"{}" listened to for longer than {} seconds. Parsing stream...'.format(track_name, min_secs_listened))

        # Was song skipped?
        track_last_state = playback_feed[-1]
        progress = track_last_state.progress_ms
        duration = track_last_state.item.duration_ms

        # This uses true amount of time song was playing for. May not be 100% accurate as some poll requests don't go through,
        percentage_listened = math.ceil(
            (secs_playing / (duration / 1000)) * 100) / 100

        # percentage_listened = round(progress / duration, 2)  # this uses whenever the song ended

        # If song 'finished' because of crossfade, mark as 100% listened
        # Spotify max crossfade is 12 seconds, so assume it is set to the max
        if percentage_listened >= .9 and ((duration - progress) / 1000) <= 12:
            percentage_listened = 1
        # Song 'skipped' if only actually listened to for 5% - 80% (or overridden config values) of its total duration
        skipped = (skip_min_threshold <= percentage_listened <= skip_max_threshold)

        # Was song rewound?
        rewound = False
        old_progress = 0
        for state in playback_feed:
            new_progress = state.progress_ms
            if new_progress < old_progress:
                rewound = True
                break
            else:
                old_progress = new_progress

        # Was song fast forwarded? (Skipped forward more than 3 seconds)
        fast_forwarded = False
        old_progress = 0
        for state in playback_feed:
            new_progress = state.progress_ms
            if new_progress / 1000 >= (old_progress / 1000) + 3:
                fast_forwarded = True
                break
            else:
                old_progress = new_progress

        track_info_df = pd.DataFrame([{
            "timestamp_utc": datetime.utcfromtimestamp(float(playback_feed[0].timestamp) / 1000),
            "track_id": playback_feed[0].item.id,
            "track_url": playback_feed[0].item.href,
            "track_name": track_name,
            "explicit": playback_feed[0].item.explicit,
            "artist_id": ', '.join([y.name for y in playback_feed[0].item.artists]),
            "artist_name": ', '.join([y.name for y in playback_feed[0].item.artists]),
            # URLs do not need to be stored, can be generated with
            # # https://open.spotify.com/track/<track_id>
            # https://open.spotify.com/artist/<artist_id>
            # https://open.spotify.com/album/<album_id>
            "album_id": playback_feed[0].item.album.id,
            "album_name": playback_feed[0].item.album.name,
            "duration_ms": playback_feed[0].item.duration_ms,
            "percentage_listened": percentage_listened,
            "skipped": skipped,
            "rewound": rewound,
            "fast_forwarded": fast_forwarded,
            "secs_playing": secs_playing,
            "secs_paused": secs_paused
        }])

        spotify = get_spotify_client()
        track_features = pd.DataFrame(
            json.loads(spotify.tracks_audio_features([playback_feed[0].item.id]).json())).drop(
            columns=['duration_ms', 'type', 'analysis_url', 'uri', 'track_href'])

        # Merge trackinfo with track features
        track_table = pd.merge(track_info_df, track_features, how='left', left_on='track_id', right_on='id').set_index(
            'timestamp_utc').drop(columns=['id'])
        # Insert into DB
        track_table.to_sql('spotify_play_history', engine, if_exists='append', index=True)
