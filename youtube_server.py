from mcp.server.fastmcp import FastMCP
import re

# Optional dependencies handled gracefully
try:
    from youtubesearchpython import VideosSearch, Video
except ImportError:
    VideosSearch = None
    Video = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

# Initialize FastMCP Server
mcp = FastMCP("youtube-mcp-server")

def extract_video_id(url_or_id: str) -> str:
    """Helper to extract video ID from various URL formats."""
    if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    # Simple regex for common YT URL formats
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'be\/([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id

@mcp.tool()
def search_youtube(query: str, limit: int = 5) -> str:
    """
    Search for YouTube videos by query. Returns titles, links, and snippets.
    
    Args:
        query: Search terms.
        limit: Max results to return (default 5).
    """
    if not VideosSearch:
        return "Error: youtube-search-python not installed. Please install the 'Full' tier."
    
    try:
        search = VideosSearch(query, limit=limit)
        result = search.result()
        
        output = []
        for v in result.get('result', []):
            output.append(f"Title: {v['title']}\nURL: {v['link']}\nDuration: {v['duration']}\nDescription: {v.get('accessibility', {}).get('title', 'N/A')}\n---")
        
        return "\n".join(output) if output else "No results found."
    except Exception as e:
        return f"Error performing search: {e}"

@mcp.tool()
def get_youtube_transcript(video_id_or_url: str) -> str:
    """
    Get the transcript/subtitles for a YouTube video URL or ID.
    
    Args:
        video_id_or_url: YouTube video URL or Video ID.
    """
    if not YouTubeTranscriptApi:
        return "Error: youtube-transcript-api not installed. Please install the 'Full' tier."
    
    video_id = extract_video_id(video_id_or_url)
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([t['text'] for t in transcript_list])
        return full_text
    except Exception as e:
        return f"Error fetching transcript: {e}"

@mcp.tool()
def get_youtube_info(video_id_or_url: str) -> str:
    """
    Get detailed metadata for a YouTube video (title, views, description).
    
    Args:
        video_id_or_url: YouTube video URL or Video ID.
    """
    if not Video:
        return "Error: youtube-search-python not installed. Please install the 'Full' tier."
    
    video_id = extract_video_id(video_id_or_url)
    try:
        v_info = Video.getInfo(f"https://www.youtube.com/watch?v={video_id}")
        info_text = (
            f"Title: {v_info.get('title')}\n"
            f"Author: {v_info.get('author', {}).get('name')}\n"
            f"Views: {v_info.get('viewCount', {}).get('text')}\n"
            f"Date: {v_info.get('publishDate')}\n"
            f"Description: {v_info.get('description')[:500]}..."
        )
        return info_text
    except Exception as e:
        return f"Error getting info: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
