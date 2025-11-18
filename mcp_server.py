#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model‑Context Protocol) server that:

 • talks to an Ollama LLM,
 • parses JSON action blocks (create / update / delete files, Git commands),
 • executes those actions safely,
 • returns the final text response (Markdown by default).

Run with:
    uvicorn mcp_server:app --host 0.0.0.0 --port 8000 --reload
"""

# --------------------------------------------------------------
# 1️⃣ Imports & global constants
# --------------------------------------------------------------
import os
import uuid
import time
import json
import pathlib
import re
from typing import List, Optional, Dict, Literal, Any

import httpx                     # pip install httpx
import git                       # GitPython
from fastapi import FastAPI, WebSocket, Depends, HTTPException, Header
from pydantic import BaseModel, Field, validator
import uvicorn                   # only needed when launching with `python mcp_server.py`

# --------------------------------------------------------------
# 2️⃣ FastAPI app (must be global so uvicorn can import it)
# --------------------------------------------------------------
app = FastAPI(title="MCP‑Git‑Ollama Server")
__all__ = ["app"]                     # explicit export for tools that inspect __all__

# In‑memory store – replace with Redis / DB for prod
SESSIONS: Dict[str, "Context"] = {}

# --------------------------------------------------------------
# 3️⃣ MCP data models (Pydantic)
# --------------------------------------------------------------
class Auth(BaseModel):
    type: str
    token: str


class Payload(BaseModel):
    type: Literal["message", "command"] = "message"
    content: str
    lang: str = "fr"
    metadata: Optional[Dict[str, Any]] = None


class Context(BaseModel):
    conversation_id: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)   # e.g. {"repo_path": "."}
    history: List[Dict[str, str]] = Field(default_factory=list)   # [{"role":"user","text":…}, …]


class MCPMessage(BaseModel):
    version: str = "1.0"
    session_id: str
    user_id: Optional[str] = None
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    auth: Auth
    payload: Payload
    context: Context


# ----- Action models that the LLM may return -------------------
class FileAction(BaseModel):
    """Create / update / delete a file inside the repo."""
    action: Literal["create", "update", "delete"]
    path: str                     # relative to repo root
    content: Optional[str] = None

    @validator("path")
    def no_path_traversal(cls, v):
        # Prevent "../../" attacks
        if ".." in pathlib.Path(v).parts:
            raise ValueError("Path traversal is not allowed")
        return v


class GitAction(BaseModel):
    """Subset of git commands the model is allowed to ask for."""
    git: Literal["add", "commit", "push", "pull", "branch", "checkout"]
    paths: Optional[List[str]] = None          # for add, etc.
    message: Optional[str] = None              # commit message
    branch: Optional[str] = None               # for branch / checkout


class SimpleMsg(BaseModel):
     msg: str

@app.post("/mcp/v1/simple")
async def simple(msg: SimpleMsg, _: None = Depends(_check_auth)):
    # Build a MCPMessage on‑the‑fly
    request_body = {
        "version": "1.0",
        "session_id": str(uuid.uuid4()),
        "auth": {"type": "Bearer", "token": TOKEN},
        "payload": {"type": "message", "content": msg.msg, "lang": "fr"},
        "context": {"variables": {"repo_path": "."}, "history": []},
    }
    # Re‑use the main dialogue logic
    return await dialogue(MCPMessage(**request_body), None)


# --------------------------------------------------------------
# 4️⃣ Helper utilities
# --------------------------------------------------------------
def _check_auth(auth: Auth):
    """Very simple token check – replace with real JWT validation."""
    if not auth.token.startswith("eyJ"):
        raise HTTPException(status_code=401, detail="Invalid token")
    # In production: decode, verify exp, issuer, scopes, etc.


def _repo_root(ctx: Context) -> pathlib.Path:
    """Root directory the server may touch (resolved & absolute)."""
    repo_path = ctx.variables.get("repo_path", ".")
    return pathlib.Path(repo_path).resolve()


def _get_repo(repo_path: str) -> git.repo.base.Repo:
    if not os.path.isdir(repo_path):
        raise ValueError(f"Repo path does not exist: {repo_path}")
    return git.Repo(repo_path)


# ----- File actions -------------------------------------------------
def file_create(root: pathlib.Path, act: FileAction) -> str:
    target = root / act.path
    if target.exists():
        return f"❌ File already exists: {act.path}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(act.content or "", encoding="utf-8")
    return f"✅ Created file {act.path}"


def file_update(root: pathlib.Path, act: FileAction) -> str:
    target = root / act.path
    if not target.exists():
        return f"❌ File not found: {act.path}"
    target.write_text(act.content or "", encoding="utf-8")
    return f"✅ Updated file {act.path}"


def file_delete(root: pathlib.Path, act: FileAction) -> str:
    target = root / act.path
    if not target.exists():
        return f"❌ File not found: {act.path}"
    target.unlink()
    return f"✅ Deleted file {act.path}"


# ----- Git actions -------------------------------------------------
def run_git_action(repo_path: str, act: GitAction) -> str:
    repo = _get_repo(repo_path)

    if act.git == "add":
        paths = act.paths or ["."]
        repo.git.add(*paths)
        return f"✅ git add {' '.join(paths)}"

    if act.git == "commit":
        if not act.message:
            return "❌ git commit requires a message"
        repo.git.commit("-m", act.message)
        return f"✅ git commit – {act.message}"

    if act.git == "push":
        repo.git.push()
        return "✅ git push"

    if act.git == "pull":
        repo.git.pull()
        return "✅ git pull"

    if act.git == "branch":
        if not act.branch:
            return "❌ branch name required"
        repo.git.branch(act.branch)
        return f"✅ git branch {act.branch}"

    if act.git == "checkout":
        if not act.branch:
            return "❌ checkout requires a branch name"
        repo.git.checkout(act.branch)
        return f"✅ git checkout {act.branch}"

    return f"❌ Unknown git action {act.git}"


# --------------------------------------------------------------
# 5️⃣ Ollama client helpers (Markdown‑first)
# --------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")   # change if you use another model


# ----------------------------------------------------------------------
# System prompt – it does two things:
#   1️⃣ Tell the model to answer **in Markdown**.
#   2️⃣ Tell the model that when it needs to touch the filesystem or git,
#       it must emit a JSON block exactly as defined below.
# ----------------------------------------------------------------------
SYSTEM_PROMPT = """
You are an assistant that can safely manipulate files in a git repository.

