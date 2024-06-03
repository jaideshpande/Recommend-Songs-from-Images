import spotipy
import time
from spotipy.oauth2 import SpotifyOAuth 
import os

from flask import Flask, request, url_for, session, redirect, render_template
from werkzeug.utils import secure_filename


#Import statements for recognizing an image
import google.generativeai as genai
import PIL.Image


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
    img = PIL.Image.open('flower.jpg')
    model = genai.GenerativeModel('gemini-pro-vision')
    response = model.generate_content(["Describe the mood and thematic content of the image using as many descriptive adjectives as possible.", img], stream=True)
    response.resolve()

    textModel = genai.GenerativeModel('gemini-pro')
    prompt = f"Given this description: {response.text} and a list of artists I like {top_artists}, recommend a song I'd like that would fit well with this image. It doesn't have to be by one of these artists, but it should be similar. Only print the name of the song and the artist."
    #prompt = f"Given this description: {response.text} recommend a song that would fit well with this image. Only print the name of the song and the artist."

    textResponse = textModel.generate_content(prompt) 
    output =  str(textResponse.text)
    output = output.replace(' by', '')
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
                        scope = 'user-library-read playlist-modify-public playlist-modify-private user-read-playback-state user-modify-playback-state user-top-read'
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
            return redirect(url_for('play_song', external=True))
        else:
            return 'Invalid file type or no file selected', 400

    # This line renders the upload form on a GET request
    return render_template('upload.html')


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)

