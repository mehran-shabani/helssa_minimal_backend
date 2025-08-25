# chatbot/views.py
from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from django.utils.encoding import force_str
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

from chatbot.permissions import HasActiveSubscription
from chatbot.generateresponse import generate_gpt_response

logger = logging.getLogger(__name__)


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = force_str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


class ChatView(APIView):
    """
    دریافت پیام/عکس از کاربر و برگرداندن پاسخ چت‌بات.

    پشتیبانی از:
      - JSON:  { message, images: [<b64>|{image:<b64>}], image_url, image_urls: [...] }
      - Multipart:  message=..., images=@file1  (همچنین images[] پشتیبانی می‌شود)
    """
    permission_classes = [IsAuthenticated, HasActiveSubscription]
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    # ---- helpers -------------------------------------------------------------
    @staticmethod
    def _getlist(data, key: str) -> List:
        """
        مثل QueryDict.getlist کار می‌کند ولی روی dict (JSON) هم جواب می‌دهد.
        """
        try:
            if hasattr(data, "getlist"):
                vals = data.getlist(key)
                if vals:
                    return list(vals)
        except Exception:
            pass

        v = data.get(key)
        if v is None:
            return []
        if isinstance(v, (list, tuple)):
            return list(v)
        return [v]

    @staticmethod
    def _collect_b64(data) -> List[str]:
        """
        تمام مسیرهای ممکن برای دریافت base64 را تجمیع می‌کند.
        """
        b64_list: List[str] = []
        candidates: List = []

        # تصاویر در JSON: images یا images[]
        candidates += ChatView._getlist(data, "images")
        candidates += ChatView._getlist(data, "images[]")
        # برخی فرانت‌ها آبجکت می‌فرستند: {image: <b64>} یا {b64: <b64>} یا {data: <b64>}
        for item in candidates:
            if isinstance(item, str) and item.strip():
                b64_list.append(item.strip())
            elif isinstance(item, dict):
                for k in ("image", "b64", "data"):
                    val = item.get(k)
                    if isinstance(val, str) and val.strip():
                        b64_list.append(val.strip())
                        break
        return b64_list

    @staticmethod
    def _collect_urls(data) -> List[str]:
        urls: List[str] = []
        for key in ("image_url", "image_urls", "images_url", "images_urls"):
            for u in ChatView._getlist(data, key):
                if isinstance(u, str) and u.strip():
                    urls.append(u.strip())
        return urls

    @staticmethod
    def _collect_files(request) -> Optional[Sequence]:
        """
        فایل‌های مولتی‌پارت را از کلیدهای رایج جمع می‌کند.
        """
        try:
            f = (
                request.FILES.getlist("images")
                or request.FILES.getlist("images[]")
                or request.FILES.getlist("file")
                or None
            )
            return f
        except Exception:
            return None

    # ---- POST ---------------------------------------------------------------
    def post(self, request):
        user = request.user
        data = request.data if hasattr(request, "data") else {}

        # message (optional if only images are sent)
        raw_msg = (data.get("message") or "").strip()
        msg: Optional[str] = raw_msg or None

        # new_session
        new_session = _to_bool(data.get("new_session"))

        # inputs: images (b64 / files / urls)
        b64_list = self._collect_b64(data)
        file_list = self._collect_files(request)
        url_list = self._collect_urls(data)

        # force_model (optional – فعلاً نادیده گرفته می‌شود در generate_gpt_response)
        force_model = data.get("force_model") or None

        # لاگ تشخیصی برای ردگیری مشکلات قبل از TalkBot
        try:
            logger.info(
                "ChatView POST hit | user=%s ct=%s msg_len=%s n_files=%s n_b64=%s n_urls=%s keys=%s file_keys=%s",
                getattr(user, "id", None),
                request.META.get("CONTENT_TYPE"),
                len(msg or ""),
                len(file_list or []),
                len(b64_list or []),
                len(url_list or []),
                list(getattr(data, "keys", lambda: [])()),
                list(getattr(request.FILES, "keys", lambda: [])()),
            )
        except Exception:
            # در هر شرایطی نگذاریم POST از بین برود
            pass

        # اگر هیچ ورودی‌ای نیست، 400 بدهیم
        if not (msg or b64_list or file_list or url_list):
            return Response(
                {"detail": "هیچ ورودی‌ای ارسال نشده است. یکی از موارد message یا تصویر را بفرستید."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # فراخوانی موتور پاسخ‌گو
        try:
            answer = generate_gpt_response(
                request_user=user,
                user_message=msg,
                new_session=new_session,
                image_b64_list=b64_list or None,
                image_files=file_list,
                image_urls=url_list or None,
                force_model=force_model,
            )
            return Response({"answer": answer}, status=status.HTTP_200_OK)

        except Exception as exc:
            # اگر هر خطایی از لایه‌های پایین رخ داد، لاگ کنیم و پیام استاندارد بدهیم
            logger.exception("ChatView generate_gpt_response failed: %s", exc)
            return Response(
                {"detail": "خطای غیرمنتظره‌ای رخ داد. لطفاً دوباره تلاش کنید."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )