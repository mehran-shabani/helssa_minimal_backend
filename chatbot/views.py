from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from chatbot.permissions import HasActiveSubscription
from chatbot.generateresponse import generate_gpt_response
from chatbot.utils.text_summary import get_or_create_global_summary, get_or_update_session_summary
from chatbot.models import ChatSession

logger = logging.getLogger(__name__)

class ChatView(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    def post(self, request):
        caps_err = getattr(request, "_caps_error", None)
        if caps_err:
            return Response({"detail": caps_err.get("reason", "محدودیت پلن.")}, status=402)

        data = request.data
        def _getlist(key: str):
            if hasattr(data, "getlist"):
                try:
                    lst = data.getlist(key)
                    if lst:
                        return lst
                except Exception:
                    pass
            v = data.get(key)
            if v is None:
                return []
            if isinstance(v, (list, tuple)):
                return list(v)
            return [v]

        msg = (data.get("message") or "").strip() or None
        new_session = str(data.get("new_session", "")).lower() in ("1", "true", "yes")

        b64_list = _getlist("images") or _getlist("images[]")
        try:
            files = request.FILES.getlist("images") or None
        except Exception:
            files = None
        url_list = []
        if data.get("image_url"):
            url_list = [data.get("image_url")]
        else:
            urls = _getlist("image_urls")
            url_list = [u for u in urls if isinstance(u, str) and u.strip()]

        specialty = data.get("specialty") or None
        force_model = data.get("force_model") or None
        caps = getattr(request, "_caps", {})

        answer = generate_gpt_response(
            request_user=request.user,
            user_message=msg,
            new_session=new_session,
            image_b64_list=b64_list or None,
            image_files=files,
            image_urls=url_list or None,
            force_model=force_model,
            max_tokens_override=caps.get("max_tokens"),
            max_images_override=caps.get("max_images"),
            tool_whitelist=caps.get("tool_whitelist"),
            specialty_code=specialty if specialty in (caps.get("allowed_specialties") or []) else None,
        )

        try:
            session = ChatSession.objects.filter(user=request.user).order_by("-started_at").first()
            sid = session.id if session else None
        except Exception:
            sid = None
        return Response({"answer": answer, "session_id": sid}, status=status.HTTP_200_OK)

class SummaryView(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]
    def get(self, request):
        user = request.user
        sid = request.query_params.get("session_id")
        if sid:
            s = ChatSession.objects.filter(id=sid, user=user).first()
            if not s:
                return Response({"detail":"جلسه پیدا نشد."}, status=404)
            sm = get_or_update_session_summary(s)
        else:
            sm = get_or_create_global_summary(user)
        return Response({
            "id": sm.id,
            "scope": "session" if sm.session_id else "global",
            "model": sm.model_used,
            "rewritten": sm.rewritten_text,
            "structured": sm.structured_json,
            "updated_at": sm.updated_at,
        })
