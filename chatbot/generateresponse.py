"""chatbot/generateresponse.py
--------------------------------
سرویس اصلی تولید پاسخ برای چت‌بات پزشکی.

منطق دو‑مرحله‌ای Vision → Text مطابق نیاز جدید:

1. اگر ورودی حاوی تصویر باشد و `force_model` تهی باشد، تصاویر با یک پرامپت ثابت
   برای مدل Vision ارسال می‌شوند و خروجی متنی Vision استخراج می‌گردد.
2. تاریخچهٔ مکالمه، خلاصه‌ها، خروجی Vision (در صورت وجود) و متن کاربر برای
   مدل متنی (یا مدل مشخص‌شده در `force_model`) ارسال می‌شود.

مزایا:
• مدل Vision فقط تصاویر را تفسیر می‌کند و متن کاربر روی پاسخ آن اثر نمی‌گذارد.
• مدل متنی با داشتن توضیح تصویری، تاریخچه و پیام کاربر پاسخ نهایی را تولید
  می‌کند.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import re
import time
from typing import Dict, List, Optional, Sequence

import requests
from django.conf import settings
from django.db import transaction

from chatbot.models import ChatMessage, ChatSession
from chatbot.cleaner import clean_bot_message
from chatbot.utils.text_summary import (
    get_or_create_global_summary,
    get_or_update_session_summary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# تنظیمات سراسری مدل‌ها و API
# ---------------------------------------------------------------------------
TALKBOT_BASE_URL = "https://api.talkbot.ir"
TALKBOT_ENDPOINT = f"{TALKBOT_BASE_URL}/v1/chat/completions"
TALKBOT_API_KEY = settings.TALKBOT_API_KEY

TALKBOT_MODEL = "o3-mini"           # مدل متنی پیش‌فرض
VISION_MODEL = "gpt-4-vision-preview"   # مدل تصویر+متن
MAX_TOKEN = 4000

REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_BACKOFF_BASE = 1.8

# ---------------------------------------------------------------------------
# پرامپت‌های سیستم
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "شما یک پزشک با تجربه هستید. علائم بیمار را بررسی و تشخیص و درمان مناسب ارائه کنید."
)

VISION_SYSTEM_PROMPT = (
    "You are an expert tele‑radiologist. Describe any clinically relevant findings "
    "from the patient image in concise Persian."
)

# ---------------------------------------------------------------------------
# RegEx برای حذف تکرارهای خروجی مدل
# ---------------------------------------------------------------------------
_REPEAT_WORDS = re.compile(r"(\b[\u0600-\u06FF\w]{2,30}\b(?:\s+|$))(?:\1){2,}", re.IGNORECASE)

# ---------------------------------------------------------------------------
# توابع کمکی HTTP / Retry
# ---------------------------------------------------------------------------

def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TALKBOT_API_KEY}",
    }


def _remove_repeated(text: str) -> str:
    """حذف توالی کلمات تکراری (اسپم) از خروجی مدل."""
    return _REPEAT_WORDS.sub(r"\1", text)


def _safe_post(url: str, payload: Dict) -> Optional[Dict]:
    """ارسال POST با بک‑آف نمایی و ثبت لاگ."""
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            resp = requests.post(url, json=payload, headers=_headers(), timeout=REQUEST_TIMEOUT)
            logger.debug("TalkBot HTTP %s (attempt %d)", resp.status_code, attempt)
            if resp.ok:
                return resp.json()
            logger.warning("TalkBot error %s: %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            logger.exception("Request failed (attempt %d): %s", attempt, exc)
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_BACKOFF_BASE ** (attempt - 1))
    return None

# ---------------------------------------------------------------------------
# توابع کمکی مربوط به تصاویر
# ---------------------------------------------------------------------------

def _guess_mime(name: str) -> str:
    mime, _ = mimetypes.guess_type(name)
    return mime or "image/jpeg"


def _to_data_url(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode()
    return f"data:{mime};base64,{encoded}"


def _build_user_content_with_images(
    text: str,
    *,
    image_b64_list: Optional[Sequence[str]] = None,
    image_files: Optional[Sequence] = None,
    image_urls: Optional[Sequence[str]] = None,
    max_images: int = 4,
) -> List[Dict]:
    """تبدیل تصاویر به فرمت مورد انتظار Chat Completions.

    اگر `text` رشتهٔ خالی باشد، فقط تصاویر ارسال می‌شوند.
    """
    parts: List[Dict] = []
    count = 0

    # Base64 strings ---------------------------------------------------------
    if image_b64_list:
        for b64 in image_b64_list:
            if count >= max_images:
                break
            if not b64.startswith("data:"):
                b64 = f"data:image/jpeg;base64,{b64}"
            parts.append({"type": "image_url", "image_url": {"url": b64}})
            count += 1

    # Uploaded files ---------------------------------------------------------
    if image_files:
        for f in image_files:
            if count >= max_images:
                break
            data = f.read()
            mime = getattr(f, "content_type", None) or _guess_mime(getattr(f, "name", ""))
            parts.append({"type": "image_url", "image_url": {"url": _to_data_url(data, mime)}})
            count += 1

    # Remote URLs ------------------------------------------------------------
    if image_urls:
        for url in image_urls:
            if count >= max_images:
                break
            try:
                r = requests.get(url, timeout=20)
                if r.ok:
                    mime = _guess_mime(url)
                    parts.append({"type": "image_url", "image_url": {"url": _to_data_url(r.content, mime)}})
                    count += 1
            except requests.RequestException:
                continue

    parts.append({"type": "text", "text": text or ""})
    return parts

# ---------------------------------------------------------------------------
# توابع کمکی دیتابیس / جلسه
# ---------------------------------------------------------------------------

def _get_or_create_open_session(user) -> ChatSession:
    session = ChatSession.objects.filter(user=user, is_open=True).order_by("-started_at").first()
    if session:
        return session
    return ChatSession.objects.create(user=user)


def _get_recent_history(session: ChatSession, max_len: int) -> List[Dict]:
    recent = session.messages.order_by("-created_at")[:max_len]
    return [{"role": "assistant" if m.is_bot else "user", "content": m.message} for m in reversed(recent)]

# ---------------------------------------------------------------------------
# مرحلهٔ Vision (اختیاری)
# ---------------------------------------------------------------------------

def _call_vision(image_parts: List[Dict]) -> Optional[str]:
    """ارسال تصاویر برای مدل Vision و دریافت تفسیر."""
    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {"role": "user", "content": image_parts},
    ]
    payload = {"model": VISION_MODEL, "messages": messages, "max-token": MAX_TOKEN}
    res = _safe_post(TALKBOT_ENDPOINT, payload)
    if not res:
        return None
    return _remove_repeated(res["choices"][0]["message"]["content"])

# ---------------------------------------------------------------------------
# تابع اصلی
# ---------------------------------------------------------------------------

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
    """پاسخ نهایی چت‌بات را برمی‌گرداند.

    Pipeline:
        1. مدیریت/ایجاد جلسه.
        2. اگر تصویر وجود داشته باشد (و force_model خالی باشد): فراخوانی Vision.
        3. اسمبل پیام‌ها و فراخوانی مدل متنی.
        4. ذخیرهٔ پیام‌ها در دیتابیس.
    """
    # 1) Session -------------------------------------------------------------
    if new_session:
        ChatSession.objects.filter(user=request_user, is_open=True).update(is_open=False)
        session = ChatSession.objects.create(user=request_user)
    else:
        session = _get_or_create_open_session(request_user)

    # Summaries --------------------------------------------------------------
    global_sum = get_or_create_global_summary(request_user)
    session_sum = get_or_update_session_summary(session)
    history = _get_recent_history(session, max_history_length)

    # 2) Vision phase --------------------------------------------------------
    has_images = bool(image_b64_list or image_files or image_urls)
    vision_output: Optional[str] = None

    if has_images and force_model is None:
        image_parts = _build_user_content_with_images(
            "",  # متن خالی؛ فقط تصویر
            image_b64_list=image_b64_list,
            image_files=image_files,
            image_urls=image_urls,
        )
        vision_output = _call_vision(image_parts)

    # 3) Assemble messages for text model -----------------------------------
    messages: List[Dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "[GLOBAL SUMMARY]\n" + global_sum.rewritten_text},
        {"role": "system", "content": "[SESSION SUMMARY]\n" + session_sum.rewritten_text},
    ] + history

    if vision_output:
        messages.append({"role": "assistant", "content": "[VISION OUTPUT]\n" + vision_output})

    messages.append({"role": "user", "content": user_message or ""})

    model_to_use = force_model or TALKBOT_MODEL
    payload = {"model": model_to_use, "messages": messages, "max-token": MAX_TOKEN}
    resp = _safe_post(TALKBOT_ENDPOINT, payload)
    if not resp:
        return "🤔 ارتباط با سرور TalkBot برقرار نشد؛ لطفاً بعداً دوباره تلاش کنید."

    bot_msg = _remove_repeated(resp["choices"][0]["message"]["content"])

    # 4) Save messages atomically -------------------------------------------
    with transaction.atomic():
        ChatMessage.objects.bulk_create([
            ChatMessage(session=session, user=request_user, message=user_message or "", is_bot=False),
            ChatMessage(session=session, user=request_user, message=bot_msg, is_bot=True),
        ])

    return clean_bot_message(bot_msg)
