import math
import threading
import time as t
from lrclib import LrcLibAPI
import requests
import os
import base64
import hashlib
import urllib.parse as urlparse
import webbrowser
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import tkinter as tk
from webbrowser import *
import tkinter.font as tkFont
from dotenv import load_dotenv

# global params
code = ""
track = ""
lyrics = ""
lyricsLine = 0
index = 0
needsReset = False
hasResetted = True
lastClickX = 0
lastClickY = 0

# load dotenv
load_dotenv()

# whole o auth process
# returns Access Token
def authProcess():
    # Client authorisation
    def generate_random_string(length):
        possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        values = os.urandom(length)
        return ''.join(possible[b % len(possible)] for b in values)

    codeVerifier = generate_random_string(64)

    async def sha256(plain):
        return hashlib.sha256(plain.encode()).digest()

    def base64encode(input):
        return base64.urlsafe_b64encode(input).decode('utf-8').rstrip('=')

    hashed = hashlib.sha256(codeVerifier.encode()).digest()
    codeChallenge = base64encode(hashed)

    clientId = os.getenv('clientId')
    redirectUri = 'http://localhost:8080'
    scope = 'user-read-currently-playing user-read-playback-state' 

    params = {
        'response_type': 'code',
        'client_id': clientId,
        'scope': scope,
        'code_challenge_method': 'S256',
        'code_challenge': codeChallenge,
        'redirect_uri': redirectUri,
    }

    url = "https://accounts.spotify.com/authorize"

    req = requests.PreparedRequest()
    req.prepare_url(url, params)

    # Define the callback server parameters
    callback_port = 8080
    callback_path = '/callback'

    # Define the handler for the HTTP server
    class SpotifyAuthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            # Parse the URL to get the code parameter
            query = urlparse(self.path).query
            params = parse_qs(query)
            if 'code' in params:
                global code
                code = params['code'][0]
            else:
                print("Authorization code not found in the URL.")

            # Send a response back to the browser
            self.send_response(200)    
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Authorization code received successfully. You can close this window.</body></html>")

    # Set up the callback server
    with socketserver.TCPServer(("", callback_port), SpotifyAuthHandler) as httpd:
        
        # Open the Spotify authorization URL in the default web browser
        webbrowser.open('{link}'.format(link=req.url), new=2)
        
        # Wait for a request and handle it
        httpd.handle_request()

    def get_token(code):

        payload = {
            'client_id': clientId,  
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirectUri,  
            'code_verifier': codeVerifier,
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        url = 'https://accounts.spotify.com/api/token'  

        response = requests.post(url, data=payload, headers=headers)
        response_json = response.json()

        access_token = response_json.get('access_token')
        if access_token:
            return access_token
            # Store the access token or use it as needed
        else:
            print("Failed to retrieve access token.")

    access_token = get_token(code)
    return access_token

access_token = authProcess()

# get request for currently playing track
def getCurrentTrack():
    
    headers = {
        'Authorization': 'Bearer {token}'.format(token = access_token),
    }

    track = requests.get('https://api.spotify.com/v1/me/player/currently-playing', headers=headers).json()
    return track

# get request for playback state
def getPlaybackState():
    headers = {
        'Authorization': 'Bearer {token}'.format(token = access_token),
    }

    playbackState = requests.get('https://api.spotify.com/v1/me/player', headers=headers).json()
    return playbackState

# instantiate lrcapi class
api = LrcLibAPI(user_agent="my-app/0.0.1")      

# get lyrics of track
def getLyrics(track):
    # get variables for lyrics
    track_name = track["item"]["name"]
    artist_name = track["item"]["artists"][0]["name"]
    album_name = track["item"]["album"]["name"]
    duration = math.floor(track["item"]["duration_ms"] / 1000)

    try:
        lyrics = api.get_lyrics(
            track_name,
            artist_name,
            album_name,
            duration
        )
    except:
        return None

    found_lyrics = lyrics.synced_lyrics
    return found_lyrics

# function to split lyrics
def splitLyrics(lyrics):   
    lst = lyrics.split("\n")
    lst = map(lambda a : a.split(" ", 1), lst)
    lst = [[sublist[0][1:-1], sublist[1]] for sublist in list(lst)]
    lst = [[(int(sublist[0].split(':')[0]) * 60) + float(sublist[0].split(':')[1]), sublist[1]] for sublist in list(lst)]
    return lst

# full function for thread
def updateResetFlag():
    global needsReset, hasResetted
    while True:
        playbackState = getPlaybackState()
        if playbackState["item"] is None:
            t.sleep(1)
            continue
        isPlaying = playbackState["is_playing"]
        currentTrack = playbackState["item"]["name"]
        if currentTrack != track and track is not None:
            needsReset = True
            hasResetted = False
        if needsReset:
            if isPlaying:
                needsReset = False
        else:
            if not isPlaying: 
                needsReset = True 
                hasResetted = False
        t.sleep(1)
        

# update lyrics on time interval
t1 = threading.Thread(target=updateResetFlag)

t1.start()

# start main tkinter program
# Create the root window
root = tk.Tk()
text_label = tk.Label(root)


def tkinterStart():

    def SaveLastClickPos(event):
        global lastClickX, lastClickY
        lastClickX = event.x
        lastClickY = event.y


    def Dragging(event):
        x, y = event.x - lastClickX + root.winfo_x(), event.y - lastClickY + root.winfo_y()
        root.geometry("+%s+%s" % (x , y))

    # Make the window transparent
    root.attributes('-alpha', 0.5) # Adjust the alpha value (0.0 to 1.0) for transparency

    # Remove window decorations (frame)
    root.overrideredirect(True)

    # Make the window stay on top of other applications
    root.attributes('-topmost', True)

    # waiting function that waits to call reset function
    def waitingFunction():
        global needsReset, hasResetted
        if not hasResetted and not needsReset:
            hasResetted = True
            initTkinter()
        else:
            root.after(200, waitingFunction)
        
    # self updating label to display appropriate lyrics
    def updateLyrics():
        global index, needsReset, lyrics, text_label
        index += 1
        timeDelay = 0
        if index < len(lyrics) - 1 and not needsReset and hasResetted: # if needsReset is false, carry on
            timeDelay = lyrics[index + 1][0] - lyrics[index][0]
        else:   # if needsReset is true or out of bounds
            waitingFunction()
            return
        timeDelay = int(timeDelay * 1000)
        displayLyrics = lyrics[index][1]
        text_label.config(text = displayLyrics) 
        root.after(timeDelay, updateLyrics) 

    # Create a label to display text
    def initTkinter():
        global index, text_label, lyrics, track
        index = 0
        tempTrack = getCurrentTrack()
        track = tempTrack["item"]["name"]
        lyricsObject = getLyrics(tempTrack)

        if lyricsObject is None:
            text_label.destroy() # destroy old label
            fontObj = tkFont.Font(size=28)
            text_label = tk.Label(root)
            text_label = tk.Label(root, text= "No lyrics available...", font=fontObj, bg='#000', fg='#fff')
            text_label.pack(fill=tk.BOTH, expand=True)
            root.after(3000, initTkinter)
        else:
            lyrics = splitLyrics(lyricsObject)
            playbackState = getPlaybackState()
            isPlaying = playbackState["is_playing"]
            currTime = 0

            if isPlaying:
                currTime = playbackState["progress_ms"] / 1000

            while currTime > lyrics[index][0] and index < len(lyrics):
                index += 1

            if index != 0 and index != len(lyrics) - 1:
                index -= 1

            displayLyrics = lyrics[index][1]
            timeDelay = int((lyrics[index + 1][0] - currTime) * 1000 - 50) # Offset lyrics 50ms
            fontObj = tkFont.Font(size=28)
            text_label.destroy() # destroy old label
            text_label = tk.Label(root)
            text_label = tk.Label(root, text= displayLyrics, font=fontObj, bg='#000', fg='#fff')
            text_label.pack(fill=tk.BOTH, expand=True)
            root.after(timeDelay, updateLyrics)

    initTkinter()

    # call draggable functions
    root.bind('<Button-1>', SaveLastClickPos)
    root.bind('<B1-Motion>', Dragging)

    # Start the Tkinter event loop
    root.mainloop()

tkinterStart()