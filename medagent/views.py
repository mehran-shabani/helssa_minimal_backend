# medagent/views.py
"""
REST-API views for patient-side MedAgent.
Permissions:
    • IsAuthenticated
    • HasActiveSubscription   (کاربر باید اشتراک فعال داشته باشد)

Endpoints
---------
POST   /session/create/                → ایجاد جلسه
POST   /session/<id>/message/          → پیام متنی یا تصویر Base64
PATCH  /session/end/                   → پایان جلسه + خلاصه‌سازی
GET    /session/<id>/summary/medical/  → خلاصهٔ ساختارمند پزشکی
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView

from medagent.models import ChatMessage, ChatSession, PatientSummary, RunningSessionSummary
from medagent.permissions import HasActiveSubscription
from medagent.serializers import (
    ChatMessageSerializer,
    CreateSessionSerializer,
    EndSessionSerializer,
)
from medagent.talkbot_client import tb_chat, vision_analyze
from medagent.tools import UpdateRunningSummaryTool

logger = logging.getLogger(__name__)


# ---------- 1) ایجاد جلسه ----------
class CreateSession(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    def post(self, request):
        ser = CreateSessionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        session = ChatSession.objects.create(
            patient=request.user,
            name=ser.validated_data.get("name", ""),
        )
        return Response({"session_id": session.id}, status=201)


# ---------- ارسال پیام ----------
class PostMessage(CreateAPIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]
    serializer_class= [ChatMessageSerializer]

    def post(self, request):
        user = request.user
        data = request.data
        session_id = data['session_id']
        session = get_object_or_404(ChatSession, id=session_id)
        payload: Any = request.data['content']

        # 1) ذخیره پیام کاربر
        ChatMessage.objects.create(session=session, role="patient", content=payload)

        rs = RunningSessionSummary.objects.get(session=session)
        ps = PatientSummary.objects.get(patient=user)
        js = ps.json_summary
        ts = ps.text_summary
        if ps & rs:
            
            patient_ctx = {
                "role": "system",
                "content": f"Patient history JSON:\n{json.dumps(js, ensure_ascii=False) if PatientSummary else '{}'}",
            }
            
            running_ctx = {
                "role": "system",
                "content": f"Running session summary JSON:\n{json.dumps(ts, ensure_ascii=False) or '{}'}",
                }
            user_msg = {"role": "user", "content": payload}

        if ps and not rs:


        # 3) پاسخ
        if isinstance(payload, dict) and "image" in payload:
            img = payload["image"]
            prompt = payload.get("prompt", "")
            reply = vision_analyze(image=img, prompt=prompt)
        else:
            reply = tb_chat([patient_ctx, running_ctx, user_msg], model="o3-mini")

        # 4) ذخیره پاسخ
        ChatMessage.objects.create(session=session, role="assistant", content=reply)

        # 5) به‌روزرسانی خلاصه زنده
        UpdateRunningSummaryTool()._run(str(session.id), reply)

        return Response({"assistant_reply": reply}, status=201)


# ---------- پایان جلسه ----------
class EndSession(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    def patch(self, request):
        ser = EndSessionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        session = get_object_or_404(
            ChatSession,
            id=ser.validated_data["session_id"],
            patient=request.user,
            ended_at__isnull=True,
        )
        session.ended_at = timezone.now()
        session.save(update_fields=["ended_at"])

        # خلاصه زنده دیگر نیاز نیست
        RunningSessionSummary.objects.filter(session=session).delete()

        return Response({"msg": "session closed"}, status=200)


# ---------- 4. خلاصهٔ پزشکی ساختارمند ----------
class GetMedicalSummary(APIView):
    """
    خروجی به‌صورت JSON مطابق الگوی استاندارد SOAP:
        {
          "subjective": "... (chief complaint + HPI)",
          "objective":  "... (findings / vitals)",
          "assessment": "... (impression / diagnosis)",
          "plan":       "... (recommendations / Rx / follow-up)"
        }
    این نما هیچ دادهٔ متنی آزاد دیگری برنمی‌گرداند تا فرانت بتواند
    مستقیماً هر بخش را در UI مناسب (مثل Accordion یا Tab) رندر کند.
    """
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    def get(self, request):
        summ = get_object_or_404(
            PatientSummary,
            patient=request.user
        )

        # اگر JSON از TalkBot دقیقاً قالب را برگردانده است:
        template = self._normalize_summary(summ.json_summary)
        return Response(template)

    # ---------- helpers ----------
    def _normalize_summary(self, src: Dict[str, Any]) -> Dict[str, str]:
        keys = ("subjective", "objective", "assessment", "plan")
        if all(k in src for k in keys):
            return {k: str(src.get(k, "")).strip() for k in keys}
        return {k: src.get(k, "") for k in keys}
