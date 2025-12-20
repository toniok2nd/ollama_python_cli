import asyncio
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional
from mcp.server.stdio import stdio_server
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

# Initialize MCP Server
server = Server("openshot-server")

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

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available video editing tools."""
    return [
        Tool(
            name="new_video_project",
            description="Start a new video project, clearing any previous state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "width": {"type": "integer", "default": 1920},
                    "height": {"type": "integer", "default": 1080},
                    "fps": {"type": "integer", "default": 30}
                }
            },
        ),
        Tool(
            name="add_video_clip",
            description="Add a video or image file to the timeline.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the media file."},
                    "position": {"type": "number", "description": "Start time on the timeline (seconds).", "default": 0},
                    "duration": {"type": "number", "description": "Duration of the clip (seconds).", "default": 5},
                    "track": {"type": "integer", "description": "Track/Layer number (1-5).", "default": 1}
                },
                "required": ["file_path"]
            },
        ),
        Tool(
            name="save_openshot_project",
            description="Save the current project to an OpenShot .osp file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {"type": "string", "description": "Path to save the .osp file.", "default": "project.osp"}
                }
            },
        ),
        Tool(
            name="quick_render_ffmpeg",
            description="Quickly concatenate the current clips into a single MP4 video using ffmpeg.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {"type": "string", "description": "Path to save the rendered video.", "default": "output.mp4"}
                }
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any] | None
) -> CallToolResult:
    """Handle video tool calls."""
    if name == "new_video_project":
        project_state["files"] = []
        project_state["clips"] = []
        project_state["width"] = (arguments or {}).get("width", 1920)
        project_state["height"] = (arguments or {}).get("height", 1080)
        project_state["fps"] = (arguments or {}).get("fps", 30)
        return CallToolResult(content=[TextContent(type="text", text="Started a new video project.")])

    elif name == "add_video_clip":
        file_path = arguments.get("file_path")
        if not os.path.exists(file_path):
            return CallToolResult(content=[TextContent(type="text", text=f"Error: File not found: {file_path}")], isError=True)
        
        if file_path not in project_state["files"]:
            project_state["files"].append(file_path)
            
        project_state["clips"].append({
            "path": file_path,
            "position": arguments.get("position", 0),
            "duration": arguments.get("duration", 5),
            "track": arguments.get("track", 1)
        })
        return CallToolResult(content=[TextContent(type="text", text=f"Added clip: {os.path.basename(file_path)} at {arguments.get('position', 0)}s")])

    elif name == "save_openshot_project":
        output_path = (arguments or {}).get("output_path", "project.osp")
        try:
            osp_data = create_osp_json()
            with open(output_path, 'w') as f:
                json.dump(osp_data, f, indent=4)
            return CallToolResult(content=[TextContent(type="text", text=f"OpenShot project saved to {output_path}")])
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error saving project: {str(e)}")], isError=True)

    elif name == "quick_render_ffmpeg":
        output_path = (arguments or {}).get("output_path", "output.mp4")
        if not project_state["clips"]:
            return CallToolResult(content=[TextContent(type="text", text="Error: No clips added to project.")], isError=True)
        
        try:
            # Create a concat file for ffmpeg
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                # ffmpeg concat only works well with same codecs/resolutions
                # For a true "quick render", we just append them.
                for clip in sorted(project_state["clips"], key=lambda x: x["position"]):
                    # Note: ffmpeg 'concat' demuxer requires 'file' directive
                    f.write(f"file '{clip['path']}'\n")
                    # Duration is tricky with concat demuxer if clips overlap or have gaps
                concat_file = f.name
            
            # Run ffmpeg
            # -f concat -safe 0: use the list of files
            # -c copy: avoid re-encoding (fastest, but files must be similar)
            # If files are different, we'd need a complex filter, but let's stick to fast concat for now.
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path]
            
            process = subprocess.run(cmd, capture_output=True, text=True)
            os.unlink(concat_file)
            
            if process.returncode == 0:
                return CallToolResult(content=[TextContent(type="text", text=f"Quick render successful! Video saved to {output_path}")])
            else:
                # If copy fails (incompatible formats), try re-encoding (slower but safer)
                print("Fast concat failed, attempting re-encode...", file=sys.stderr)
                cmd_slow = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, output_path]
                process_slow = subprocess.run(cmd_slow, capture_output=True, text=True)
                if process_slow.returncode == 0:
                    return CallToolResult(content=[TextContent(type="text", text=f"Quick render (re-encoded) successful! Video saved to {output_path}")])
                return CallToolResult(content=[TextContent(type="text", text=f"FFmpeg Error: {process.stderr}\n{process_slow.stderr}")], isError=True)
                
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error during render: {str(e)}")], isError=True)

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="openshot-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import os
    import sys
    # Recursive cleaner: if we detecting we are in a "dirty" environment that prints 
    # things on startup (like "Welcome back"), we re-run ourselves and filter stdout.
    if os.environ.get("MCP_CLEANER_OK") != "TRUE":
        import subprocess
        new_env = os.environ.copy()
        new_env["MCP_CLEANER_OK"] = "TRUE"
        proc = subprocess.Popen(
            [sys.executable] + sys.argv, 
            stdout=subprocess.PIPE, 
            stdin=sys.stdin, 
            stderr=sys.stderr, 
            env=new_env
        )
        
        # Filter EVERY line of stdout to ensure only valid JSON-RPC reaches the client
        for line in proc.stdout:
            stripped = line.strip()
            if stripped.startswith(b'{'):
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            elif stripped:
                # Redirect noise to stderr for debugging
                sys.stderr.buffer.write(b"[DEBUG] Discarded noise: " + line)
                sys.stderr.flush()
        
        sys.exit(proc.wait())
    else:
        # We are the "clean" child process
        asyncio.run(main())
