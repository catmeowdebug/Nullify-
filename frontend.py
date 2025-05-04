import streamlit as st
import requests
import os
from dotenv import load_dotenv
import streamlit.components.v1 as components

load_dotenv()

# Backend URL
BACKEND_URL = "http://localhost:5000"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm your music recommendation assistant. How are you feeling today?"}
    ]


if "current_state" not in st.session_state:
    st.session_state.current_state = "waiting_for_mood"

if "detected_emotion" not in st.session_state:
    st.session_state.detected_emotion = None

if "recommendations" not in st.session_state:
    st.session_state.recommendations = []

if "spotify_authenticated" not in st.session_state:
    st.session_state.spotify_authenticated = False

if "spotify_token" not in st.session_state:
    st.session_state.spotify_token = None

if "current_track_index" not in st.session_state:
    st.session_state.current_track_index = 0

if "player_created" not in st.session_state:
    st.session_state.player_created = False


# Custom CSS for the player
def inject_custom_css():
    st.markdown("""
    <style>
        .track-item {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .track-item:hover {
            background-color: #f0f0f0;
        }
        .track-item.playing {
            background-color: #e3f2fd;
            font-weight: bold;
        }
        .player-container {
            margin-top: 20px;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 15px;
            background-color: #f9f9f9;
        }
        .player-controls {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
    </style>
    """, unsafe_allow_html=True)


# Create the music player component
def create_music_player(tracks):
    # Filter tracks with YouTube links
    yt_tracks = [track for track in tracks if 'yt_link' in track]

    if not yt_tracks:
        return "<div>No playable tracks found</div>"

    # Generate HTML/JS for the player
    player_html = f"""
    <div class="player-container">
        <h3>🎵 Music Player</h3>
        <div id="now-playing">Now Playing: {yt_tracks[0]['artist']} - {yt_tracks[0]['track']}</div>
        <iframe id="yt-player" width="100%" height="200" src="https://www.youtube.com/embed/{yt_tracks[0]['yt_link'].split('=')[-1]}?enablejsapi=1&autoplay=1" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

        <div class="player-controls">
            <button onclick="playPrevious()">⏮ Previous</button>
            <button onclick="togglePlay()">⏯ Play/Pause</button>
            <button onclick="playNext()">⏭ Next</button>
        </div>

        <div style="max-height: 300px; overflow-y: auto; margin-top: 15px;">
            <h4>Playlist</h4>
            {"".join([f"""
            <div class="track-item {'playing' if i == 0 else ''}" 
                 onclick="playTrack({i})" 
                 id="track-{i}">
                {track['artist']} - {track['track']}
            </div>
            """ for i, track in enumerate(yt_tracks)])}
        </div>
    </div>

    <script>
        var tracks = {[{'id': track['yt_link'].split('=')[-1], 'title': f"{track['artist']} - {track['track']}"} for track in yt_tracks]};
        var currentTrackIndex = 0;
        var player;

        // Inject YouTube API script
        var tag = document.createElement('script');
        tag.src = "https://www.youtube.com/iframe_api";
        var firstScriptTag = document.getElementsByTagName('script')[0];
        firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

        function onYouTubeIframeAPIReady() {{
            player = new YT.Player('yt-player', {{
                events: {{
                    'onReady': onPlayerReady,
                    'onStateChange': onPlayerStateChange
                }}
            }});
        }}

        function onPlayerReady(event) {{
            event.target.playVideo();
        }}

        function onPlayerStateChange(event) {{
            if (event.data == YT.PlayerState.ENDED) {{
                playNext();
            }}
        }}

        function playTrack(index) {{
            currentTrackIndex = index;
            player.loadVideoById(tracks[index].id);
            document.getElementById('now-playing').innerText = "Now Playing: " + tracks[index].title;
            updateTrackDisplay();
        }}

        function playNext() {{
            currentTrackIndex = (currentTrackIndex + 1) % tracks.length;
            playTrack(currentTrackIndex);
        }}

        function playPrevious() {{
            currentTrackIndex = (currentTrackIndex - 1 + tracks.length) % tracks.length;
            playTrack(currentTrackIndex);
        }}

        function togglePlay() {{
            if (player.getPlayerState() == YT.PlayerState.PLAYING) {{
                player.pauseVideo();
            }} else {{
                player.playVideo();
            }}
        }}

        function updateTrackDisplay() {{
            document.querySelectorAll('.track-item').forEach((item, index) => {{
                if (index == currentTrackIndex) {{
                    item.classList.add('playing');
                }} else {{
                    item.classList.remove('playing');
                }}
            }});
        }}
    </script>
    """
    return player_html


# Page config
st.set_page_config(page_title="Music Recommendation Chatbot", page_icon="🎵")

# Inject custom CSS
inject_custom_css()

