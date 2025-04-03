import os
import sys
import json
import requests
import subprocess
from dotenv import load_dotenv
import lmstudio as lms
from ytmusicapi import YTMusic
import streamlit as st

load_dotenv()

# Spotify API credentials
CLIENT_ID = "97debce860cb4f6caafe1e5f67b97a8b"
CLIENT_SECRET = "35fa27bd5b0a48919ce00c1cd86675b5"
REDIRECT_URI = "https://nullify-jt6x.onrender.com/callback"

# Last.fm API key
LASTFM_API_KEY = "894c8fa3285772930a82e00d410c5fd3"

# Initialize YouTube Music API
yt = YTMusic()

# Disable symlinks warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# 1. Emotion Detection
def detect_emotion(text):
    try:
        model = lms.llm()
        chat = lms.Chat("You are an emotion detection expert. "
                        "Respond ONLY with: emotion: [label]")
        chat.add_user_message(f"Detect the sentiment emotions with around maximum of 5 labels in this text: \"{text}\"")
        response = model.respond(chat).content.strip()
        emotion = response.split(':')[-1].strip().lower()
        return {"emotion": emotion}
    except Exception as e:
        st.error(f"Detection Error: {str(e)}")
        return {"emotion": "unknown"}

# 2. LM Studio Tag Generation
def generate_lastfm_tags_with_spotify(emotion, genres, country):
    try:
        model = lms.llm()
        chat = lms.Chat("You are a music recommendation expert. "
                        "Respond ONLY with a comma-separated list of emotion-related tags.")
        prompt = f"""
        For the emotion "{emotion}", and considering the user's favorite genres: {', '.join(genres)} 
        and country: {country}, generate a list of 5 related emotion tags. 
        The tags should reflect a combination of the user's emotional state, their preferred music genres, and cultural context.
        Example: If the emotion is "happy", genres are ["hindi pop", "bollywood"], and country is "IN", the tags could be: joyful, melodious, energetic, festive, soulful.
        """
        chat.add_user_message(prompt)
        response = model.respond(chat).content.strip()
        tags = [tag.strip() for tag in response.split(",") if tag.strip()]
        return tags if tags else []
    except Exception as e:
        st.error(f"Tag Generation Error: {str(e)}")
        return []

