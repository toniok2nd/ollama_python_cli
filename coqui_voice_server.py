from mcp.server.fastmcp import FastMCP
import asyncio
import os
import uuid
import sys
from concurrent.futures import ThreadPoolExecutor

# Initialize FastMCP Server
mcp = FastMCP("coqui-voice-server")

# Global TTS model reference to allow lazy loading
_tts_model = None

def get_tts_model(model_name: str = "tts_models/en/ljspeech/glow-tts"):
    """
    Lazy load the TTS model.
    """
    global _tts_model
    if _tts_model is None:
        try:
            from TTS.api import TTS
            import torch
            # Check for GPU
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Loading Coqui TTS model '{model_name}' on {device}...", file=sys.stderr)
            _tts_model = TTS(model_name=model_name, progress_bar=False, gpu=torch.cuda.is_available())
            print("Model loaded.", file=sys.stderr)
        except ImportError:
            raise ImportError("TTS library not found. Please install with 'pip install TTS'.")
    return _tts_model

def run_tts_generation(text: str, output_file: str, model_name: str, speaker: str = None, language: str = None):
    """
    Synchronous helper to run TTS generation (CPU/GPU bound).
    """
    tts = get_tts_model(model_name)
    # Some models allow multi-speaker or multi-language
    # For simplicity, we just pass what we have if the model supports it, 
    # but the simple API often handles defaults well.
    # Note: tts.tts_to_file supports speaker and language args.
    
    tts.tts_to_file(text=text, file_path=output_file, speaker=speaker, language=language)

def play_audio(file_path: str):
    """Helper to play audio using minimal dependencies or tools."""
    # Try different players
    players = ["ffplay", "aplay", "paplay", "mpg123"]
    for player in players:
        try:
            import subprocess
            # Use -nodisp -autoexit for ffplay to be unobtrusive
            args = [player, file_path]
            if player == "ffplay":
                args.extend(["-nodisp", "-autoexit", "-loglevel", "quiet"])
            
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    # Fallback to printing path if no player found
    print(f"Audio saved to {file_path}. Please open it manually.")

@mcp.tool()
async def speak_text_coqui(text: str, model_name: str = "tts_models/en/ljspeech/glow-tts", speaker: str = None, language: str = None) -> str:
    """
    Convert text to speech using Coqui TTS and play it locally.
    
    Args:
        text: The text to speak.
        model_name: The Coqui TTS model to use (default: tts_models/en/ljspeech/glow-tts).
        speaker: (Optional) Speaker ID for multi-speaker models.
        language: (Optional) Language code for multi-language models.
    """
    try:
        import torch
    except ImportError:
        return "Error: 'TTS' library (Coqui) not installed or dependencies missing. Please install it."

    # Generate a temporary file
    output_file = f"speech_coqui_{uuid.uuid4().hex}.wav"
    
    try:
        loop = asyncio.get_event_loop()
        
        # Run generation in executor because it blocks
        await loop.run_in_executor(None, run_tts_generation, text, output_file, model_name, speaker, language)
        
        # Play in a separate thread/executor
        await loop.run_in_executor(None, play_audio, output_file)

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)
            
        return f"Spoken (Coqui): '{text}'"
    except Exception as e:
        return f"Error in Coqui TTS: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
