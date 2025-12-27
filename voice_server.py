from mcp.server.fastmcp import FastMCP
import asyncio
import os
import uuid
import sys
from concurrent.futures import ThreadPoolExecutor

# Initialize FastMCP Server
mcp = FastMCP("voice-server")

async def run_tts(text: str, voice: str, output_file: str) -> None:
    """Helper to run edge-tts command."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

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
async def speak_text(text: str, voice: str = "en-US-AriaNeural") -> str:
    """
    Convert text to speech and play it locally.
    
    Args:
        text: The text to speak.
        voice: The voice to use (default: en-US-AriaNeural).
    """
    try:
        import edge_tts
    except ImportError:
        return "Error: 'edge-tts' library not installed. Please install the 'Medium' or 'Full' tier."

    # Generate a temporary file
    output_file = f"speech_{uuid.uuid4().hex}.mp3"
    
    try:
        await run_tts(text, voice, output_file)
        
        # Play in a separate thread to not block completely, 
        # but for this simple tool satisfying the user immediately is fine.
        # However, playing audio blocks. Let's do it in a thread executor if typically long.
        # For CLI usage, blocking until speech is done is actually often desired to avoid overlap.
        # But let's run in executor to keep the event loop moving if needed.
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, play_audio, output_file)

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)
            
        return f"Spoken: '{text}'"
    except Exception as e:
        return f"Error in text-to-speech: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
