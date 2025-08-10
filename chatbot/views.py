# chatbot/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from chatbot.permissions import HasActiveSubscription

import json

from chatbot.generateresponse import generate_gpt_response


class ChatView(APIView):
    """دریافت پیام کاربر و برگرداندن پاسخ چت‌بات."""

    permission_classes = [IsAuthenticated, HasActiveSubscription]

    def post(self, request):  # noqa: C901 – ساده و سرراست
        user = request.user

        data = request.data

        # Helper: getlist که روی JSON هم کار کند
        def _getlist(key: str):
            # اگر QueryDict باشد (فرم/مالتی‌پارت)
            if hasattr(data, "getlist"):
                return data.getlist(key)
            # اگر dict معمولی (JSON) باشد
            v = data.get(key)
            if v is None:
                return []
            if isinstance(v, (list, tuple)):
                return list(v)
            return [v]

        # متن پیام (می‌تواند خالی باشد اگر صرفاً تصویر ارسال شود)
        raw_msg = (data.get("message") or "").strip()
        msg: str | None = raw_msg or None

        # شروع جلسهٔ جدید در صورت نیاز
        new_session = str(data.get("new_session", "")).lower() in ("1", "true", "yes")

        # تصاویر به‌صورت Base64:
        # پشتیبانی از کلیدهای رایج: "images", "images[]"
        b64_candidates = _getlist("images") or _getlist("images[]")
        b64_list = []
        for item in b64_candidates:
            if isinstance(item, str):
                # اگر JSON فرستاده شده باشد ممکن است رشتهٔ Base64 باشد
                b64_list.append(item)
            elif isinstance(item, dict) and "image" in item:
                # اگر ساختار [{ "image": "<b64>" }, ...] باشد
                b64_list.append(item.get("image"))

        # فایل‌های آپلودی (multipart)
        files = None
        try:
            files = request.FILES.getlist("images") or None
        except Exception:
            files = None

        # آدرس URL تکی تصویر (اختیاری) + پشتیبانی از لیست آدرس‌ها در JSON
        img_url = data.get("image_url")
        url_list = None
        if img_url:
            url_list = [img_url]
        else:
            urls = _getlist("image_urls")
            if urls:
                # در صورت ارسال آرایهٔ URLها در JSON
                url_list = [u for u in urls if isinstance(u, str) and u.strip()]

        # انتخاب مدل اجباری (اختیاری)
        force_model = data.get("force_model") or None

        # فراخوانی سرویس پاسخ‌گو
        answer = generate_gpt_response(
            request_user=user,
            user_message=msg,
            new_session=new_session,
            image_b64_list=b64_list or None,
            image_files=files,
            image_urls=url_list,
            force_model=force_model,
        )

        return Response({"answer": answer}, status=status.HTTP_200_OK)
