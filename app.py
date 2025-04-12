import os
import sys
import json
import requests
import subprocess  # To open SMPlayer
from dotenv import load_dotenv
import lmstudio as lms
from ytmusicapi import YTMusic

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

print("Debug: Script started")
print("https://nullify-jt6x.onrender.com/callback?code=AQBnfz3TLqhwfVv5gBLK0qQ4H0CRWriSb_w1PKxTNApdlDq2YVix9OyvOKPFRMXfiXPmjleXsweJi-_Ia3UcdyPfS6NHJeXkYFLsGubG5y8QA1k8eBjagTiEBbM0WSF0LF0NS7qiY4qUb0IZq4My6ye3dMbVK1IPCojkpHFnwVwsusKvI_CbG4u_HV82_0bWI_BDA28jvxL31aS6tLaoOIRStx7PWaGamC-E4QKeE52SLmFAWNq0vLuH11OyQ0jDJ3hQhZda9wi4siuGmTOggjhkU3EtdrTvU3pnxLPQCUAxgzLPYXG6AbXFtv8Z6UYYYE_X0tur-ZlzX6a4fMi3dRyZD33mLiMR4lM1ftWMSKsD7p8OQ-n3dw")
# 1. Emotion Detection
def detect_emotion(text):
    try:
        model = lms.llm()
        chat = lms.Chat("You are an emotion detection expert. "
                        "Respond ONLY with: emotion: [label]")
        chat.add_user_message(f"Detect the sentiment emotions wiht around maximum of 5 labels  in this text : \"{text}\"")
        response = model.respond(chat).content.strip()
        emotion = response.split(':')[-1].strip().lower()
        return {"emotion": emotion}
    except Exception as e:
        print(f"Detection Error: {str(e)}")
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
        print(f"Tag Generation Error: {str(e)}")
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
            print(f"\n🔍 Debug: API response for tag '{tag}': {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if "tracks" in data and "track" in data["tracks"]:
                    for t in data["tracks"]["track"]:
                        tracks.append({
                            "track": t["name"],
                            "artist": t["artist"]["name"]
                        })
                else:
                    print(f"⚠ No tracks found for tag: {tag}")
        return tracks
    except Exception as e:
        print(f"Last.fm Error: {str(e)}")
        return []

# 4. Fetch YouTube Music Links
def get_ytmusic_link(track, artist):
    results = yt.search(f"{track} {artist}")
    for item in results:
        if item["resultType"] == "video":
            return f"https://music.youtube.com/watch?v={item['videoId']}"
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
        print(f"✅ Playlist saved as {filename}")
    except Exception as e:
        print(f"M3U Error: {str(e)}")

# 6. Play in SMPlayer
def play_playlist_in_smplayer(filename="playlist.m3u"):
    try:
        choice = input("Do you want to play the playlist now in SMPlayer? (yes/no): ").strip().lower()
        if choice == "yes":
            smplayer_path = r"C:\Program Files\SMPlayer\smplayer.exe"  # Update this path if needed
            subprocess.run([smplayer_path, filename], check=True)
            print("🎵 Now playing in SMPlayer...")
        else:
            print("Okay, you can play it later.")
    except Exception as e:
        print(f"SMPlayer Error: {str(e)}")

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

        # Debugging: Print the response details
        print("Response Status Code:", response.status_code)
        print("Response Body:", response.text)

        response.raise_for_status()  # Raise an error for bad status codes
        tokens = response.json()
        return tokens.get("access_token"), tokens.get("refresh_token")
    except Exception as e:
        print(f"Spotify Token Error: {str(e)}")
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
        country = response.json().get("country", "US")  # Default to US if not found

        return {
            "genres": list(genres),
            "country": country
        }
    except Exception as e:
        print(f"Spotify API Error: {str(e)}")
        return {
            "genres": [],
            "country": "US"
        }

# Main Workflow
if __name__ == "__main__":
    print("Debug: Starting main workflow")
    try:
        user_text = input("Describe your mood: ").strip()
        if not user_text:
            print("Error: Empty input")
            sys.exit(1)

        # Step 1: Emotion Detection
        emotion_result = detect_emotion(user_text)
        detected_emotion = emotion_result['emotion']
        print(f"\nDetected emotion: {detected_emotion}")

        # Step 2: Get Spotify Access Token
        auth_code = input("Paste your Spotify auth code here: ")
        access_token, refresh_token = get_spotify_access_token(auth_code)
        if not access_token:
            print("Error: Failed to get Spotify access token")
            sys.exit(1)

        # Step 3: Fetch Spotify User Data
        spotify_user_data = get_spotify_user_data(access_token)
        print("Spotify User Data:", spotify_user_data)

        # Step 4: Generate Tags with Spotify Data
        tags = generate_lastfm_tags_with_spotify(detected_emotion, spotify_user_data["genres"], spotify_user_data["country"])
        print(f"\nRecommended tags with Spotify data: {', '.join(tags) if tags else 'None'}")

        # Step 5: Music Search
        if tags:
            recommendations = search_lastfm(tags)
            print("\n🎵 Music Recommendations:")
            if recommendations:
                for track in recommendations:
                    print(f"- {track['track']} by {track['artist']}")
            else:
                print("No recommendations found.")

            # Step 6: Create Playlist
            create_m3u_playlist(recommendations)

            # Step 7: Ask to Play in SMPlayer
            play_playlist_in_smplayer()
        else:
            print("No valid tags generated")

    except KeyboardInterrupt:
        print("\nProcess interrupted")
    except Exception as e:
        print(f"Critical error: {str(e)}")
