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
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import numpy as np
import random

client_id = config.get('spotify', 'client_id')
client_secret = config.get('spotify', 'client_secret')
redirect_uri = config.get('spotify', 'redirect_uri')


# Retrieve current tokens from db
def current_token_dict():
    try:
        token_dict = app.session.query(apiTokens.tokens).filter(apiTokens.service == 'Spotify').first()
        token_dict = ast.literal_eval(token_dict[0]) if token_dict else {}
        app.session.remove()
    except BaseException as e:
        app.server.logger.error(e)
        token_dict = {}
    return token_dict


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
    app.session.add(apiTokens(date_utc=datetime.utcnow(), service='Spotify', tokens=str(token_dict)))
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


def save_spotify_play_history():
    '''
    Function that we be polled every refresh to populate spotify_play_history table
    :return:
    '''
    if spotify_connected():
        app.server.logger.info('Pulling spotify play history...')
        spotify = get_spotify_client()
        # Get latest tracks
        tracks = spotify.playback_recently_played(limit=50).items
        # Get features of all the tracks to join in with track information
        track_features = pd.DataFrame(json.loads(spotify.tracks_audio_features([x.track.id for x in tracks]).json()))
        # Get track information
        track_information = []
        for x in tracks:
            played_at = x.played_at
            x = json.loads(x.track.json())
            if x['type'] == 'track':  # Only add tracks (no podcasts, etc.)
                track_information.append({
                    "played_at": pd.to_datetime(played_at),
                    "track_id": x["id"],
                    "track_name": x["name"],
                    "explicit": x["explicit"],
                    "artist_id": ', '.join([y["id"] for y in x["artists"]]),
                    "artist_name": ', '.join([y["name"] for y in x["artists"]]),
                    # URLs do not need to be stored, can be generated with
                    # # https://open.spotify.com/track/<track_id>
                    # https://open.spotify.com/artist/<artist_id>
                    # https://open.spotify.com/album/<album_id>
                    "album_id": x["album"]["id"],
                    "album_name": x["album"]["name"]
                })

        # Convert trackinfo into df
        track_info_df = pd.DataFrame(track_information)
        # Merge trackinfo with track features
        track_table = pd.merge(track_info_df, track_features, how='left', left_on='track_id', right_on='id').set_index(
            'played_at')
        track_table.drop_duplicates(inplace=True)
        track_table = track_table.drop(columns=['id', 'type', 'uri', 'track_href'])

        # Filter to only new records and insert into DB
        latest = app.session.query(func.max(spotifyPlayHistory.played_at)).first()[0]
        app.session.remove()
        if latest:
            track_table = track_table[track_table.index > latest]

        if len(track_table) > 0:
            app.server.logger.debug(f'{len(track_table)} new songs found!')
            track_table.to_sql('spotify_play_history', engine, if_exists='append', index=True)


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
            extract('year', spotifyPlayHistory.played_at) >= (datetime.utcnow().year - 1)).statement, con=engine)

        df_tracks['Period'] = 'Current'
        df_tracks.at[df_tracks['played_at'].dt.year == (datetime.utcnow().date().year - 1), 'Period'] = 'Previous'

    elif pop_time_period in ['l90d', 'l6w', 'l30d']:
        days = {'l90d': 180, 'l6w': 84, 'l30d': 60}
        df_tracks = pd.read_sql(sql=app.session.query(spotifyPlayHistory).filter(
            spotifyPlayHistory.played_at >= (
                    datetime.utcnow().date() - timedelta(days=days[pop_time_period]))).statement,
                                con=engine)
        df_tracks['Period'] = 'Current'
        df_tracks.at[
            df_tracks['played_at'].dt.date <= (
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
    df_merge = df_merge.query('played_at >= start_date_utc and played_at <= end_date_utc')
    # Join back to original date range table and drop key column
    df = df_tracks.merge(df_merge, on=['played_at'], how='left').fillna('').drop('join_key', axis=1)
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

    df.set_index('played_at', inplace=True)

    return df


def generate_recommendation_playlists(workout_intensity='all', sport='all', normalize=True, num_clusters=25,
                                      num_playlists=3, time_period='l90d'):
    '''

    :param workout_intensity: specify intensity for querying seeds
    :param sport: specify workout type for querying seeds
    :param normalize: boolean for normalizing audio features
    :param num_clusters: number of clusters K-Means will use
    :param num_playlists: number of spotify playlists to be generated
    :param time_period: time period for querying seeds
    :return: None; generates spotify playlists
    '''

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
    df = df[df['Period'] == 'Current']
    if len(df) >= num_clusters:

        _audiofeat_df = df[
            ['track_id', 'time_signature', 'duration_ms', 'acousticness', 'danceability',
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

        ### Choose N (num_playlists) random clusters to get tracks to be used as seeds for getting recommendations as creating playlists
        rand_clusters = np.random.choice(df['cluster'].unique(), num_playlists, False).tolist()

        # Create the playlists!
        for i in range(1, len(rand_clusters) + 1):
            # Grab playlist id if it already exists otherwise create the playlist
            sport = sport + ' ' if sport else ''
            playlist_id = playlists.get(f'Fitly Playlist {i}')
            if not playlist_id:
                playlist_id = spotify.playlist_create(user_id=user_id, name=f'Fitly Playlist {i}', public=False).id

            # Get 5 random tracks from the cluster to use as seeds for recommendation
            track_uris = df[df['cluster'] == i]['track_id'].unique().tolist()
            # artist_uris = df[df['cluster'] == i]['artist_id'].unique().tolist()

            seed_tracks = random.sample(track_uris, 5 if len(track_uris) > 5 else len(track_uris))
            # seed_artists = random.sample(artist_uris, 5 if len(artist_uris) > 5 else len(artist_uris))

            # Get recommendations from spotify
            recommendations = spotify.recommendations(track_ids=seed_tracks, limit=50).tracks
            # recommendations = spotify.recommendations(artist_ids=artist_uris, limit=50).tracks

            # Add recommended tracks to the playlist
            spotify.playlist_add(playlist_id=playlist_id, uris=[x.uri for x in recommendations])
            app.server.logger.debug(f'Fitly Playlist {i} refreshed')

    else:
        app.server.logger.debug(
            f'Not enough tracks found for "{workout_intensity}" intensity and "{sport}" workout types to generate playlist recommendations. Skipping playlist generation.')
