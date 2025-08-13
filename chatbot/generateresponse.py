from __future__ import annotations
import base64, io, json, logging, mimetypes, random, re, time
from typing import Dict, List, Optional, Sequence, Tuple
import requests
from django.conf import settings
from django.db import transaction
from chatbot.models import ChatMessage, ChatSession
from chatbot.cleaner import clean_bot_message
from chatbot.utils.text_summary import get_or_create_global_summary, get_or_update_session_summary
from chatbot.agent import agent_chat

logger = logging.getLogger(__name__)

# مدل‌ها
TEXT_MODEL = settings.CHAT_MODEL_TEXT
VISION_MODEL = settings.CHAT_MODEL_VISION
MAX_TOKEN = int(getattr(settings, "OPENAI_MAX_TOKENS", 1500))
MAX_TOKENS_KEY = "max_tokens"

# حدود پیام/تصویر
MAX_IMAGES = 4
MAX_IMAGE_MEGAPIXELS = 3.0
MAX_IMAGE_BYTES_TARGET = 1_200_000
MAX_PAYLOAD_BYTES = 2_400_000

# Timeout ها
TIMEOUT_CONNECT = settings.OPENAI_TIMEOUT_CONNECT
TIMEOUT_READ = settings.OPENAI_TIMEOUT_READ

