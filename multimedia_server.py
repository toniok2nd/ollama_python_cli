import asyncio
import os
import sys
import tempfile
import threading
from typing import Any, Dict, List, Optional

# Lazy imports for heavy libraries
np = None
cv2 = None
sd = None
whisper = None

# State for toggled recording
recording_state = {
    "active": False,
    "buffer": None,
    "fs": 16000
}

def get_cv2():
    global cv2
    if cv2 is None:
        import cv2 as _cv2
        cv2 = _cv2
    return cv2

def get_sd():
    global sd
    if sd is None:
        import sounddevice as _sd
        sd = _sd
    return sd

def get_whisper():
    global whisper
    if whisper is None:
        import whisper as _whisper
        whisper = _whisper
    return whisper

def get_np():
    global np
    if np is None:
        import numpy as _np
        np = _np
    return np

from mcp.server.stdio import stdio_server
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

# Initialize MCP Server
server = Server("multimedia-server")

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available multimedia tools."""
    return [
        Tool(
            name="capture_webcam",
            description="Capture a frame from the webcam and save it to a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename to save the image (e.g., 'snapshot.jpg')",
                        "default": "webcam.jpg"
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="record_and_transcribe",
            description="Record audio from the microphone for a specified duration and transcribe it to text using Whisper.",
            inputSchema={
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "integer",
                        "description": "Duration of the recording in seconds (default 5)",
                        "default": 5
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="start_recording",
            description="Start recording audio from the microphone in the background. Does not return until stop_recording is called.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="stop_recording",
            description="Stop the background recording and transcribe it to text.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any] | None
) -> CallToolResult:
    """Handle multimedia tool calls."""
    if name == "capture_webcam":
        filename = (arguments or {}).get("filename", "webcam.jpg")
        try:
            try:
                _cv2 = get_cv2()
            except ImportError:
                 return CallToolResult(content=[TextContent(type="text", text="Error: 'opencv-python' not installed. Please install the 'Full' tier.")], isError=True)
            
            cap = _cv2.VideoCapture(0)
            if not cap.isOpened():
                return CallToolResult(content=[TextContent(type="text", text="Error: Could not open webcam.")], isError=True)
            
            # Wait for camera to warm up
            for _ in range(5):
                 cap.read()
                 
            ret, frame = cap.read()
            if ret:
                _cv2.imwrite(filename, frame)
                cap.release()
                return CallToolResult(content=[TextContent(type="text", text=f"Webcam capture successful. Image saved to {filename}")])
            else:
                cap.release()
                return CallToolResult(content=[TextContent(type="text", text="Error: Failed to capture frame from webcam.")], isError=True)
        except Exception as e:
            return CallToolResult(content=[TextContent(type="text", text=f"Error capturing webcam: {str(e)}")], isError=True)

    elif name == "record_and_transcribe":
        duration = (arguments or {}).get("duration", 5)
        fs = 16000  # Sample rate for Whisper
        
        try:
            try:
                _sd = get_sd()
                _whisper = get_whisper()
            except ImportError:
                 return CallToolResult(content=[TextContent(type="text", text="Error: 'sounddevice' or 'openai-whisper' not installed. Please install the 'Full' tier.")], isError=True)
            
            # Use a tiny model for speed
            model = _whisper.load_model("tiny")
            
            print(f"Recording for {duration} seconds...", file=sys.stderr)
            recording = _sd.rec(int(duration * fs), samplerate=fs, channels=1)
            _sd.wait()  # Wait for recording to finish
            print("Recording finished. Transcribing...", file=sys.stderr)
            
            try:
                _np = get_np()
            except ImportError:
                 return CallToolResult(content=[TextContent(type="text", text="Error: 'numpy' not installed. Please install the 'Full' tier.")], isError=True)
            
            # Convert to float32 if needed
            audio = recording.flatten().astype(_np.float32)
            
            # Transcribe
            result = model.transcribe(audio)
            text = result.get("text", "").strip()
            
            return CallToolResult(content=[TextContent(type="text", text=f"Transcription: {text}")])
            
        except Exception as e:
             return CallToolResult(content=[TextContent(type="text", text=f"Error in STT: {str(e)}")], isError=True)

    elif name == "start_recording":
        try:
            _sd = get_sd()
            if recording_state["active"]:
                 return CallToolResult(content=[TextContent(type="text", text="Error: Recording already in progress.")], isError=True)
            
            # Record a very long buffer (e.g., 10 minutes)
            max_duration = 600 
            fs = recording_state["fs"]
            recording_state["active"] = True
            recording_state["buffer"] = _sd.rec(int(max_duration * fs), samplerate=fs, channels=1)
            
            return CallToolResult(content=[TextContent(type="text", text="Recording started. Type '<<' again to stop.")])
        except Exception as e:
             recording_state["active"] = False
             return CallToolResult(content=[TextContent(type="text", text=f"Error starting recording: {str(e)}")], isError=True)

    elif name == "stop_recording":
        try:
            _sd = get_sd()
            _whisper = get_whisper()
            _np = get_np()

            if not recording_state["active"]:
                 return CallToolResult(content=[TextContent(type="text", text="Error: No recording in progress.")], isError=True)
            
            # Stop the recording
            _sd.stop()
            recording_state["active"] = False
            
            # Extract the part that was actually recorded
            # Note: sounddevice returns the full buffer, but Whisper is generally good at ignoring end silence.
            audio = recording_state["buffer"].flatten().astype(_np.float32)
            recording_state["buffer"] = None # cleanup

            # Use a tiny model for speed
            model = _whisper.load_model("tiny")
            result = model.transcribe(audio)
            text = result.get("text", "").strip()
            
            return CallToolResult(content=[TextContent(type="text", text=text)])
            
        except Exception as e:
             recording_state["active"] = False
             return CallToolResult(content=[TextContent(type="text", text=f"Error stopping recording: {str(e)}")], isError=True)

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="multimedia-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
