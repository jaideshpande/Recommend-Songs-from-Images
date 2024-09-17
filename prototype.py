import spotipy
import time
from spotipy.oauth2 import SpotifyOAuth 
import os

from flask import Flask, request, url_for, session, redirect, render_template
from werkzeug.utils import secure_filename


#Import statements for recognizing an image
import google.generativeai as genai
from PIL import Image


app = Flask(__name__)

app.config['SESSION_COOKIE_NAME'] = "Spotify Cookie"
app.secret_key = 'safsl452hlhsasfuihil*^1'

TOKEN_INFO = 'token_info'
token_info = None

genai.configure(api_key='AIzaSyBgfmgzdWIQcofocB04E3entWOs5aY--js') # set into env variable

#For user image upload
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'jpg'}

@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)


@app.route('/redirect')
def redirect_page():
    session.clear()
    code = request.args.get('code')
    token_info = create_spotify_oauth().get_access_token(code) # this exchanges the auth code for an access token
    session[TOKEN_INFO] = token_info
    #return redirect(url_for('play_song', external=True))
    return redirect(url_for('file_upload', external=True))



def determine_song_rec():
    try:
        token_info = get_token()
    except:
        print("User not logged in")
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token']) # Find a way avoid repetition with this line
    top_artists = sp.current_user_top_artists(limit=10)

# Determine song rec from input image. Image --> text description --> song rec based on preferences
    filepath = session.get('filepath')
    img = Image.open(filepath)
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(["Rate this image's energy as a decimal value on a scale from 0 to 1, where 0 is the dullest, lowest energy. And 1 is the most vibrant, fast-moving image possible. Only return the decimal value and nothing else.", img], stream=True)
    response.resolve()
    response_checker = str(response.text)
    print(response_checker)

    textModel = genai.GenerativeModel('gemini-pro')
    fav_songs = get_top_tracks(sp)
    #prompt = f"Given this image description: {response.text} and a list of songs I like: {fav_songs}, recommend one song that best fits the description that I would like. Only print the name of the song."
    prompt = f"Given this rating of an image's energy (from 0 to 1): {response.text} , and a list of my favorite songs: {fav_songs}, recommend a song that would fit well with this image. Only print the name of the song and the artist."
    

    textResponse = textModel.generate_content(prompt) 
    output =  str(textResponse.text)
    #output = output.replace(' by', '')
    print(output)
    playlist_checker = get_playlist_tracks(sp,'37i9dQZEVXbLRQDuF5jeBp')
    print(playlist_checker)
    return output
    

def get_token():  # refreshes token if it expires
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        redirect(url_for('login', external = False))
    now = int(time.time())

    is_expired = token_info['expires_at'] - now < 60
    if (is_expired):
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info


def create_spotify_oauth():
    return SpotifyOAuth(client_id = '0fd41a617c7a41018be9a9cb8bcf2582',
                        client_secret = '7b977dcb49d64486ae0b1e9018562f45',
                        redirect_uri = url_for('redirect_page', _external= True),
                        scope = 'user-library-read playlist-modify-public playlist-modify-private user-read-playback-state user-modify-playback-state user-top-read playlist-read-private playlist-read-collaborative'
                        )

@app.route('/play_song')
def play_song():
    try:
        token_info = get_token()
    except:
        print("User not logged in")
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token'])
    #user_id = sp.current_user()['id']   

    track_title = determine_song_rec() 
    track_uri = search_track(sp, track_title)
    
    if track_uri:
        # Get the available devices
        devices = sp.devices()['devices']
        if devices:
            # Pick the first available device
            device_id = devices[0]['id']
            sp.start_playback(device_id=device_id, uris=[track_uri])
            return f"Playing {track_title} on device {devices[0]['name']}" 
        else:
            return "No active devices found. Please open Spotify on a device and try again."
    else:
        return "Track not found"

def get_top_tracks(sp):
    # Initialize an empty list to store song titles
    song_titles = []
    results = sp.current_user_top_tracks(limit=50, time_range='medium_term')  # Adjust time_range if necessary
    for item in results['items']:
        # Append only the song title to the list
        song_titles.append(item['name'])
    
    return song_titles  # Return the list of song titles


def get_top_track_ids(sp):
    top_tracks = sp.current_user_top_tracks(limit=50)  # Fetch top 50 tracks
    top_track_ids = [track['id'] for track in top_tracks['items']]
    return top_track_ids


def get_playlist_tracks(sp,playlist_id):
     # Ensure we have a token
    if not sp.auth_manager.get_access_token(as_dict=False):
        raise Exception("Failed to obtain access token")

    # Fetch tracks from the playlist
    results = sp.playlist_tracks(playlist_id)
    tracks = []
    while results:
        for item in results['items']:
            track = item['track']
            if track:  # Check if track details are present
                title = track['name']
                artists = ', '.join(artist['name'] for artist in track['artists'])
                tracks.append((title, artists))
        if results['next']:
            results = sp.next(results)
        else:
            break
    return tracks







def search_track(sp, track_title):
    results = sp.search(q=track_title, type='track', limit=1)
    tracks = results['tracks']['items']
    if tracks:
        return tracks[0]['uri']
    return None

def play_track(sp, track_uri):
    sp.start_playback(uris=[track_uri])


# Check if user image is in right format
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route

@app.route('/upload', methods=['GET', 'POST'])
def file_upload():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            session['filepath'] = filepath
            return redirect(url_for('play_song', external=True))
        else:
            return 'Invalid file type or no file selected', 400

    # This line renders the upload form on a GET request
    return render_template('upload.html')





if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)

