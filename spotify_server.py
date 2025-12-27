from mcp.server.fastmcp import FastMCP
import os
import json
from typing import Dict, Optional
from pathlib import Path

# Check for spotipy
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    spotipy = None

# Initialize FastMCP Server
mcp = FastMCP("spotify-server")

def get_config() -> Dict[str, str]:
    """Helper to get configuration from environment or settings.json."""
    config = {
        "client_id": os.environ.get("SPOTIPY_CLIENT_ID", ""),
        "client_secret": os.environ.get("SPOTIPY_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
    }

    # Try loading from settings.json if environment variables are missing
    settings_path = Path(__file__).parent / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                if not config["client_id"]: config["client_id"] = settings.get("SPOTIPY_CLIENT_ID", "")
                if not config["client_secret"]: config["client_secret"] = settings.get("SPOTIPY_CLIENT_SECRET", "")
                if "SPOTIPY_REDIRECT_URI" in settings: config["redirect_uri"] = settings["SPOTIPY_REDIRECT_URI"]
        except Exception:
            pass
    return config

def get_spotify_client():
    if spotipy is None:
        raise Exception("spotipy library not installed")
    
    config = get_config()
    if not config["client_id"] or not config["client_secret"]:
        raise Exception("Spotify credentials missing in settings.json. Run /config-spotify in the CLI.")

    scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-modify-public playlist-modify-private"
    
    # Use a custom cache path to avoid permission issues in some environments
    cache_path = Path(__file__).parent / ".spotify_cache"
    
    auth_manager = SpotifyOAuth(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        scope=scope,
        cache_path=str(cache_path),
        open_browser=False # NEVER open browser in background server
    )
    
    # Explicitly check for token to avoid hanging on a hidden prompt
    token_info = auth_manager.get_cached_token()
    if not token_info:
        auth_url = auth_manager.get_authorize_url()
        raise Exception(f"Authentication required. Please visit this URL to authorize, then run /config-spotify and paste the result: {auth_url}")
        
    return spotipy.Spotify(auth_manager=auth_manager)

def handle_spotify_error(e: Exception) -> str:
    """Helper to format Spotify errors."""
    if "re-authenticate" in str(e) or "http" in str(e):
        return f"Authentication required. Please check terminal for OAuth flow or ensure credentials are correct. Error: {e}"
    return f"Spotify Error: {e}"

@mcp.tool()
def spotify_get_current_track() -> str:
    """Get information about the track currently playing on Spotify."""
    try:
        sp = get_spotify_client()
        current = sp.current_playback()
        if not current or not current.get("item"):
            return "No track currently playing."
        
        track = current["item"]
        artist = ", ".join([a["name"] for a in track["artists"]])
        return f"Playing: {track['name']} by {artist}\nAlbum: {track['album']['name']}\nProgress: {current['progress_ms'] // 1000}s / {track['duration_ms'] // 1000}s"
    except Exception as e:
        return handle_spotify_error(e)

@mcp.tool()
def spotify_search(query: str, type: str = "track") -> str:
    """
    Search for tracks, artists, albums, or playlists on Spotify.
    
    Args:
        query: Search term.
        type: Type: track, artist, album, or playlist (default 'track').
    """
    try:
        sp = get_spotify_client()
        results = sp.search(q=query, type=type, limit=5)
        
        output = f"Search results for '{query}' ({type}):\n"
        if type == "track":
            for item in results['tracks']['items']:
                artists = ", ".join([a['name'] for a in item['artists']])
                output += f"- {item['name']} by {artists} (URI: {item['uri']})\n"
        elif type == "artist":
            for item in results['artists']['items']:
                output += f"- {item['name']} (URI: {item['uri']})\n"
        return output
    except Exception as e:
        return handle_spotify_error(e)

@mcp.tool()
def spotify_play(uri: Optional[str] = None) -> str:
    """
    Play a track, album, or playlist by URI, or resume playback.
    
    Args:
        uri: Spotify URI (e.g. spotify:track:...) to play. Leave empty to resume.
    """
    try:
        sp = get_spotify_client()
        if uri:
            sp.start_playback(uris=[uri] if "track" in uri else None, context_uri=uri if "track" not in uri else None)
            return f"Started playing: {uri}"
        else:
            sp.start_playback()
            return "Playback resumed."
    except Exception as e:
        return handle_spotify_error(e)

@mcp.tool()
def spotify_pause() -> str:
    """Pause Spotify playback."""
    try:
        sp = get_spotify_client()
        sp.pause_playback()
        return "Playback paused."
    except Exception as e:
        return handle_spotify_error(e)

@mcp.tool()
def spotify_next() -> str:
    """Skip to the next track on Spotify."""
    try:
        sp = get_spotify_client()
        sp.next_track()
        return "Skipped to next track."
    except Exception as e:
        return handle_spotify_error(e)

@mcp.tool()
def spotify_previous() -> str:
    """Skip to the previous track on Spotify."""
    try:
        sp = get_spotify_client()
        sp.previous_track()
        return "Skipped to previous track."
    except Exception as e:
        return handle_spotify_error(e)

@mcp.tool()
def spotify_set_volume(volume_percent: int) -> str:
    """
    Set the volume for Spotify playback.
    
    Args:
        volume_percent: Volume percentage (0-100).
    """
    try:
        sp = get_spotify_client()
        sp.volume(volume_percent)
        return f"Volume set to {volume_percent}%."
    except Exception as e:
        return handle_spotify_error(e)

if __name__ == "__main__":
    mcp.run(transport='stdio')
