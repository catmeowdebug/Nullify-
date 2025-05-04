import json

from flask import Flask, request, jsonify
import requests
import os
import logging
from dotenv import load_dotenv
from flask_cors import CORS
import lmstudio as lms
from ytmusicapi import YTMusic


# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# API credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "97debce860cb4f6caafe1e5f67b97a8b")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "35fa27bd5b0a48919ce00c1cd86675b5")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://nullify-jt6x.onrender.com/callback")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "894c8fa3285772930a82e00d410c5fd3")

# Initialize YouTube Music API
try:
    yt = YTMusic()
except Exception as e:
    logger.error(f"Failed to initialize YTMusic: {str(e)}")
    yt = None
from flask import send_file
import tempfile


@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    try:
        if not request.json or 'recommendations' not in request.json:
            return jsonify({"error": "Missing recommendations data"}), 400

        recommendations = request.json['recommendations']

        # Create a temporary M3U playlist file
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.m3u', delete=False) as temp_file:
            temp_file.write("#EXTM3U\n")
            for track in recommendations:
                if 'yt_link' in track:
                    temp_file.write(f"#EXTINF:-1,{track['artist']} - {track['track']}\n")
                    temp_file.write(f"{track['yt_link']}\n")

            temp_file_path = temp_file.name

        return jsonify({
            "playlist_url": f"/download_playlist?path={temp_file_path}",
            "message": "Playlist created successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download_playlist')
def download_playlist():
    try:
        file_path = request.args.get('path')
        return send_file(
            file_path,
            as_attachment=True,
            download_name='music_recommendations.m3u',
            mimetype='audio/x-mpegurl'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def health_check():
    return jsonify({"status": "healthy", "service": "music-recommendation-api"})


@app.route('/detect_emotion', methods=['POST'])
def detect_emotion():
    try:
        if not request.json or 'text' not in request.json:
            return jsonify({"error": "Missing text in request"}), 400

        text = request.json['text']
        logger.info(f"Detecting emotion for text: {text[:50]}...")

        model = lms.llm()
        chat = lms.Chat("You are an emotion detection expert. "
                        "Respond ONLY with: emotion: [label]")
        chat.add_user_message(
            f"Detect the sentiment emotions with around maximum of 5 labels in this text: \"{text}\"")

        response = model.respond(chat).content.strip()
        emotion = response.split(':')[-1].strip().lower()

        logger.info(f"Detected emotion: {emotion}")
        return jsonify({"emotion": emotion})

    except Exception as e:
        logger.error(f"Emotion detection error: {str(e)}")
        return jsonify({"error": "Failed to detect emotion", "detail": str(e)}), 500


@app.route('/get_spotify_token', methods=['POST'])
def get_spotify_token():
    try:
        if not request.json or 'auth_code' not in request.json:
            return jsonify({"error": "Missing auth_code in request"}), 400

        auth_code = request.json['auth_code']
        logger.info("Received request for Spotify token exchange")

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

        logger.debug(f"Sending request to Spotify with data: {data}")
        response = requests.post(token_url, data=data, headers=headers)

        if response.status_code != 200:
            error_detail = response.json().get('error_description', 'No error details')
            logger.error(f"Spotify API error: {response.status_code} - {error_detail}")
            return jsonify({
                "error": f"Spotify API error: {response.status_code}",
                "detail": error_detail
            }), response.status_code

        tokens = response.json()
        logger.info("Successfully obtained Spotify tokens")

        return jsonify({
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in")
        })

    except Exception as e:
        logger.error(f"Token exchange error: {str(e)}")
        return jsonify({
            "error": "Internal server error during token exchange",
            "detail": str(e)
        }), 500


@app.route('/get_user_data', methods=['POST'])
def get_user_data():
    try:
        if not request.json or 'access_token' not in request.json:
            return jsonify({"error": "Missing access_token in request"}), 400

        access_token = request.json['access_token']
        logger.info("Fetching Spotify user data")

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # Get user profile
        user_profile_url = "https://api.spotify.com/v1/me"
        response = requests.get(user_profile_url, headers=headers)

        if response.status_code != 200:
            error_detail = response.json().get('error', {}).get('message', 'Unknown error')
            logger.error(f"Spotify user profile error: {response.status_code} - {error_detail}")
            return jsonify({
                "error": f"Failed to get user profile: {response.status_code}",
                "detail": error_detail
            }), response.status_code

        profile_data = response.json()

        # Get top artists
        top_artists_url = "https://api.spotify.com/v1/me/top/artists?time_range=medium_term&limit=5"
        response = requests.get(top_artists_url, headers=headers)

        top_artists = []
        genres = set()

        if response.status_code == 200:
            top_artists = response.json().get("items", [])
            for artist in top_artists:
                genres.update(artist.get("genres", []))

        return jsonify({
            "user_id": profile_data.get("id"),
            "country": profile_data.get("country", "US"),
            "genres": list(genres),
            "top_artists": [artist["name"] for artist in top_artists]
        })

    except Exception as e:
        logger.error(f"User data error: {str(e)}")
        return jsonify({
            "error": "Failed to get user data",
            "detail": str(e)
        }), 500


@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    try:
        # Validate input
        if not request.json:
            return jsonify({"error": "Missing request body"}), 400

        if 'access_token' not in request.json:
            return jsonify({"error": "Missing access_token"}), 400

        if 'emotion' not in request.json:
            return jsonify({"error": "Missing emotion"}), 400

        access_token = request.json['access_token']
        emotion = request.json['emotion']

        logger.info(f"Starting recommendation process for emotion: {emotion}")

        # Step 1: Get user data
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get user profile
        profile_url = "https://api.spotify.com/v1/me"
        profile_response = requests.get(profile_url, headers=headers)

        if profile_response.status_code != 200:
            error = profile_response.json().get('error', {})
            return jsonify({
                "error": "Failed to get user profile",
                "detail": error.get('message', 'Unknown error')
            }), profile_response.status_code

        profile_data = profile_response.json()
        country = profile_data.get('country', 'US')

        # Get top artists
        artists_url = "https://api.spotify.com/v1/me/top/artists?time_range=medium_term&limit=5"
        artists_response = requests.get(artists_url, headers=headers)

        genres = set()
        if artists_response.status_code == 200:
            for artist in artists_response.json().get('items', []):
                genres.update(artist.get('genres', []))

        # Step 2: Generate emotion tags
        model = lms.llm()
        chat = lms.Chat("You are a music recommendation expert. "
                        "Respond ONLY with a comma-separated list of emotion-related tags.")
        prompt = f"""
        For the emotion "{emotion}", and considering these genres: {', '.join(genres)} 
        and country: {country}, generate 5 music tags.
        Respond ONLY with comma-separated tags.
        """
        chat.add_user_message(prompt)
        response = model.respond(chat).content.strip()
        tags = [tag.strip() for tag in response.split(",") if tag.strip()]

        if not tags:
            return jsonify({"error": "Failed to generate tags"}), 500

        # Step 3: Get recommendations from Last.fm
        base_url = "http://ws.audioscrobbler.com/2.0/"
        recommendations = []

        for tag in tags[:3]:  # Limit to 3 tags to avoid too many requests
            params = {
                "method": "tag.gettoptracks",
                "tag": tag,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": 5
            }
            response = requests.get(base_url, params=params)

            if response.status_code == 200:
                data = response.json()
                tracks = data.get('tracks', {}).get('track', [])
                for track in tracks:
                    recommendations.append({
                        "track": track.get('name'),
                        "artist": track.get('artist', {}).get('name'),
                        "tag": tag
                    })

        if not recommendations:
            return jsonify({"error": "No tracks found for these tags"}), 404

        # Step 4: Add YouTube links
        if yt:
            for track in recommendations[:10]:  # Limit to 10 to avoid timeout
                try:
                    results = yt.search(f"{track['track']} {track['artist']}")
                    for item in results:
                        if item["resultType"] == "video":
                            track["yt_link"] = f"https://music.youtube.com/watch?v={item['videoId']}"
                            break
                except Exception as e:
                    logger.warning(f"Couldn't get YT link for {track['track']}: {str(e)}")
                    continue

        return jsonify({
            "recommendations": recommendations,
            "emotion": emotion,
            "genres": list(genres),
            "country": country
        })

    except Exception as e:
        logger.error(f"Recommendation error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "detail": str(e)
        }), 500


@app.route('/process_feedback', methods=['POST'])
def process_feedback():
    """Process user feedback using LM Studio and update recommendations"""
    data = request.json

    # Initialize LM Studio model
    model = lms.llm()
    chat = lms.Chat("""
    You are a music recommendation assistant analyzing user feedback. 
    Respond with JSON containing: 
    - response: string (friendly reply)
    - mood_adjustment: string (more_energetic|more_calm|no_change)
    - new_tags: array (3-5 music tags based on feedback)
    """)

    # Build context for the model
    context = f"""
    Current mood: {data.get('current_mood')}
    Current track: {data.get('current_track')}
    User feedback: {data.get('feedback')}
    Previous tags: {data.get('current_tags')}
    """

    chat.add_user_message(f"""
    Analyze this music feedback and suggest adjustments:
    {context}
    """)

    try:
        # Get structured response from LM Studio
        result = model.respond(chat).content.strip()
        response_data = json.loads(result)

        # Generate new recommendations based on adjusted tags
        new_recommendations = get_recommendations_by_tags(
            response_data['new_tags'],
            data.get('access_token')
        )

        return jsonify({
            "success": True,
            "bot_response": response_data['response'],
            "mood_adjustment": response_data['mood_adjustment'],
            "recommendations": new_recommendations
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def get_recommendations_by_tags(tags, access_token):
    """Get recommendations based on specific tags"""
    recommendations = []

    # Get user preferences first
    user_data = get_user_data(access_token)

    for tag in tags:
        # Combine tag with user preferences
        search_query = f"{tag} {user_data['genres'][0]}"

        # Search Last.fm
        params = {
            "method": "tag.gettoptracks",
            "tag": search_query,
            "api_key": LASTFM_API_KEY,
            "limit": 3
        }
        response = requests.get("http://ws.audioscrobbler.com/2.0/", params=params)

        if response.status_code == 200:
            tracks = response.json().get('tracks', {}).get('track', [])
            for track in tracks:
                # Get YouTube link
                yt_link = None
                if yt:
                    results = yt.search(f"{track['name']} {track['artist']['name']}")
                    for item in results:
                        if item["resultType"] == "video":
                            yt_link = f"https://music.youtube.com/watch?v={item['videoId']}"
                            break

                recommendations.append({
                    "track": track['name'],
                    "artist": track['artist']['name'],
                    "tag": tag,
                    "yt_link": yt_link
                })

    return recommendations

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