When you need to create, update or delete a file, reply **only** with a JSON block
wrapped in triple back‑ticks (```json … ```). The JSON must match the schema:

{
  "action": "create|update|delete",
  "path": "relative/path/inside/repo.ext",
  "content": "file content (required for create/update)"
}

If you also want to run a git command, add a **second** JSON block after the first,
using this schema:

{
  "git": "add|commit|push|pull|branch|checkout",
  "paths": ["file1", "dir/"],          // optional, for add / other commands
  "message": "commit message",         // required for commit
  "branch": "new-branch-name"          // required for branch / checkout
}

Otherwise, answer the user's question **using proper Markdown**.
Do not wrap the entire answer in a code‑block unless the answer itself is code.
"""

async def _ollama_http(messages: List[Dict[str, str]]) -> str:
    """
    Low‑level HTTP call to Ollama.
    Returns the **content** field of Ollama's response (already Markdown‑ready).
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(OLLAMA_URL, json=payload, timeout=30.0)
        if resp.status_code >= 400:
            # Debug helper – you can see the raw error from Ollama
            console.print("[bold red]Ollama error:[/]")
            console.print(resp.text)
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns {"message":{"role":"assistant","content":"…"}}
        return data["message"]["content"]


# ----------------------------------------------------------------------
# Public helpers
# ----------------------------------------------------------------------
async def ask_ollama(messages: List[Dict[str, str]]) -> str:
    """
    Backward‑compatible function used by the ``/dialogue`` endpoint.
    It receives a *full* list of messages (system + history) and returns the raw answer.
    The system prompt already contains the Markdown + JSON‑action instructions.
    """
    return await _ollama_http(messages)


async def ask_ollama_question(
    question: str,
    system_prompt: str = SYSTEM_PROMPT,
    user_role: str = "user",
    model_name: Optional[str] = None,
) -> str:
    """
    Simple one‑shot question → Markdown answer.

    Parameters
    ----------
    question : str
        The user question.
    system_prompt : str, optional
        Prompt that forces Markdown + JSON‑action behaviour (default = SYSTEM_PROMPT).
    user_role : str, optional
        Role of the user message (default ``"user"``).
    model_name : str, optional
        Override the model used for this call.

    Returns
    -------
    str
        Assistant answer in Markdown (no surrounding JSON unless the model
        decides to emit an action, which the caller can handle separately).
    """
    model_to_use = model_name or OLLAMA_MODEL
    # If you ever need to change the model for a single call, you could alter
    # the payload here; Ollama's API currently selects the model from the
    # endpoint URL, so we just keep the same model variable.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": user_role, "content": question},
    ]
    return await _ollama_http(messages)


# --------------------------------------------------------------
# 6️⃣ Core endpoint – POST /mcp/v1/dialogue
# --------------------------------------------------------------
@app.post("/mcp/v1/dialogue")
async def dialogue(msg: MCPMessage, _: None = Depends(_check_auth)):
    # 1️⃣ Load or create the session context
    ctx: Context = SESSIONS.get(msg.session_id, msg.context)

    # 2️⃣ Append user message to history (keep only last 10)
    ctx.history.append({"role": "user", "text": msg.payload.content})
    ctx.history = ctx.history[-10:]

    response_text: str = ""

    # -----------------------------------------------------------------
    # 3️⃣ If the client sent a *command* (git‑only shortcut)
    # -----------------------------------------------------------------
    if msg.payload.type == "command":
        cmd = msg.payload.content.lower()
        repo_path = ctx.variables.get("repo_path", ".")
        try:
            if "status" in cmd:
                response_text = _get_repo(repo_path).git.status()
            elif "log" in cmd:
                n = int(re.search(r"\d+", cmd).group()) if re.search(r"\d+", cmd) else 5
                response_text = _get_repo(repo_path).git.log(f"-{n}", "--oneline")
            elif "pull" in cmd:
                response_text = _get_repo(repo_path).git.pull()
            elif "push" in cmd:
                response_text = _get_repo(repo_path).git.push()
            elif "add" in cmd:
                parts = cmd.split("add", 1)[1].strip()
                paths = parts.split() if parts else ["."]
                _get_repo(repo_path).git.add(*paths)
                response_text = f"✅ git add {' '.join(paths)}"
            elif "commit" in cmd:
                m = re.search(r'commit\s*["\']?(.*?)["\']?$', cmd)
                msg_txt = m.group(1) if m else "update via chat"
                _get_repo(repo_path).git.commit("-m", msg_txt)
                response_text = f"✅ git commit – {msg_txt}"
            else:
                response_text = f"⚠️ Command not recognised: {cmd}"
        except Exception as e:
            response_text = f"❌ Git error: {str(e)}"

    # -----------------------------------------------------------------
    # 4️⃣ Normal message → ask Ollama, then maybe act on JSON blocks
    # -----------------------------------------------------------------
    else:
        # Build full message list with system prompt first
        messages_for_ollama = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ] + [{"role": m["role"], "content": m["text"]} for m in ctx.history]

        raw_reply = await ask_ollama(messages_for_ollama)

        # Try to extract JSON blocks (file actions, git actions, …)
        blocks = _extract_json_blocks(raw_reply)

        if blocks:
            repo_root = _repo_root(ctx)

            # ----- FileAction (if present) ---------------------------------
            if "action" in blocks[0]:
                try:
                    fa = FileAction(**blocks[0])
                    if fa.action == "create":
                        response_text = file_create(repo_root, fa)
                    elif fa.action == "update":
                        response_text = file_update(repo_root, fa)
                    elif fa.action == "delete":
                        response_text = file_delete(repo_root, fa)
                except Exception as e:
                    response_text = f"⚠️ Invalid FileAction payload: {e}"

            # ----- GitAction (optional second block) -----------------------
            if len(blocks) > 1 and "git" in blocks[1]:
                try:
                    ga = GitAction(**blocks[1])
                    response_text = run_git_action(str(repo_root), ga)
                except Exception as e:
                    response_text = f"⚠️ Invalid GitAction payload: {e}"
        else:
            # No JSON → plain chat reply from Ollama (already Markdown)
            response_text = raw_reply

    # 5️⃣ Append assistant reply to history (keep last 10)
    ctx.history.append({"role": "assistant", "text": response_text})
    ctx.history = ctx.history[-10:]

    # 6️⃣ Persist session
    SESSIONS[msg.session_id] = ctx

    # 7️⃣ Return MCP‑compatible JSON
    return {
        "session_id": msg.session_id,
        "payload": {"type": "message", "content": response_text},
        "context": ctx.dict(),
    }


