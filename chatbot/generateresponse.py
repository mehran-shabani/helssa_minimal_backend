# chatbot/generateresponse.py
# --------------------------------
# سرویس تولید پاسخ برای چت‌بات پزشکی (Vision: تصویر + متن) با OpenAI-compatible SDK (GapGPT)

from __future__ import annotations

import base64
import io
import json
import logging
import mimetypes
import re
import time
from typing import Dict, List, Optional, Sequence, Tuple

from django.conf import settings
from django.db import transaction

from chatbot.models import ChatMessage, ChatSession
from chatbot.cleaner import clean_bot_message
from chatbot.utils.text_summary import (
    get_or_create_global_summary,
    get_or_update_session_summary,
)

logger = logging.getLogger(__name__)

# ==============================
# OpenAI-compatible client
# ==============================
try:
    from openai import OpenAI
except Exception as exc:  # کتابخانه نصب نیست
    OpenAI = None
    logger.error("openai library not installed: %s", exc)

CLIENT = None
def _get_client():
    global CLIENT
    if CLIENT is None:
        if not OpenAI:
            raise RuntimeError("openai library missing. `pip install openai`")
        base_url = getattr(settings, "GAPGPT_BASE_URL", "https://api.gapgpt.app/v1")
        api_key  = getattr(settings, "GAPGPT_API_KEY", None)
        if not api_key:
            raise RuntimeError("GAPGPT_API_KEY is missing in settings/env.")
        CLIENT = OpenAI(base_url=base_url, api_key=api_key)
    return CLIENT

# ==============================
# System / summaries
# ==============================
SYSTEM_PROMPT = (
    "شما یک پزشک با تجربه هستید. علائم بیمار را بررسی و تشخیص و درمان مناسب ارائه کنید. "
    "همیشه پاسخ نهایی را به زبان فارسی و به‌صورت دقیق و مختصر ارائه کن. اگر لازم شد "
    "پیشنهاد بده بیمار در اپلیکیشن هلسا قسمت ویزیت نوبت بگیرد تا پزشک با شرح‌حال کامل تصمیم بهتری بگیرد."
)
MIN_SUMMARY_LEN = 30
MAX_SUMMARY_CHARS = 2000

_REPEAT_WORDS = re.compile(
    r"(\b[\u0600-\u06FF\w]{2,30}\b(?:\s+|$))(?:\1){2,}",
    re.IGNORECASE,
)

# ==============================
# Image constraints
# ==============================
MAX_IMAGES = 4
MAX_IMAGE_MEGAPIXELS = 3.0
MAX_IMAGE_BYTES_TARGET = 1_200_000

# پاس دوم (fallback) اگر پِی‌لود بزرگ شد
MAX_IMAGES_FALLBACK = 1
MAX_IMAGE_MEGAPIXELS_FALLBACK = 2.0
MAX_IMAGE_BYTES_TARGET_FALLBACK = 900_000

ALLOW_HEIC = True

# ==============================
# Utils
# ==============================
def _ensure_text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return str(x)

def _clip_text(s: str, max_chars: int) -> str:
    if not s:
        return s
    s = s.strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"

def _remove_repeated(text: str) -> str:
    text = _ensure_text(text)
    try:
        return _REPEAT_WORDS.sub(r"\1", text)
    except Exception:
        return text

def _guess_mime(name: str) -> str:
    mime, _ = mimetypes.guess_type(name)
    return mime or "image/jpeg"

def _to_data_url(data: bytes, mime: str) -> str:
    import base64 as _b64
    encoded = _b64.b64encode(data).decode()
    return f"data:{mime};base64,{encoded}"

# ==============================
# Imaging
# ==============================
_PIL_READY = False
_HEIF_READY = False
try:
    from PIL import Image
    _PIL_READY = True
    if ALLOW_HEIC:
        try:
            import pillow_heif  # type: ignore
            pillow_heif.register_heif_opener()
            _HEIF_READY = True
        except Exception:
            _HEIF_READY = False
except Exception:
    _PIL_READY = False