# ——— Utilities ———
def _json_dumps(obj: Dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

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
    return s[: max_chars - 10] + "…"

_REPEAT_WORDS = re.compile(r"(\b[\u0600-\u06FF\w]{2,30}\b(?:\s+|$))(?:\1){2,}", re.IGNORECASE)
def _remove_repeated(text: str) -> str:
    text = _ensure_text(text)
    try:
        return _REPEAT_WORDS.sub(r"\1", text)
    except Exception:
        return text

def _extract_assistant_text(resp: dict) -> str:
    if not isinstance(resp, dict):
        return ""
    err = resp.get("error")
    if isinstance(err, dict):
        msg = err.get("message") or err.get("detail") or ""
        return f"❗ خطای سرویس: {msg}".strip()
    choices = resp.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
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

# ——— Image processing ———
_PIL_READY = False
try:
    from PIL import Image
    _PIL_READY = True
    try:
        import pillow_heif  # type: ignore
        pillow_heif.register_heif_opener()
    except Exception:
        pass
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
    im.save(buf, format="JPEG", quality=int(quality), optimize=True, progressive=True, subsampling="4:2:0")
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
    except Exception:
        return data, mime

def _b64_to_bytes(b64: str) -> Optional[bytes]:
    try:
        if b64.startswith("data:"):
            _, b64part = b64.split(",", 1)
            return base64.b64decode(b64part)
        return base64.b64decode(b64)
    except Exception:
        return None

def _guess_mime(name: str) -> str:
    mime, _ = mimetypes.guess_type(name)
    return mime or "image/jpeg"

def _to_data_url(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode()
    return f"data:{mime};base64,{encoded}"

def _build_user_content_with_images(text: str, *, image_b64_list=None, image_files=None, image_urls=None, max_images: int=MAX_IMAGES, target_mp: float=MAX_IMAGE_MEGAPIXELS, target_bytes: int=MAX_IMAGE_BYTES_TARGET) -> List[Dict]:
    parts: List[Dict] = []
    count = 0
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
                parts.append({"type":"image_url","image_url":{"url": b64}})
            else:
                data, mime = _process_image_to_budget(raw, "image/jpeg", target_mp=target_mp, target_bytes=target_bytes)
                parts.append({"type":"image_url","image_url":{"url": _to_data_url(data, mime)}})
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
            data, mime = _process_image_to_budget(data, mime, target_mp=target_mp, target_bytes=target_bytes)
            parts.append({"type":"image_url","image_url":{"url": _to_data_url(data, mime)}})
            count += 1
    if image_urls:
        for url in image_urls:
            if count >= max_images:
                break
            if not isinstance(url, str) or not url.strip():
                continue
            parts.append({"type":"image_url","image_url":{"url": url.strip()}})
            count += 1
    parts.append({"type":"text","text": _ensure_text(text)})
    return parts

# ——— DB helpers ———
def _get_or_create_open_session(user) -> ChatSession:
    s = ChatSession.objects.filter(user=user, is_open=True).order_by("-started_at").first()
    if s:
        return s
    return ChatSession.objects.create(user=user)

def _get_recent_history(session: ChatSession, max_len: int) -> List[Dict]:
    recent = session.messages.order_by("-created_at")[:max_len]
    return [{"role": "assistant" if m.is_bot else "user", "content": _ensure_text(m.message)} for m in reversed(recent)]

def _summary_text(obj) -> str:
    txt = _ensure_text(getattr(obj, "rewritten_text", "")).strip()
    if len(txt) >= 30:
        return _clip_text(txt, 2000)
    for k in ("raw_text","text","content"):
        v = _ensure_text(getattr(obj, k, "")).strip()
        if v:
            return _clip_text(v, 2000)
    return ""

# ——— Main ———
def generate_gpt_response(
    request_user,
    user_message: str | None,
    *,
    new_session: bool=False,
    image_b64_list: Optional[Sequence[str]] = None,
    image_files: Optional[Sequence] = None,
    image_urls: Optional[Sequence[str]] = None,
    max_history_length: int = 6,
    force_model: Optional[str] = None,
    # From plan caps:
    max_tokens_override: Optional[int] = None,
    max_images_override: Optional[int] = None,
    tool_whitelist: Optional[List[str]] = None,
    specialty_code: Optional[str] = None,
) -> str:
    t0 = time.monotonic()
    try:
        # Session
        if new_session:
            ChatSession.objects.filter(user=request_user, is_open=True).update(is_open=False)
            session = ChatSession.objects.create(user=request_user)
        else:
            session = _get_or_create_open_session(request_user)

        # Summaries & history
        global_sum = get_or_create_global_summary(request_user)
        session_sum = get_or_update_session_summary(session)
        history = _get_recent_history(session, max_history_length)

        base_system = "تو یک پزشک باتجربه و ایمن هستی. راهنمایی علمی و محتاطانه بده؛ از تجویز داروی نسخه‌ای خودداری کن. اگر مناسب بود، در پایان پیشنهاد ثبت ویزیت در اپ هِلسا بده."
        messages: List[Dict] = [{"role":"system","content": base_system}] + history
        gtxt = _summary_text(global_sum)
        if gtxt:
            messages.append({"role":"system","content":"[GLOBAL SUMMARY]\n"+gtxt})
        stxt = _summary_text(session_sum)
        if stxt:
            messages.append({"role":"system","content":"[SESSION SUMMARY]\n"+stxt})

        has_images = bool(image_b64_list or image_files or image_urls)
        if max_images_override is not None and has_images:
            if image_b64_list and len(image_b64_list) > max_images_override:
                image_b64_list = image_b64_list[:max_images_override]
            if image_files and len(image_files) > max_images_override:
                image_files = image_files[:max_images_override]
            if image_urls and len(image_urls) > max_images_override:
                image_urls = image_urls[:max_images_override]

        if has_images:
            user_content = _build_user_content_with_images(
                user_message or "", image_b64_list=image_b64_list, image_files=image_files, image_urls=image_urls,
                max_images=max_images_override or MAX_IMAGES
            )
            messages.append({"role":"user","content": user_content})
        else:
            if not (user_message and user_message.strip()):
                return "لطفاً متن سؤال یا تصویر را ارسال کنید."
            messages.append({"role":"user","content": user_message.strip()})

        model = force_model or (VISION_MODEL if has_images else TEXT_MODEL)
        max_tokens = max_tokens_override or MAX_TOKEN

        bot_msg = agent_chat(
            user_id=request_user.id, session=session, messages=messages,
            model=model, max_tokens=max_tokens, temperature=0.2, max_steps=3,
            tool_whitelist=tool_whitelist, specialty_code=specialty_code
        )
        bot_msg = _remove_repeated(_ensure_text(bot_msg))
        bot_msg = clean_bot_message(bot_msg or "پاسخی دریافت نشد.")

        # Save + usage
        try:
            with transaction.atomic():
                ChatMessage.objects.bulk_create([
                    ChatMessage(session=session, user=request_user, message=user_message or "", is_bot=False),
                    ChatMessage(session=session, user=request_user, message=bot_msg, is_bot=True),
                ])
                from chatbot.models import UsageLog
                UsageLog.objects.create(
                    user=request_user, session=session, model=model,
                    input_chars=sum(len((_ensure_text(m.get("content")) if isinstance(m.get("content"), str) else "")) for m in messages),
                    output_chars=len(bot_msg),
                )
        except Exception as e:
            logger.exception("DB save failed: %s", e)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info("generate_gpt_response done in %sms (has_images=%s)", elapsed_ms, has_images)
        return bot_msg

    except Exception as exc:
        logger.exception("generate_gpt_response crashed: %s", exc)
        return "❗ خطای غیرمنتظره‌ای رخ داد. لطفاً دوباره تلاش کنید."
