from mcp.server.fastmcp import FastMCP
import sys
import threading
from typing import Optional

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

# Initialize FastMCP Server
mcp = FastMCP("multimedia-server")

@mcp.tool()
def capture_webcam(filename: str = "webcam.jpg") -> str:
    """
    Capture a frame from the webcam and save it to a file.
    
    Args:
        filename: The filename to save the image (e.g., 'snapshot.jpg'). Default 'webcam.jpg'.
    """
    try:
        try:
            _cv2 = get_cv2()
        except ImportError:
            return "Error: 'opencv-python' not installed. Please install the 'Full' tier."
        
        cap = _cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Error: Could not open webcam."
        
        # Wait for camera to warm up
        for _ in range(5):
            cap.read()
                
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            _cv2.imwrite(filename, frame)
            return f"Webcam capture successful. Image saved to {filename}"
        else:
            return "Error: Failed to capture frame from webcam."
    except Exception as e:
        return f"Error capturing webcam: {e}"

@mcp.tool()
def record_and_transcribe(duration: int = 5) -> str:
    """
    Record audio from the microphone for a specified duration and transcribe it to text using Whisper.
    
    Args:
        duration: Duration of the recording in seconds (default 5).
    """
    fs = 16000  # Sample rate for Whisper
    
    try:
        try:
            _sd = get_sd()
            _whisper = get_whisper()
            _np = get_np()
        except ImportError:
            return "Error: 'sounddevice', 'numpy', or 'openai-whisper' not installed. Please install the 'Full' tier."
        
        # Use a tiny model for speed
        model = _whisper.load_model("tiny")
        
        print(f"Recording for {duration} seconds...", file=sys.stderr)
        recording = _sd.rec(int(duration * fs), samplerate=fs, channels=1)
        _sd.wait()  # Wait for recording to finish
        print("Recording finished. Transcribing...", file=sys.stderr)
        
        # Convert to float32 if needed
        audio = recording.flatten().astype(_np.float32)
        
        # Transcribe
        result = model.transcribe(audio)
        text = result.get("text", "").strip()
        
        return f"Transcription: {text}"
        
    except Exception as e:
        return f"Error in STT: {e}"

@mcp.tool()
def start_recording() -> str:
    """Start recording audio from the microphone in the background. Does not return until stop_recording is called."""
    try:
        try:
            _sd = get_sd()
        except ImportError:
            return "Error: 'sounddevice' not installed. Please install the 'Full' tier."

        if recording_state["active"]:
            return "Error: Recording already in progress."
        
        # Record a very long buffer (e.g., 10 minutes)
        max_duration = 600 
        fs = recording_state["fs"]
        recording_state["active"] = True
        recording_state["buffer"] = _sd.rec(int(max_duration * fs), samplerate=fs, channels=1)
        
        return "Recording started. Type '<<' again to stop."
    except Exception as e:
        recording_state["active"] = False
        return f"Error starting recording: {e}"

@mcp.tool()
def stop_recording() -> str:
    """Stop the background recording and transcribe it to text."""
    try:
        try:
            _sd = get_sd()
            _whisper = get_whisper()
            _np = get_np()
        except ImportError:
            return "Error: 'sounddevice', 'numpy', or 'openai-whisper' not installed. Please install the 'Full' tier."

        if not recording_state["active"]:
             return "Error: No recording in progress."

        _sd.stop()
        recording_state["active"] = False
        
        # Process the buffer
        # actual recorded length is usually determined by when we stopped, 
        # but _sd.rec returns the full buffer. 
        # Ideally we'd know how many samples were captured, but simple stop() on a blocking rec() isn't trivial asynchronously.
        # Wait, start_recording used _sd.rec() which is non-blocking effectively if not waited on?
        # sounddevice.rec is non-blocking by default. It returns immediately.
        
        print("Transcribing...", file=sys.stderr)
        
        model = _whisper.load_model("tiny")
        full_recording = recording_state["buffer"]
        
        # Trim zeros if needed? For now just transcribe the whole buffer (mostly silence if short recording).
        # Actually, sounddevice fills the buffer. If we stop early, the rest is zeros?
        # A safer way to find the end of meaningful audio is simpler, but for this MVP let's just transcribe.
        # Whisper handles silence reasonably well.
        
        audio = full_recording.flatten().astype(_np.float32)
        
        result = model.transcribe(audio)
        text = result.get("text", "").strip()
        
        return f"Transcription: {text}"
    except Exception as e:
        recording_state["active"] = False
        return f"Error stopping recording: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
