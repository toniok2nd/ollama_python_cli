from mcp.server.fastmcp import FastMCP
import json
import os
import subprocess
import tempfile
import sys
from typing import Optional

# Initialize FastMCP Server
mcp = FastMCP("openshot-server")

# In-memory project state
project_state = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "files": [], # List of media files
    "clips": [], # List of clips on the timeline
    "tracks": 5  # Typical number of tracks
}

def create_osp_json():
    """Generate the OpenShot Project (.osp) JSON structure."""
    # This is a simplified version of a valid .osp file
    osp = {
        "version": {
            "openshot-qt": "3.1.1",
            "libopenshot": "0.3.2"
        },
        "width": project_state["width"],
        "height": project_state["height"],
        "fps": {
            "num": project_state["fps"],
            "den": 1
        },
        "files": [],
        "clips": [],
        "effects": []
    }
    
    # Map project files
    for i, file_path in enumerate(project_state["files"]):
        file_obj = {
            "id": f"F{i}",
            "path": file_path,
            "name": os.path.basename(file_path),
            "media_type": "video" # Simplified
        }
        osp["files"].append(file_obj)
        
    # Map clips
    for i, clip in enumerate(project_state["clips"]):
        clip_obj = {
            "id": f"C{i}",
            "file_id": f"F{project_state['files'].index(clip['path'])}",
            "position": clip["position"], # Start time on timeline
            "start": clip.get("start", 0), # Start time within source file
            "end": clip.get("start", 0) + clip["duration"],
            "layer": clip.get("track", 1)
        }
        osp["clips"].append(clip_obj)
        
    return osp

@mcp.tool()
def new_video_project(width: int = 1920, height: int = 1080, fps: int = 30) -> str:
    """
    Start a new video project, clearing any previous state.
    
    Args:
        width: Video width (default 1920).
        height: Video height (default 1080).
        fps: Frames per second (default 30).
    """
    project_state["files"] = []
    project_state["clips"] = []
    project_state["width"] = width
    project_state["height"] = height
    project_state["fps"] = fps
    return "Started a new video project."

@mcp.tool()
def add_video_clip(file_path: str, position: float = 0, duration: float = 5, track: int = 1) -> str:
    """
    Add a video or image file to the timeline.
    
    Args:
        file_path: Absolute path to the media file.
        position: Start time on the timeline in seconds (default 0).
        duration: Duration of the clip in seconds (default 5).
        track: Track/Layer number (1-5) (default 1).
    """
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"
    
    if file_path not in project_state["files"]:
        project_state["files"].append(file_path)
        
    project_state["clips"].append({
        "path": file_path,
        "position": position,
        "duration": duration,
        "track": track
    })
    return f"Added clip: {os.path.basename(file_path)} at {position}s"

@mcp.tool()
def save_openshot_project(output_path: str = "project.osp") -> str:
    """
    Save the current project to an OpenShot .osp file.
    
    Args:
        output_path: Path to save the .osp file (default 'project.osp').
    """
    try:
        osp_data = create_osp_json()
        with open(output_path, 'w') as f:
            json.dump(osp_data, f, indent=4)
        return f"OpenShot project saved to {output_path}"
    except Exception as e:
        return f"Error saving project: {e}"

@mcp.tool()
def quick_render_ffmpeg(output_path: str = "output.mp4") -> str:
    """
    Quickly concatenate the current clips into a single MP4 video using ffmpeg.
    
    Args:
        output_path: Path to save the rendered video (default 'output.mp4').
    """
    if not project_state["clips"]:
        return "Error: No clips added to project."
    
    try:
        # Create a concat file for ffmpeg
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            # ffmpeg concat only works well with same codecs/resolutions
            # For a true "quick render", we just append them.
            for clip in sorted(project_state["clips"], key=lambda x: x["position"]):
                # Note: ffmpeg 'concat' demuxer requires 'file' directive
                f.write(f"file '{clip['path']}'\n")
            concat_file = f.name
        
        # Run ffmpeg
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path]
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(concat_file)
        
        if process.returncode == 0:
            return f"Quick render successful! Video saved to {output_path}"
        else:
            # If copy fails (incompatible formats), try re-encoding (slower but safer)
            print("Fast concat failed, attempting re-encode...", file=sys.stderr)
            cmd_slow = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, output_path]
            process_slow = subprocess.run(cmd_slow, capture_output=True, text=True)
            if process_slow.returncode == 0:
                return f"Quick render (re-encoded) successful! Video saved to {output_path}"
            return f"FFmpeg Error: {process.stderr}\n{process_slow.stderr}"
            
    except Exception as e:
        return f"Error during render: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
