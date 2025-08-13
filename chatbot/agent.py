from __future__ import annotations
import json
import logging
from typing import Dict, List, Optional, Tuple, Callable

import requests
from django.conf import settings
from chatbot.models import ChatSession, ToolCallLog

logger = logging.getLogger(__name__)

ENDPOINT = f"{settings.OPENAI_BASE_URL}/chat/completions"
API_KEY = settings.OPENAI_API_KEY
MAX_TOKENS_KEY = "max_tokens"

def _headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# -------------------- Tool registry --------------------
_TOOL_REGISTRY: Dict[str, Tuple[Dict, Callable]] = {}

def register_tool(name: str, description: str, parameters: Dict):
    def decorator(func):
        _TOOL_REGISTRY[name] = ({"name": name, "description": description, "parameters": parameters}, func)
        return func
    return decorator

def list_tools_for_api(whitelist: Optional[List[str]] = None) -> List[Dict]:
    all_tools = [{"type":"function","function": schema} for schema, _ in _TOOL_REGISTRY.values()]
    if not whitelist:
        return all_tools
    names = set(whitelist)
    return [t for t in all_tools if (t.get("function") or {}).get("name") in names]

# -------------------- Basic tools --------------------
@register_tool(
    "triage_level", "ارزیابی سطح فوریت علائم بیمار (کم/متوسط/زیاد).",
    {"type":"object","properties":{"symptoms":{"type":"string"}}, "required":["symptoms"]}
)
def tool_triage(args, user_id, session: ChatSession):
    s = (args or {}).get("symptoms","")
    lvl = "کم"
    s_low = s.lower()
    if any(k in s_low for k in ["درد قفسه سینه","تنگی نفس","بی‌حسی نیمه بدن","کاهش هوشیاری","خونریزی شدید"]):
        lvl = "زیاد"
    elif any(k in s_low for k in ["تب بالا","تهوع مداوم","سردرد شدید","درد مداوم"]):
        lvl = "متوسط"
    return {"triage": lvl}

@register_tool(
    "get_patient_profile", "دریافت پروفایل مختصر بیمار (سن/جنس/حساسیت/بیماری‌ها).",
    {"type":"object","properties":{}}
)
def tool_get_profile(args, user_id, session: ChatSession):
    return {"age": None, "sex": None, "allergies": [], "conditions": []}

@register_tool(
    "update_patient_profile", "به‌روزرسانی پروفایل بیمار.",
    {"type":"object","properties":{"age":{"type":"integer"},"sex":{"type":"string"},"allergies":{"type":"array","items":{"type":"string"}},"conditions":{"type":"array","items":{"type":"string"}}}}
)
def tool_update_profile(args, user_id, session: ChatSession):
    return {"ok": True, "saved": args or {}}

# -------------------- Helpers --------------------
def _extract_text(msg: Dict) -> str:
    if not isinstance(msg, dict):
        return ""
    c = msg.get("content")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        parts = []
        for p in c:
            if isinstance(p, dict) and p.get("type") == "text":
                t = p.get("text")
                if isinstance(t, str) and t.strip():
                    parts.append(t.strip())
        return "\n".join(parts).strip()
    return ""

# -------------------- Agent main --------------------
def agent_chat(*, user_id: int, session: ChatSession, messages: List[Dict], model: str, max_tokens: int, temperature: float=0.2, max_steps: int=3, tool_whitelist: Optional[List[str]] = None, specialty_code: Optional[str] = None) -> str:
    if not API_KEY:
        logger.error("Agent: API key missing.")
        return "⚠️ تنظیمات کلید API خالی است."

    tools = list_tools_for_api(tool_whitelist)
    local = list(messages)
    for _ in range(max_steps):
        payload = {
            "model": model,
            "messages": local,
            MAX_TOKENS_KEY: max_tokens,
            "temperature": temperature,
            "tool_choice": "auto" if tools else "none",
            "tools": tools if tools else None,
        }
        try:
            r = requests.post(ENDPOINT, data=json.dumps(payload), headers=_headers(), timeout=(settings.OPENAI_TIMEOUT_CONNECT, settings.OPENAI_TIMEOUT_READ))
        except requests.RequestException as e:
            logger.warning("Agent request failed: %s", e)
            return "🤔 سرویس موقتا در دسترس نیست."
        if not r.ok:
            logger.warning("Agent http %s: %s", r.status_code, r.text[:200])
            return "🤔 پاسخ نامعتبر از سرویس دریافت شد."

        data = r.json() or {}
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        tool_calls = msg.get("tool_calls") or []

        if tool_calls:
            for call in tool_calls:
                fn = (call or {}).get("function") or {}
                name = fn.get("name", "")
                args = fn.get("arguments")
                try:
                    args = json.loads(args) if isinstance(args, str) else (args or {})
                except Exception:
                    args = {}
                schema_handler = _TOOL_REGISTRY.get(name)
                if schema_handler:
                    _schema, handler = schema_handler
                    try:
                        result = handler(args, user_id, session)
                    except Exception as e:
                        logger.exception("Tool %s crashed: %s", name, e)
                        result = {"error": "tool_failed", "detail": str(e)}
                else:
                    result = {"error": f"unknown_tool:{name}"}
                try:
                    ToolCallLog.objects.create(user_id=user_id, session=session, name=name or "", arguments=args, result=result)
                except Exception:
                    pass
                local.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue

        text = _extract_text(msg)
        if text:
            return text
        local.append({"role": "assistant", "content": ""})

    return "⚠️ فرایند چندمرحله‌ای کامل نشد."
