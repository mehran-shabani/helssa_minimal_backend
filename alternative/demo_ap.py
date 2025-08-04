# medagent_cli_demo.py
"""Simple CLI client for MedAgent REST API.

Usage examples:
    # token via flag
    python medagent_cli_demo.py --token ABC create-session --name "Chest pain"

    # token via env var
    set MEDAGENT_TOKEN=ABC   (Windows)
    export MEDAGENT_TOKEN=ABC (Linux/Mac)
    python medagent_cli_demo.py send-message --session 42 --text "سلام"

    # interactive prompt for token
    python medagent_cli_demo.py get-history

This client is plain Python (requests + argparse) and avoids any HTML/CSS/JS.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000/agent"  # change if your API root differs


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ---------------------------- core wrappers ----------------------------

def create_session(token: str, name: str) -> int:
    r = requests.post(
        f"{BASE_URL}/session/create/",
        headers=_headers(token),
        json={"name": name},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["session_id"]


def send_message(token: str, session_id: int, text: str):
    r = requests.post(
        f"{BASE_URL}/session/{session_id}/message/",
        headers=_headers(token),
        json={"content": text},
        timeout=30,
    )
    r.raise_for_status()
    print(r.json()["assistant_reply"])


def send_image(token: str, session_id: int, image_path: str, prompt: str):
    data_uri = _file_to_data_uri(image_path)
    body = {"content": {"image": data_uri, "prompt": prompt}}
    r = requests.post(
        f"{BASE_URL}/session/{session_id}/message/",
        headers=_headers(token),
        json=body,
        timeout=60,
    )
    r.raise_for_status()
    print(r.json()["assistant_reply"])


def end_session(token: str, session_id: int):
    r = requests.patch(
        f"{BASE_URL}/session/end/",
        headers=_headers(token),
        json={"session_id": session_id},
        timeout=10,
    )
    r.raise_for_status()
    print(r.json()["msg"])


def get_history(token: str):
    r = requests.get(
        f"{BASE_URL}/session/summary/",
        headers=_headers(token),
        timeout=10,
    )
    r.raise_for_status()
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))


def _file_to_data_uri(path: str) -> str:
    mime = "image/jpeg"
    if path.lower().endswith(".png"):
        mime = "image/png"
    with Path(path).open("rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


# ---------------------------- CLI ----------------------------

def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="MedAgent CLI client")
    parser.add_argument("--token", help="Bearer token (can also use MEDAGENT_TOKEN env var)")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-session"); p_create.add_argument("--name", default="Untitled")
    p_msg = sub.add_parser("send-message");  p_msg.add_argument("--session", type=int, required=True); p_msg.add_argument("--text", required=True)
    p_img = sub.add_parser("send-image");   p_img.add_argument("--session", type=int, required=True); p_img.add_argument("--image", required=True); p_img.add_argument("--prompt", default="Describe")
    p_end = sub.add_parser("end-session");  p_end.add_argument("--session", type=int, required=True)
    sub.add_parser("get-history")

    args = parser.parse_args(argv)

    # Resolve token priority: CLI flag > env var > prompt
    token = args.token or os.getenv("MEDAGENT_TOKEN")
    if not token:
        token = input("Enter your Bearer token: ").strip()
        if not token:
            sys.exit("Token is required.")

    try:
        if args.cmd == "create-session":
            sid = create_session(token, args.name); print(f"Session created: {sid}")
        elif args.cmd == "send-message":
            send_message(token, args.session, args.text)
        elif args.cmd == "send-image":
            send_image(token, args.session, args.image, args.prompt)
        elif args.cmd == "end-session":
            end_session(token, args.session)
        elif args.cmd == "get-history":
            get_history(token)
    except requests.HTTPError as e:
        print("HTTP error:", e.response.text, file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
