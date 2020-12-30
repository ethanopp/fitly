import tekore as tk
import pandas as pd
import json
from ..utils import config
from ..app import app
from ..api.database import engine
from ..api.sqlalchemy_declarative import apiTokens, spotifyPlayHistory, stravaSummary
from sqlalchemy import delete, func
from datetime import datetime
import ast
import time

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
                    "track_url": x["external_urls"]["spotify"],
                    "track_isrc": x["external_ids"]["isrc"],
                    "track_popularity": x["popularity"],
                    "explicit": x["explicit"],
                    "artist_id": x["artists"][0]["id"],
                    "artist_name": x["artists"][0]["name"],
                    "artist_url": x["artists"][0]["external_urls"]["spotify"],
                    "album_id": x["album"]["id"],
                    "album_name": x["album"]["name"]
                })

        # Convert trackinfo into df
        track_info_df = pd.DataFrame(track_information)
        # Merge trackinfo with track features
        track_table = pd.merge(track_info_df, track_features, how='left', left_on='track_id', right_on='id').set_index(
            'played_at')
        track_table.drop_duplicates(inplace=True)
        track_table = track_table.drop(columns=['id', 'type', 'uri'])

        # Filter to only new records and insert into DB
        latest = app.session.query(func.max(spotifyPlayHistory.played_at)).first()[0]
        app.session.remove()
        if latest:
            track_table = track_table[track_table.index > latest]

        if len(track_table) > 0:
            app.server.logger.debug(f'{len(track_table)} new songs found!')
            track_table.to_sql('spotify_play_history', engine, if_exists='append', index=True)


def get_workout_tracks(workout_intensity=None, sport=None):
    '''

    :param workout_intensity: (Optional) Filters the spotify tracks by the intensity of the workout that was done
    :return: df of spotify tracks that were done during a workout
    '''
    # Query tracks and workouts
    df_summary = pd.read_sql(
        sql=app.session.query(stravaSummary.start_date_utc, stravaSummary.activity_id, stravaSummary.name,
                              stravaSummary.elapsed_time, stravaSummary.type,
                              stravaSummary.workout_intensity).statement, con=engine)
    df_summary['end_date_utc'] = df_summary['start_date_utc'] + pd.to_timedelta(df_summary['elapsed_time'], 's')
    df_summary.drop(columns=['elapsed_time'], inplace=True)
    df_tracks = pd.read_sql(sql=app.session.query(spotifyPlayHistory).statement, con=engine)
    # Full Cross Join
    df_tracks = df_tracks.assign(key=1)
    df_summary = df_summary.assign(key=1)
    df_merge = pd.merge(df_summary, df_tracks, on='key').drop('key', axis=1)
    # Filter only on tracks performed during workout times
    df_merge = df_merge.query('played_at >= start_date_utc and played_at <= end_date_utc')
    # Join back to original date range table and drop key column
    df = df_tracks.merge(df_merge, on=['played_at'], how='left').fillna('').drop('key', axis=1)
    # Cleanup the end resulting df
    df = df[[c for c in df.columns if '_y' not in c]]
    df.columns = [c.replace('_x', '') for c in df.columns]
    df = df.rename(columns={'type': 'workout_type', 'name': 'workout_name'})
    df = df[df['start_date_utc'] != '']
    # If workout intensity passed, filter on it
    if workout_intensity:
        df = df[df['workout_intensity'] == workout_intensity]
    if sport:
        df = df[df['workout_type'] == workout_intensity]

    df.drop(columns=['start_date_utc', 'end_date_utc'], inplace=True)

    df.set_index('played_at', inplace=True)

    return df


def get_recommendations():
    '''
    Queries the users play history table and passes filters specified by user in UI for recommendations
    :return:
    '''
    # TODO: Finish writing this function
    if spotify_connected():
        spotify = get_spotify_client()
        # Recommendations
        play_history = app.session.query(spotifyPlayHistory)

        recommendations = spotify.recommendations(track_ids=top_track_ids, limit=50).tracks
        spotify.recommendations()
