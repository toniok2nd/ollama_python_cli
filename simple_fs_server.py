from mcp.server.fastmcp import FastMCP
import os

# Create an MCP server
mcp = FastMCP("Simple File System Server")

@mcp.tool()
def read_file(path: str) -> str:
    """Read the content of a file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {path}: {e}"

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file {path}: {e}"

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories in the given path."""
    try:
        return "\n".join(os.listdir(path))
    except Exception as e:
        return f"Error listing directory {path}: {e}"

@mcp.tool()
def create_directory(path: str) -> str:
    """Create a new directory."""
    try:
        os.makedirs(path, exist_ok=True)
        return f"Successfully created directory {path}"
    except Exception as e:
        return f"Error creating directory {path}: {e}"

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
        if len(sys.argv) > 1:
            root_dir = sys.argv[1]
            try:
                os.chdir(root_dir)
            except Exception as e:
                # We can't print to stdout as it's used for MCP transport
                # Log to stderr
                print(f"Error changing directory to {root_dir}: {e}", file=sys.stderr)
                sys.exit(1)
                
        mcp.run(transport='stdio')
