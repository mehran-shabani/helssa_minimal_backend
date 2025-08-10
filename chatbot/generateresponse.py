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
import io
import json
import logging
import mimetypes
import re
import time
from typing import Dict, List, Optional, Sequence, Tuple

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

# =============================================================================
# TalkBot API
# =============================================================================
TALKBOT_BASE_URL = "https://api.talkbot.ir"
TALKBOT_ENDPOINT = f"{TALKBOT_BASE_URL}/v1/chat/completions"
TALKBOT_API_KEY = getattr(settings, "TALKBOT_API_KEY", None)

# کلید سقف توکن (سرویس شما ظاهراً از "max-token" استفاده می‌کند)
MAX_TOKENS_KEY = getattr(settings, "TALKBOT_MAX_TOKENS_KEY", "max-token")

# فقط همین مدل (طبق درخواست شما)
VISION_MODEL = "gpt-4-vision-preview"

# سقف توکن پاسخ
MAX_TOKEN = 1500

# timeoutها
TIMEOUT_CONNECT = 4   # ثانیه
TIMEOUT_READ = 20     # ثانیه

# =============================================================================
# System / summaries
# =============================================================================
SYSTEM_PROMPT = (
    "شما یک پزشک با تجربه هستید. علائم بیمار را بررسی و تشخیص و درمان مناسب ارائه کنید. "
    "همیشه پاسخ نهایی را به زبان فارسی و به‌صورت دقیق و مختصر ارائه کن.اگر نیاز به توصیه پزشک به بیمار داشتی بهش پیشنهاد بده که میتونه از طریق اپلیکیشن هلسا و در قسمت ویزیت ویزیت خودش رو ثبت کنه و مزیت اون اینه که پزشک با شرح حال کامل و تفسیر هایه موجود در همین اپلیکیشن میتونه بهترین نتیجه رو بگیره"
)
MIN_SUMMARY_LEN = 30

_REPEAT_WORDS = re.compile(
    r"(\b[\u0600-\u06FF\w]{2,30}\b(?:\s+|$))(?:\1){2,}",
    re.IGNORECASE,
)

# =============================================================================
# Image constraints & payload budget
# =============================================================================
MAX_IMAGES = 4
MAX_IMAGE_MEGAPIXELS = 3.0               # پاس اول: ≤ ۳MP
MAX_IMAGE_BYTES_TARGET = 1_200_000       # ~1.2MB خروجی JPEG

# پاس دوم (fallback شدید):
MAX_IMAGES_FALLBACK = 1
MAX_IMAGE_MEGAPIXELS_FALLBACK = 2.0
MAX_IMAGE_BYTES_TARGET_FALLBACK = 900_000

# بودجهٔ تقریبی کل JSON (برای جلوگیری از قطع اتصال توسط پراکسی/سرور)
MAX_PAYLOAD_BYTES = 2_400_000

# URLها را دانلود نکن؛ مستقیم پاس بده (در صورت پشتیبانی سرویس)
DOWNLOAD_REMOTE_IMAGES = False
ALLOW_HEIC = True  # اگر pillow_heif نصب باشد

# =============================================================================
# HTTP session pooling
# =============================================================================
_http_session: Optional[requests.Session] = None

def _get_http_session() -> requests.Session:
    global _http_session
    if _http_session is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=0)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            "Authorization": f"Bearer {TALKBOT_API_KEY}" if TALKBOT_API_KEY else "",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "MedChat/1.0 (+Django)",
        })
        _http_session = s
    return _http_session

# =============================================================================
# Network helpers
# =============================================================================
def _post_once(
    session: requests.Session,
    url: str,
    payload: Dict,
    *,
    connection_close: bool = False,
) -> Optional[requests.Response]:
    headers = {}
    if connection_close:
        headers["Connection"] = "close"
    try:
        return session.post(
            url,
            json=payload,
            headers=headers or None,
            timeout=(TIMEOUT_CONNECT, TIMEOUT_READ),
        )
    except requests.RequestException as exc:
        logger.warning("TalkBot request exception: %s: %s", exc.__class__.__name__, exc)
        return None

def _safe_post(url: str, payload: Dict) -> Optional[Dict]:
    """
    تلاش 1: keep-alive
    تلاش 2: Connection: close
    4xx => بدون retry
    """
    session = _get_http_session()

    resp = _post_once(session, url, payload, connection_close=False)
    if resp is not None:
        if resp.ok:
            try:
                return resp.json()
            except Exception as exc:
                logger.error("TalkBot JSON parse error: %s | body[:200]=%s", exc, (resp.text or "")[:200])
                return None
        logger.warning("TalkBot status=%s body[:200]=%s", getattr(resp, "status_code", "?"), (resp.text or "")[:200])
        if 400 <= resp.status_code < 500:
            return None

    time.sleep(0.1)
    resp2 = _post_once(session, url, payload, connection_close=True)
    if resp2 is not None and resp2.ok:
        try:
            return resp2.json()
        except Exception as exc:
            logger.error("TalkBot JSON parse error (fallback): %s", exc)
            return None
    return None

