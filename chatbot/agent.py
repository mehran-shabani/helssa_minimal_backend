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

# -------------------- Visit creation tool --------------------
from django.db import transaction
from chatbot.utils import text_summary as ts
from telemedicine.models import Visit, BoxMoney

def _map_symptoms_to_visit_fields(text: str) -> Dict[str, str]:
    t = (text or "").lower()
    def has_any(words: List[str]) -> bool:
        return any(w in t for w in words)
    detected = False
    general = ""
    if has_any(["تب", "fever"]):
        general = "fever"; detected = True
    elif has_any(["خستگی", "fatigue"]):
        general = "fatigue"; detected = True
    elif has_any(["کاهش وزن", "weight loss"]):
        general = "weight_loss"; detected = True
    elif has_any(["بی‌اشتهایی", "کاهش اشتها", "appetite"]):
        general = "appetite_loss"; detected = True
    elif has_any(["تعریق شبانه"]):
        general = "night_sweats"; detected = True
    # اگر هیچ‌کدام از عمومی‌ها match نشد، بعداً fallback می‌دهیم
    neuro = ""
    if has_any(["سردرد", "migraine", "headache"]):
        neuro = "headache"; detected = True
    elif has_any(["سرگیجه", "dizzy"]):
        neuro = "dizziness"; detected = True
    elif has_any(["تشنج", "seizure"]):
        neuro = "seizures"; detected = True
    elif has_any(["بی‌حسی", "numb"]):
        neuro = "numbness"; detected = True
    elif has_any(["ضعف"]):
        neuro = "weakness"; detected = True
    cardio = ""
    if has_any(["قفسه سینه", "chest pain"]):
        cardio = "chest_pain"; detected = True
    elif has_any(["تپش", "palpitation"]):
        cardio = "palpitations"; detected = True
    elif has_any(["فشار خون", "hypertension"]):
        cardio = "high_blood_pressure"; detected = True
    elif has_any(["غش", "بیهوشی", "faint"]):
        cardio = "fainting"; detected = True
    gi = ""
    if has_any(["تهوع", "nausea"]):
        gi = "nausea"; detected = True
    elif has_any(["استفراغ", "vomit"]):
        gi = "vomiting"; detected = True
    elif has_any(["اسهال", "diarrhea"]):
        gi = "diarrhea"; detected = True
    elif has_any(["یبوست", "constipation"]):
        gi = "constipation"; detected = True
    elif has_any(["درد شکم", "abdominal pain"]):
        gi = "abdominal_pain"; detected = True
    resp = ""
    if has_any(["سرفه", "cough"]):
        resp = "cough"; detected = True
    elif has_any(["تنگی نفس", "shortness of breath"]):
        resp = "shortness_of_breath"; detected = True
    elif has_any(["خس خس", "wheeze"]):
        resp = "wheezing"; detected = True
    elif has_any(["گلودرد", "sore throat"]):
        resp = "sore_throat"; detected = True
    urgency = "online_consultation"
    if has_any(["اعتیاد", "戒", "ترک"]):
        urgency = "addiction"; detected = True
    elif has_any(["رژیم", "diet"]):
        urgency = "diet"; detected = True
    elif has_any(["نسخه", "renew", "داروهای پر مصرف"]):
        urgency = "prescription"; detected = True
    return {
        "detected": bool(detected),
        "urgency": urgency,
        "general_symptoms": general or "general_pain",
        "neurological_symptoms": neuro,
        "cardiovascular_symptoms": cardio,
        "gastrointestinal_symptoms": gi,
        "respiratory_symptoms": resp,
    }

@register_tool(
    "create_visit_from_summary",
    "ایجاد ویزیت خودکار بر اساس شرح‌حال مکالمهٔ جاری. فقط وقتی اجرا می‌شود که بتوان علائم را تشخیص داد؛ سپس هزینه از کیف‌پول کسر و ویزیت ثبت می‌شود.",
    {"type":"object","properties":{
        "name":{"type":"string","description":"عنوان اختیاری ویزیت"},
        "notes":{"type":"string","description":"یادداشت اختیاری برای توضیحات"},
        "max_cost":{"type":"integer","description":"حداکثر هزینهٔ مجاز برای کسر از کیف‌پول","default":398000}
    }}
)
def tool_create_visit_from_summary(args, user_id, session: ChatSession):
    name = (args or {}).get("name") or "ویزیت خودکار"
    notes = (args or {}).get("notes") or ""
    max_cost = int((args or {}).get("max_cost") or 398000)
    try:
        summary = ts.get_or_update_session_summary(session)
        text = (getattr(summary, "rewritten_text", "") or "").strip()
        fields = _map_symptoms_to_visit_fields(text)
        if not fields.get("detected"):
            return {"ok": False, "error": "insufficient_data"}
        with transaction.atomic():
            # کیف پول در سیگنال ایجاد کاربر ساخته می‌شود؛ در غیر این صورت get_or_create
            box, _ = BoxMoney.objects.select_for_update().get_or_create(user_id=user_id, defaults={"amount": 0})
            if box.amount < max_cost:
                return {"ok": False, "error": "insufficient_funds", "balance": box.amount, "needed": max_cost}
            box.amount -= max_cost
            box.save(update_fields=["amount"])
            v = Visit.objects.create(
                user_id=user_id,
                name=name,
                urgency=fields["urgency"],
                general_symptoms=fields["general_symptoms"],
                neurological_symptoms=fields["neurological_symptoms"],
                cardiovascular_symptoms=fields["cardiovascular_symptoms"],
                gastrointestinal_symptoms=fields["gastrointestinal_symptoms"],
                respiratory_symptoms=fields["respiratory_symptoms"],
                description=(text[:900] + ("\n\n" + notes if notes else ""))[:1200],
            )
            return {
                "ok": True,
                "visit_id": v.id,
                "cost_deducted": max_cost,
                "visit": {
                    "name": v.name,
                    "urgency": v.urgency,
                    "general_symptoms": v.general_symptoms,
                    "neurological_symptoms": v.neurological_symptoms,
                    "cardiovascular_symptoms": v.cardiovascular_symptoms,
                    "gastrointestinal_symptoms": v.gastrointestinal_symptoms,
                    "respiratory_symptoms": v.respiratory_symptoms,
                    "description": v.description,
                },
            }
    except Exception as e:
        logger.exception("create_visit_from_summary failed: %s", e)
        return {"ok": False, "error": "internal_error", "detail": str(e)}

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