# --------------------------------------------------------------
# 7️⃣ Helper to extract JSON blocks from Ollama answer
# --------------------------------------------------------------
def _extract_json_blocks(text: str) -> List[dict]:
    """
    Find *all* JSON blocks wrapped in triple back‑ticks.
    Returns a list of parsed dictionaries (empty list = none found).
    """
    pattern = r"```json\s*(\{.*?\})\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    parsed = []
    for m in matches:
        try:
            parsed.append(json.loads(m))
        except json.JSONDecodeError:
            continue
    return parsed


# --------------------------------------------------------------
# 8️⃣ Optional WebSocket endpoint (real‑time UI)
# --------------------------------------------------------------
@app.websocket("/mcp/v1/ws")
async def ws_endpoint(ws: WebSocket, token: str = Header(...)):
    await ws.accept()
    if not token.startswith("eyJ"):
        await ws.close(code=1008)
        return

    # Create a temporary session for this socket
    session_id = str(uuid.uuid4())
    ctx = Context(variables={"repo_path": "."})
    SESSIONS[session_id] = ctx
    await ws.send_json({"session_id": session_id})

    while True:
        try:
            data = await ws.receive_json()
        except Exception:
            break

        try:
            msg = MCPMessage(
                session_id=session_id,
                auth=Auth(type="Bearer", token=token),
                payload=Payload(**data["payload"]),
                context=ctx,
            )
        except Exception as exc:
            await ws.send_json({"error": f"Invalid message format: {exc}"})
            continue

        resp = await dialogue(msg)
        await ws.send_json(resp)


# --------------------------------------------------------------
# 9️⃣ Utility HTTP endpoints (session inspection / deletion)
# --------------------------------------------------------------
@app.get("/mcp/v1/session/{sid}")
async def get_session(sid: str, auth: Auth = Depends(_check_auth)):
    ctx = SESSIONS.get(sid)
    if not ctx:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": sid, "context": ctx.dict()}


@app.delete("/mcp/v1/session/{sid}")
async def delete_session(sid: str, auth: Auth = Depends(_check_auth)):
    if sid in SESSIONS:
        del SESSIONS[sid]
    return {"detail": "session deleted"}


# --------------------------------------------------------------
# 10️⃣ Run with `python mcp_server.py` (development mode)
# --------------------------------------------------------------
if __name__ == "__main__":
    # uvicorn will reload when you edit the file (good for dev)
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8000, reload=True)