def _downscale_to_megapixels(im, max_mp: float):
    w, h = im.size
    mp = (w * h) / 1_000_000.0
    if mp <= max_mp:
        return im
    scale = (max_mp / mp) ** 0.5
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return im.resize(new_size, Image.LANCZOS)

def _jpeg_bytes(im: "Image.Image", quality: int) -> bytes:
    buf = io.BytesIO()
    im.save(
        buf,
        format="JPEG",
        quality=int(quality),
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    return buf.getvalue()

def _process_image_to_budget(
    data: bytes, mime: str, *, target_mp: float, target_bytes: int
) -> Tuple[bytes, str]:
    if not _PIL_READY:
        return data, mime
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im = _downscale_to_megapixels(im, target_mp)
            q_lo, q_hi = 45, 88
            best = _jpeg_bytes(im, q_hi)
            if len(best) <= target_bytes:
                return best, "image/jpeg"
            for _ in range(5):
                mid = (q_lo + q_hi) // 2
                cand = _jpeg_bytes(im, mid)
                if len(cand) <= target_bytes:
                    best = cand
                    q_lo = mid + 1
                else:
                    q_hi = mid - 1
                if q_lo > q_hi:
                    break
            return best, "image/jpeg"
    except Exception as exc:
        logger.warning("Image process failed; fallback original. err=%s", exc)
        return data, mime

def _b64_to_bytes(b64: str) -> Optional[bytes]:
    try:
        if b64.startswith("data:"):
            _, b64part = b64.split(",", 1)
            return base64.b64decode(b64part)
        return base64.b64decode(b64)
    except Exception:
        return None

def _build_user_content_with_images(
    text: str,
    *,
    image_b64_list: Optional[Sequence[str]] = None,
    image_files: Optional[Sequence] = None,
    image_urls: Optional[Sequence[str]] = None,
    max_images: int = MAX_IMAGES,
    target_mp: float = MAX_IMAGE_MEGAPIXELS,
    target_bytes: int = MAX_IMAGE_BYTES_TARGET,
) -> List[Dict]:
    """
    خروجی سازگار با OpenAI: آرایه‌ای از پارت‌های متن/عکس:
    [{"type":"image_url","image_url":{"url":...}}, {"type":"text","text":"..."}]
    """
    parts: List[Dict] = []
    count = 0

    if image_b64_list:
        for b64 in image_b64_list:
            if count >= max_images:
                break
            if not isinstance(b64, str) or not b64.strip():
                continue
            raw = _b64_to_bytes(b64)
            if raw is None:  # احتمالا dataURL است
                if not b64.startswith("data:"):
                    b64 = f"data:image/jpeg;base64,{b64}"
                parts.append({"type": "image_url", "image_url": {"url": b64}})
            else:
                data, mime = _process_image_to_budget(
                    raw, "image/jpeg", target_mp=target_mp, target_bytes=target_bytes
                )
                parts.append({"type": "image_url", "image_url": {"url": _to_data_url(data, mime)}})
            count += 1

    if image_files:
        for f in image_files:
            if count >= max_images:
                break
            try:
                data = f.read()
            except Exception:
                continue
            mime = getattr(f, "content_type", None) or _guess_mime(getattr(f, "name", ""))
            data, mime = _process_image_to_budget(
                data, mime, target_mp=target_mp, target_bytes=target_bytes
            )
            parts.append({"type": "image_url", "image_url": {"url": _to_data_url(data, mime)}})
            count += 1

    if image_urls:
        for url in image_urls:
            if count >= max_images:
                break
            if not isinstance(url, str) or not url.strip():
                continue
            parts.append({"type": "image_url", "image_url": {"url": url.strip()}})
            count += 1

    parts.append({"type": "text", "text": _ensure_text(text)})
    return parts

# ==============================
# DB helpers
# ==============================
def _get_or_create_open_session(user) -> ChatSession:
    session = ChatSession.objects.filter(user=user, is_open=True).order_by("-started_at").first()
    if session:
        return session
    return ChatSession.objects.create(user=user)

def _get_recent_history(session: ChatSession, max_len: int) -> List[Dict]:
    recent = session.messages.order_by("-created_at")[:max_len]
    return [
        {"role": "assistant" if m.is_bot else "user", "content": _ensure_text(m.message)}
        for m in reversed(recent)
    ]

def _summary_or_self(obj) -> str:
    txt = _ensure_text(getattr(obj, "rewritten_text", "")).strip()
    if len(txt) >= MIN_SUMMARY_LEN:
        return _clip_text(txt, MAX_SUMMARY_CHARS)
    for k in ("original_text", "source_text", "raw_text", "text", "content"):
        v = _ensure_text(getattr(obj, k, "")).strip()
        if v:
            return _clip_text(v, MAX_SUMMARY_CHARS)
    return ""

# ==============================
# Main
# ==============================
def generate_gpt_response(
    request_user,
    user_message: str | None,
    *,
    new_session: bool = False,
    image_b64_list: Optional[Sequence[str]] = None,
    image_files: Optional[Sequence] = None,
    image_urls: Optional[Sequence[str]] = None,
    max_history_length: int = 5,
    force_model: Optional[str] = None,
) -> str:
    t0 = time.monotonic()
    try:
        client = _get_client()
        model_name = force_model or getattr(settings, "VISION_MODEL_NAME", "gpt-4o")
        max_tokens = int(getattr(settings, "RESPONSE_MAX_TOKENS", 1500))

        # Session
        if new_session:
            ChatSession.objects.filter(user=request_user, is_open=True).update(is_open=False)
            session = ChatSession.objects.create(user=request_user)
        else:
            session = _get_or_create_open_session(request_user)

        # Summaries & History
        global_sum = get_or_create_global_summary(request_user)
        session_sum = get_or_update_session_summary(session)
        history = _get_recent_history(session, max_history_length)

        # Base messages
        messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        gtxt = _summary_or_self(global_sum)
        if gtxt:
            messages.append({"role": "system", "content": "[GLOBAL SUMMARY]\n" + gtxt})
        stxt = _summary_or_self(session_sum)
        if stxt:
            messages.append({"role": "system", "content": "[SESSION SUMMARY]\n" + stxt})

        # Build user turn
        has_images = bool(image_b64_list or image_files or image_urls)
        if has_images:
            user_content = _build_user_content_with_images(
                user_message or "",
                image_b64_list=image_b64_list,
                image_files=image_files,
                image_urls=image_urls,
                max_images=MAX_IMAGES,
                target_mp=MAX_IMAGE_MEGAPIXELS,
                target_bytes=MAX_IMAGE_BYTES_TARGET,
            )
            messages_with_user = messages + [{"role": "user", "content": user_content}]
        else:
            if not (user_message and user_message.strip()):
                return "لطفاً متن سؤال یا تصویر را ارسال کنید."
            messages_with_user = messages + [{"role": "user", "content": _ensure_text(user_message)}]

        # Call API
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages_with_user,
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.9,
        )
        bot_msg = (resp.choices[0].message.content or "").strip()
        if not bot_msg:
            logger.error("Empty response from model.")
            return "🤔 پاسخ نامعتبر از سرویس دریافت شد."

        bot_msg = _remove_repeated(bot_msg)

        # Save to DB
        try:
            with transaction.atomic():
                ChatMessage.objects.bulk_create([
                    ChatMessage(session=session, user=request_user, message=_ensure_text(user_message or ""), is_bot=False),
                    ChatMessage(session=session, user=request_user, message=bot_msg, is_bot=True),
                ])
        except Exception as exc:
            logger.exception("DB save failed: %s", exc)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info("generate_gpt_response done in %sms (has_images=%s)", elapsed_ms, has_images)

        return clean_bot_message(bot_msg)

    except Exception as exc:
        logger.exception("generate_gpt_response crashed: %s", exc)
        return "❗ خطای غیرمنتظره‌ای رخ داد. لطفاً دوباره تلاش کنید."
