#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CLI wrapper that talks to an MCP server (FastAPI) which in turn talks to Ollama.
All side‑effects (file creation / git commands) are performed by the server,
so this client never calls `ollama` directly.
"""

# ------------------------------------------------------------
#  ⚙️  CONFIGURATION – adapt to your environment
# ------------------------------------------------------------
MCP_URL = "http://127.0.0.1:8000/mcp/v1/dialogue"   # adresse du serveur MCP
TOKEN   = "eyJdemo-token"                           # même token que le serveur (remplacez en prod)

# ------------------------------------------------------------
#  Imports
# ------------------------------------------------------------
import argparse
import sys
import uuid
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx                     # pip install httpx
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown

# ------------------------------------------------------------
#  Rich console & Prompt‑Toolkit styles
# ------------------------------------------------------------
console = Console()

style_user = Style.from_dict({
    "": "#ffffff bg:#0e49ba",   # bleu foncé pour le prompt
})

# ------------------------------------------------------------
#  Helper utilities
# ------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI wrapper around an MCP server (Ollama + Git).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-m", "--model", type=str, required=False,
                        help="Nom du modèle Ollama (ex: llama3)", metavar="MODEL")
    parser.add_argument("-r", "--repo", type=str, default=".",
                        help="Chemin du dépôt Git que le modèle pourra manipuler.", metavar="PATH")
    return parser

def _init_session() -> str:
    """Génère un `session_id` unique valable pendant toute l’exécution du client."""
    return str(uuid.uuid4())

def _default_context(repo_path: str) -> Dict[str, Any]:
    """Valeur initiale du champ `context` envoyé au serveur."""
    return {
        "variables": {"repo_path": repo_path},
        "history": []          # le serveur remplira l’historique
    }

def _extract_text_from_markdown(txt: str) -> str:
    """Supprime d’éventuels triples back‑ticks autour de la réponse."""
    if txt.strip().startswith("```"):
        parts = txt.strip().split("\n")
        if len(parts) >= 3:
            return "\n".join(parts[1:-1])
    return txt

# ------------------------------------------------------------
#  Communication with the MCP server
# ------------------------------------------------------------
async def call_mcp(
    session_id: str,
    user_msg: str,
    context: Dict[str, Any],
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Envoie un message au serveur MCP et retourne le JSON décodé.
    """
    request_body = {
        "version": "1.0",                     # <-- champ obligatoire
        "session_id": session_id,
        "auth": {"type": "Bearer", "token": TOKEN},
        "payload": {
            "type": "message",
            "content": user_msg,
            "lang": "fr"
        },
        "context": context,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(MCP_URL, json=request_body)

        # Affichage du détail d’erreur (utile pour le debug 422)
        if resp.status_code >= 400:
            console.print("[bold red]Réponse du serveur :[/]")
            console.print(resp.text)

        resp.raise_for_status()
        return resp.json()

# ------------------------------------------------------------
#  Main – boucle interactive
# ------------------------------------------------------------
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # 1️⃣ Vérification du dépôt Git demandé
    repo_path = Path(args.repo).expanduser().resolve()
    if not repo_path.is_dir():
        console.print(f"[bold red]Erreur :[/] Le répertoire {repo_path} n’existe pas.")
        sys.exit(1)

    # 2️⃣ Initialise session & contexte
    session_id = _init_session()
    context = _default_context(str(repo_path))

    console.print("[bold green]Chat‑MCP + Ollama (tapez « exit » pour quitter)[/]")

    # 3️⃣ Boucle REPL
    while True:
        try:
            user_input = prompt("🧑‍💻 > ", style=style_user).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[bold yellow]Fin de session…[/]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            console.print("[bold yellow]Au revoir ![/]")
            break
        if user_input.startswith("/"):
            console.print("[bold magenta]Commande interne non implémentée[/]")
            continue

        # 4️⃣ Appel au serveur MCP
        try:
            # asyncio.run crée une boucle temporaire pour chaque appel sync → async
            result = asyncio.run(
                call_mcp(session_id, user_input, context, args.model)
            )
        except Exception as exc:
            console.print(f"[bold red]Erreur de communication :[/] {exc}")
            continue

        # 5️⃣ Mise à jour du contexte local (history + variables)
        context = result.get("context", context)

        # 6️⃣ Affichage de la réponse
        reply = result["payload"]["content"]
        reply = _extract_text_from_markdown(reply)
        console.print(Markdown(reply))

    console.print("[bold cyan]Session terminée.[/]")

if __name__ == "__main__":
    main()