# Sidebar with Spotify auth link (only show if not authenticated)
with st.sidebar:
    if not st.session_state.spotify_authenticated:
        st.header("Spotify Authentication")
        st.markdown(
            f"""
            To get personalized recommendations, authenticate with Spotify:

            [Authorize with Spotify](https://accounts.spotify.com/authorize?client_id=97debce860cb4f6caafe1e5f67b97a8b&response_type=code&redirect_uri=https%3A//nullify-jt6x.onrender.com/callback&scope=user-read-private%20user-read-email%20user-top-read%20user-read-recently-played%20user-library-read%20playlist-read-private%20user-follow-read)
            """
        )
        st.write("After authenticating, paste your auth code in the chat.")
    else:
        st.success("✅ Spotify Connected")
        if st.button("Disconnect Spotify"):
            st.session_state.spotify_authenticated = False
            st.session_state.spotify_token = None
            st.session_state.messages.append(
                {"role": "assistant", "content": "Spotify disconnected. You can reconnect anytime."})
            st.rerun()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Display music player if we have recommendations
if st.session_state.recommendations and any('yt_link' in track for track in st.session_state.recommendations):
    st.markdown("### Your Personal Playlist")
    components.html(
        create_music_player(st.session_state.recommendations),
        height=500
    )

# Chat input
if prompt := st.chat_input("How are you feeling today?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process user input based on current state
    if st.session_state.current_state == "waiting_for_mood":
        # Analyze mood
        with st.chat_message("assistant"):
            st.markdown("Analyzing your mood...")
            st.session_state.messages.append({"role": "assistant", "content": "Analyzing your mood..."})

            try:
                response = requests.post(
                    f"{BACKEND_URL}/detect_emotion",
                    json={"text": prompt}
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise Exception(result["error"])

                st.session_state.detected_emotion = result["emotion"]
                message = f"I sense you're feeling {st.session_state.detected_emotion}."
                st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})

                if st.session_state.spotify_authenticated:
                    message = "Would you like me to generate music recommendations based on your mood? (yes/no)"
                    st.markdown(message)
                    st.session_state.messages.append({"role": "assistant", "content": message})
                    st.session_state.current_state = "ready_for_recommendations"
                else:
                    message = "To give you personalized recommendations, I'll need your Spotify authorization code."
                    st.markdown(message)
                    st.session_state.messages.append({"role": "assistant", "content": message})
                    message = "Please visit the link in the sidebar to authenticate with Spotify, then paste your auth code here."
                    st.markdown(message)
                    st.session_state.messages.append({"role": "assistant", "content": message})
                    st.session_state.current_state = "waiting_for_spotify"

            except Exception as e:
                message = f"Oops! Something went wrong: {str(e)}"
                st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})
                st.session_state.current_state = "waiting_for_mood"

    elif st.session_state.current_state == "waiting_for_spotify":
        # Process Spotify auth code
        with st.chat_message("assistant"):
            st.markdown("Connecting to Spotify...")
            st.session_state.messages.append({"role": "assistant", "content": "Connecting to Spotify..."})

            try:
                response = requests.post(
                    f"{BACKEND_URL}/get_spotify_token",
                    json={"auth_code": prompt}
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise Exception(result["error"])

                if not result.get("access_token"):
                    raise Exception("Failed to get access token from Spotify")

                st.session_state.spotify_token = result["access_token"]
                st.session_state.spotify_authenticated = True

                message = "Successfully connected to Spotify! This connection will be remembered."
                st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})

                message = "Would you like me to generate music recommendations based on your mood? (yes/no)"
                st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})

                st.session_state.current_state = "ready_for_recommendations"
                st.rerun()

            except Exception as e:
                message = f"Oops! Something went wrong: {str(e)}"
                st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})
                st.session_state.current_state = "waiting_for_mood"

    elif st.session_state.current_state == "ready_for_recommendations":
        if prompt.lower() in ["yes", "y", "sure"]:
            with st.chat_message("assistant"):
                st.markdown("Generating personalized recommendations...")
                st.session_state.messages.append(
                    {"role": "assistant", "content": "Generating personalized recommendations..."})

                try:
                    response = requests.post(
                        f"{BACKEND_URL}/get_recommendations",
                        json={
                            "access_token": st.session_state.spotify_token,
                            "emotion": st.session_state.detected_emotion
                        }
                    )

                    if response.status_code != 200:
                        raise Exception(response.json().get('detail', 'Failed to get recommendations'))

                    result = response.json()

                    if "error" in result:
                        raise Exception(result["error"])

                    st.session_state.recommendations = result["recommendations"]
                    st.session_state.current_track_index = 0
                    st.session_state.player_created = True

                    message = "Here's your personalized playlist based on your mood:"
                    st.markdown(message)
                    st.session_state.messages.append({"role": "assistant", "content": message})

                    message = "How are you feeling now?"
                    st.markdown(message)
                    st.session_state.messages.append({"role": "assistant", "content": message})

                    st.session_state.current_state = "waiting_for_mood"
                    st.rerun()  # Refresh to show the player

                except Exception as e:
                    message = f"Oops! Something went wrong: {str(e)}"
                    st.markdown(message)
                    st.session_state.messages.append({"role": "assistant", "content": message})
                    st.session_state.current_state = "waiting_for_mood"
        else:
            with st.chat_message("assistant"):
                message = "Okay, let me know if you change your mind!"
                st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})

                message = "How are you feeling now?"
                st.markdown(message)
                st.session_state.messages.append({"role": "assistant", "content": message})

                st.session_state.current_state = "waiting_for_mood"
