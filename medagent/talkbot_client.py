# medagent/talkbot_client.py
"""Low-level HTTP client for TalkBot API (text و vision)."""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict

import requests
from django.conf import settings

TALKBOT_BASE: str = settings.TALKBOT_BASE_URL
TALKBOT_TOKEN: str = settings.TALKBOT_API_KEY
DEFAULT_MODEL: str = "gemini-pro-vision"


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {TALKBOT_TOKEN}",
        "Content-Type": "application/json",
    }


_DATA_URI_RE = re.compile(r"^data:[^;]+;base64,")


def _as_base64(image: str) -> str:
    """تبدیل ورودی به data URI (مسیر فایل، URL یا data:image;base64, ...)."""
    if _DATA_URI_RE.match(image):
        return image  # قبلاً دیتای Base64 است
    if image.startswith(("http://", "https://")):  # URL
        resp = requests.get(image, timeout=15)
        resp.raise_for_status()
        mime = resp.headers.get("content-type", "application/octet-stream")
        b64 = base64.b64encode(resp.content).decode()
        return f"data:{mime};base64,{b64}"
    # مسیر فایل
    path = Path(image)
    if not path.exists():
        raise FileNotFoundError(str(path))
    mime, _ = mimetypes.guess_type(path.name)
    with path.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime or 'application/octet-stream'};base64,{b64}"


def tb_chat(
    messages: list[dict[str, Any]],
    model: str = "o3-mini",
    timeout: int = 30,
) -> str:
    """ارسال مکالمهٔ متنی به مدل زبانی TalkBot."""
    body = {"model": model, "messages": messages}
    try:
        r = requests.post(
            f"{TALKBOT_BASE}/v1/chat/completions",
            headers=_headers(),
            json=body,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.text
    except Exception as exc:
        logging.exception("tb_chat error: %s", exc)
        return '{"error": "talkbot communication failed"}'


def vision_analyze(
    image: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """تحلیل تصویر پزشکی به‌همراه متن پرسش."""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _as_base64(image)}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.7,
        "stream": False,
    }
    try:
        r = requests.post(
            f"{TALKBOT_BASE}/v1/chat/completions",
            headers=_headers(),
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logging.exception("vision_analyze error: %s", exc)
        return {"error": str(exc)}