# 3. Last.fm Music Search
def search_lastfm(tags):
    try:
        base_url = "http://ws.audioscrobbler.com/2.0/"
        tracks = []

        for tag in tags:
            params = {
                "method": "tag.gettoptracks",
                "tag": tag,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": 5
            }
            response = requests.get(base_url, params=params)
            st.write(f"🔍 Debug: API response for tag '{tag}': {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if "tracks" in data and "track" in data["tracks"]:
                    for t in data["tracks"]["track"]:
                        tracks.append({
                            "track": t["name"],
                            "artist": t["artist"]["name"]
                        })
                else:
                    st.warning(f"No tracks found for tag: {tag}")
        return tracks
    except Exception as e:
        st.error(f"Last.fm Error: {str(e)}")
        return []

# 4. Fetch YouTube Music Links
def get_ytmusic_link(track, artist):
    try:
        results = yt.search(f"{track} {artist}")
        for item in results:
            if item["resultType"] == "video":
                return f"https://music.youtube.com/watch?v={item['videoId']}"
        return None
    except Exception as e:
        st.error(f"YouTube Music Error: {str(e)}")
        return None

# 5. Generate M3U Playlist
def create_m3u_playlist(tracks, filename="playlist.m3u"):
    try:
        with open(filename, "w", encoding="utf-8") as file:
            file.write("#EXTM3U\n")
            for track in tracks:
                yt_link = get_ytmusic_link(track["track"], track["artist"])
                if yt_link:
                    file.write(f"#EXTINF:-1,{track['artist']} - {track['track']}\n")
                    file.write(f"{yt_link}\n")
        st.success(f"✅ Playlist saved as {filename}")
        return True
    except Exception as e:
        st.error(f"M3U Error: {str(e)}")
        return False

# 6. Play in SMPlayer
def play_playlist_in_smplayer(filename="playlist.m3u"):
    try:
        smplayer_path = r"C:\Program Files\SMPlayer\smplayer.exe"  # Update this path if needed
        subprocess.run([smplayer_path, filename], check=True)
        st.success("🎵 Now playing in SMPlayer...")
    except Exception as e:
        st.error(f"SMPlayer Error: {str(e)}")

# Spotify Integration
def get_spotify_access_token(auth_code):
    try:
        token_url = "https://accounts.spotify.com/api/token"
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        tokens = response.json()
        return tokens.get("access_token"), tokens.get("refresh_token")
    except Exception as e:
        st.error(f"Spotify Token Error: {str(e)}")
        return None, None

def get_spotify_user_data(access_token):
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        # Get user's top artists
        top_artists_url = "https://api.spotify.com/v1/me/top/artists?time_range=medium_term&limit=5"
        response = requests.get(top_artists_url, headers=headers)
        response.raise_for_status()
        top_artists = response.json().get("items", [])

        # Extract genres from top artists
        genres = set()
        for artist in top_artists:
            genres.update(artist.get("genres", []))

        # Get user's country
        user_profile_url = "https://api.spotify.com/v1/me"
        response = requests.get(user_profile_url, headers=headers)
        response.raise_for_status()
        country = response.json().get("country", "US")

        return {
            "genres": list(genres),
            "country": country
        }
    except Exception as e:
        st.error(f"Spotify API Error: {str(e)}")
        return {
            "genres": [],
            "country": "US"
        }

# Streamlit UI
def main():
    st.title("🎵 MoodTunes - Music for Your Emotions 🎵")

    # User input
    mood_text = st.text_area("How are you feeling today?", "I feel happy and energetic!")

    if st.button("Analyze My Mood"):
        with st.spinner("Detecting emotion..."):
            emotion_result = detect_emotion(mood_text)
            detected_emotion = emotion_result['emotion']
            st.success(f"Detected Emotion: **{detected_emotion}**")

        # Spotify Authentication
        st.subheader("Spotify Connection")
        auth_code = st.text_input("Enter your Spotify auth code (get it from the URL after authorization):")

        if auth_code:
            with st.spinner("Connecting to Spotify..."):
                access_token, refresh_token = get_spotify_access_token(auth_code)
                if access_token:
                    st.success("Successfully connected to Spotify!")

                    # Get user data
                    with st.spinner("Fetching your Spotify data..."):
                        spotify_user_data = get_spotify_user_data(access_token)
                        st.write(f"Your favorite genres: {', '.join(spotify_user_data['genres']) if spotify_user_data['genres'] else 'None'}")
                        st.write(f"Your country: {spotify_user_data['country']}")

                    # Generate tags
                    with st.spinner("Generating music tags..."):
                        tags = generate_lastfm_tags_with_spotify(
                            detected_emotion,
                            spotify_user_data["genres"],
                            spotify_user_data["country"]
                        )
                        st.write("Recommended Tags:", ", ".join(tags))

                    # Get recommendations
                    with st.spinner("Finding perfect tracks for you..."):
                        recommendations = search_lastfm(tags)
                        if recommendations:
                            st.subheader("🎶 Recommended Tracks:")
                            for track in recommendations:
                                st.write(f"- **{track['track']}** by {track['artist']}")

                            # Playlist actions
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Create Playlist"):
                                    if create_m3u_playlist(recommendations):
                                        st.balloons()
                            with col2:
                                if st.button("Play in SMPlayer"):
                                    play_playlist_in_smplayer()
                        else:
                            st.warning("No tracks found. Try different mood words.")
                else:
                    st.error("Failed to connect to Spotify. Please check your auth code.")

if __name__ == "__main__":
    main()