# =============================================================================
# Utils
# =============================================================================
def _ensure_text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return str(x)

def _remove_repeated(text: str) -> str:
    text = _ensure_text(text)
    try:
        return _REPEAT_WORDS.sub(r"\1", text)
    except Exception:
        return text

def _extract_assistant_text(resp: dict) -> str:
    """
    content ممکن است رشته یا آرایهٔ قطعات باشد.
    """
    try:
        msg = resp["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        pieces: List[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text")
                if isinstance(t, str) and t.strip():
                    pieces.append(t.strip())
        return "\n".join(pieces).strip()
    for alt in ("text", "answer"):
        v = msg.get(alt)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _guess_mime(name: str) -> str:
    mime, _ = mimetypes.guess_type(name)
    return mime or "image/jpeg"

def _to_data_url(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode()
    return f"data:{mime};base64,{encoded}"

def _payload_size_bytes(payload: Dict) -> int:
    try:
        return len(json.dumps(payload, ensure_ascii=False))
    except Exception:
        return 0

# =============================================================================
# Image processing (downscale + compress, HEIC optional)
# =============================================================================
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

def _process_image_to_budget(data: bytes, mime: str, *, target_mp: float, target_bytes: int) -> Tuple[bytes, str]:
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
            for _ in range(6):
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
    """پیام چندرسانه‌ای کاربر برای Vision (عکس‌ها + متن)."""
    parts: List[Dict] = []
    count = 0

    # Base64s
    if image_b64_list:
        for b64 in image_b64_list:
            if count >= max_images:
                break
            if not isinstance(b64, str) or not b64.strip():
                continue
            raw = _b64_to_bytes(b64)
            if raw is None:
                if not b64.startswith("data:"):
                    b64 = f"data:image/jpeg;base64,{b64}"
                parts.append({"type": "image_url", "image_url": {"url": b64}})
            else:
                data, mime = _process_image_to_budget(raw, "image/jpeg", target_mp=target_mp, target_bytes=target_bytes)
                parts.append({"type": "image_url", "image_url": {"url": _to_data_url(data, mime)}})
            count += 1

    # Uploaded files
    if image_files:
        for f in image_files:
            if count >= max_images:
                break
            try:
                data = f.read()
            except Exception:
                continue
            mime = getattr(f, "content_type", None) or _guess_mime(getattr(f, "name", ""))
            data, mime = _process_image_to_budget(data, mime, target_mp=target_mp, target_bytes=target_bytes)
            parts.append({"type": "image_url", "image_url": {"url": _to_data_url(data, mime)}})
            count += 1

    # Remote URLs
    if image_urls:
        for url in image_urls:
            if count >= max_images:
                break
            if not isinstance(url, str) or not url.strip():
                continue
            if DOWNLOAD_REMOTE_IMAGES:
                try:
                    r = _get_http_session().get(url, timeout=(TIMEOUT_CONNECT, 8))
                    if r.ok:
                        mime = _guess_mime(url)
                        data, mime = _process_image_to_budget(r.content, mime, target_mp=target_mp, target_bytes=target_bytes)
                        parts.append({"type": "image_url", "image_url": {"url": _to_data_url(data, mime)}})
                        count += 1
                except requests.RequestException:
                    continue
            else:
                parts.append({"type": "image_url", "image_url": {"url": url.strip()}})
                count += 1

    # متن کاربر
    parts.append({"type": "text", "text": _ensure_text(text)})
    return parts

# =============================================================================
# DB helpers
# =============================================================================
def _get_or_create_open_session(user) -> ChatSession:
    session = ChatSession.objects.filter(user=user, is_open=True).order_by("-started_at").first()
    if session:
        return session
    return ChatSession.objects.create(user=user)

def _get_recent_history(session: ChatSession, max_len: int) -> List[Dict]:
    recent = session.messages.order_by("-created_at")[:max_len]
    return [{"role": "assistant" if m.is_bot else "user", "content": _ensure_text(m.message)} for m in reversed(recent)]

def _summary_or_self(obj) -> str:
    txt = _ensure_text(getattr(obj, "rewritten_text", "")).strip()
    if len(txt) >= MIN_SUMMARY_LEN:
        return txt
    for k in ("original_text", "source_text", "raw_text", "text", "content"):
        v = _ensure_text(getattr(obj, k, "")).strip()
        if v:
            return v
    return ""

# =============================================================================
# Main
# =============================================================================
def generate_gpt_response(
    request_user,
    user_message: str | None,
    *,
    new_session: bool = False,
    image_b64_list: Optional[Sequence[str]] = None,
    image_files: Optional[Sequence] = None,
    image_urls: Optional[Sequence[str]] = None,
    max_history_length: int = 5,
    force_model: Optional[str] = None,  # برای سازگاری با ویو؛ نادیده گرفته می‌شود
) -> str:
    """Vision-only: عکس + متن به Vision؛ بدون OCR؛ با فشرده‌سازی تصویر و فالبک شبکه."""
    try:
        if not TALKBOT_API_KEY:
            logger.error("TALKBOT_API_KEY is missing in settings.")
            return "⚠️ پیکربندی سرور کامل نیست (API Key). لطفاً با پشتیبانی تماس بگیرید."

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

        # Messages base
        messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        gtxt = _summary_or_self(global_sum)
        if gtxt:
            messages.append({"role": "system", "content": "[GLOBAL SUMMARY]\n" + gtxt})
        stxt = _summary_or_self(session_sum)
        if stxt:
            messages.append({"role": "system", "content": "[SESSION SUMMARY]\n" + stxt})

        # Build user message
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

        payload: Dict = {"model": VISION_MODEL, "messages": messages_with_user, MAX_TOKENS_KEY: MAX_TOKEN}

        # اگر payload خیلی بزرگ شد و عکس داریم، نسخهٔ compact بسازیم
        if has_images and _payload_size_bytes(payload) > MAX_PAYLOAD_BYTES:
            logger.warning("Payload too large; rebuilding with compact image settings.")
            compact_user = _build_user_content_with_images(
                user_message or "",
                image_b64_list=image_b64_list,
                image_files=image_files,
                image_urls=image_urls,
                max_images=MAX_IMAGES_FALLBACK,
                target_mp=MAX_IMAGE_MEGAPIXELS_FALLBACK,
                target_bytes=MAX_IMAGE_BYTES_TARGET_FALLBACK,
            )
            messages_with_user = messages + [{"role": "user", "content": compact_user}]
            payload = {"model": VISION_MODEL, "messages": messages_with_user, MAX_TOKENS_KEY: MAX_TOKEN}

        # Call TalkBot (با fallback شبکه)
        resp = _safe_post(TALKBOT_ENDPOINT, payload)

        # اگر باز هم None بود و عکس داشتیم، ultra-compact تلاش کن
        if not resp and has_images:
            logger.warning("Retrying with ultra-compact payload (1 image, 2MP, 900KB, Connection: close).")
            tiny_user = _build_user_content_with_images(
                user_message or "",
                image_b64_list=image_b64_list,
                image_files=image_files,
                image_urls=image_urls,
                max_images=1,
                target_mp=2.0,
                target_bytes=900_000,
            )
            tiny_messages = messages + [{"role": "user", "content": tiny_user}]
            payload = {"model": VISION_MODEL, "messages": tiny_messages, MAX_TOKENS_KEY: MAX_TOKEN}
            # یک بار مستقیم با Connection: close
            s = requests.Session()
            s.headers.update({
                "Authorization": f"Bearer {TALKBOT_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Connection": "close",
            })
            try:
                r = s.post(TALKBOT_ENDPOINT, json=payload, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ))
                if r.ok:
                    resp = r.json()
            except requests.RequestException as exc:
                logger.warning("Ultra-compact attempt failed: %s", exc)

        if not resp:
            return "🤔 سرویس پاسخ‌گو در حال حاضر در دسترس نیست یا به ورودی تصویر پاسخ نداد. لطفاً کمی بعد دوباره تلاش کنید."

        bot_msg = _extract_assistant_text(resp)
        if not bot_msg:
            logger.error("Empty/unknown response structure: %s", str(resp)[:500])
            return "🤔 پاسخ نامعتبر از TalkBot دریافت شد."

        bot_msg = _remove_repeated(_ensure_text(bot_msg))

        # Save messages
        try:
            with transaction.atomic():
                ChatMessage.objects.bulk_create([
                    ChatMessage(session=session, user=request_user, message=_ensure_text(user_message), is_bot=False),
                    ChatMessage(session=session, user=request_user, message=bot_msg, is_bot=True),
                ])
        except Exception as exc:
            logger.exception("DB save failed: %s", exc)

        return clean_bot_message(bot_msg)

    except Exception as exc:
        logger.exception("generate_gpt_response crashed: %s", exc)
        return "❗ خطای غیرمنتظره‌ای رخ داد. لطفاً دوباره تلاش کنید."