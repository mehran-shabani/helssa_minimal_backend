from __future__ import annotations
from typing import Dict, List, Optional
from django.utils import timezone
from django.db.models import Sum, Count
from django.conf import settings
from .models import Subscription, Plan, Specialty, SpecialtyAccess, TokenTopUp
from chatbot.models import UsageLog

CHARS_PER_TOKEN = getattr(settings, "CHARS_PER_TOKEN", 4.0)

def get_active_subscription(user) -> Optional[Subscription]:
    return (
        Subscription.objects
        .select_related("plan")
        .filter(user=user, active=True, expires_at__gt=timezone.now())
        .order_by("-expires_at")
        .first()
    )

def _today_bounds():
    now = timezone.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now

def get_today_usage(user) -> Dict[str, int]:
    start, now = _today_bounds()
    qs = UsageLog.objects.filter(user=user, created_at__gte=start, created_at__lte=now)
    agg = qs.aggregate(chars=Sum("input_chars") + Sum("output_chars"), reqs=Count("id"))
    return {"chars": int(agg.get("chars") or 0), "requests": int(agg.get("reqs") or 0)}

def get_topup_balance(user) -> int:
    return int(TokenTopUp.objects.filter(user=user).aggregate(b=Sum("char_balance"))["b"] or 0)

def get_allowed_specialties(user, plan: Plan) -> List[Specialty]:
    base = list(plan.specialties.all())
    add_ons = [a.specialty for a in SpecialtyAccess.objects.select_related("specialty").filter(
        user=user, active=True, expires_at__gt=timezone.now()
    )]
    seen = set()
    res = []
    for s in base + add_ons:
        if s.id in seen:
            continue
        seen.add(s.id)
        res.append(s)
    return res

def compute_caps_for_request(user, sub: Subscription, request) -> Dict:
    plan = sub.plan
    usage = get_today_usage(user)
    topup_chars = get_topup_balance(user)

    # سقف درخواست روزانه
    if usage["requests"] >= plan.daily_requests_limit:
        return {"ok": False, "reason": "سقف تعداد درخواست روزانهٔ پلن شما تمام شده.", "status": 402}

    # کاراکتر/توکن
    remaining_chars = max(0, plan.daily_char_limit - usage["chars"])
    available_chars = remaining_chars + topup_chars
    available_tokens_by_chars = int(available_chars / CHARS_PER_TOKEN)
    per_request_cap = min(
        getattr(settings, "OPENAI_MAX_TOKENS", 1500),
        plan.max_tokens_per_request,
        max(60, available_tokens_by_chars)
    )

    # تصاویر
    has_images = False
    try:
        data = request.data
        if (data.get("images") or data.get("images[]")):
            has_images = True
        if request.FILES.getlist("images"):
            has_images = True
        if data.get("image_url") or data.get("image_urls"):
            has_images = True
    except Exception:
        pass
    if has_images and not plan.allow_vision:
        return {"ok": False, "reason": "ارسال تصویر در پلن فعلی فعال نیست. پلن Pro یا بالاتر تهیه کنید.", "status": 402}
    max_images = plan.max_images if plan.allow_vision else 0

    # ابزارها
    if not plan.allow_agent_tools:
        tool_whitelist = []
    elif plan.code == "starter":
        tool_whitelist = ["triage_level", "get_patient_profile", "update_patient_profile"]
    else:
        tool_whitelist = None  # یعنی همهٔ ابزارهای رجیستر

    # تخصص
    specialty_code = None
    try:
        specialty_code = request.data.get("specialty") or request.query_params.get("specialty")
    except Exception:
        pass
    allowed_codes = {s.code for s in get_allowed_specialties(user, plan)}
    if specialty_code and specialty_code not in allowed_codes:
        specialty_code = None  # اجازه نده، ولی ادامه بده

    return {
        "ok": True,
        "plan": plan.code,
        "max_tokens": per_request_cap,
        "max_images": max_images,
        "tool_whitelist": tool_whitelist,
        "specialty_code": specialty_code,
        "allowed_specialties": list(allowed_codes),
    }
