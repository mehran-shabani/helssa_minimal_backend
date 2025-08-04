# medagent/tools.py
"""
LangChain tools used in MedAgent
────────────────────────────────
    • SummarizeSessionTool         – SOAP summary at end of visit
    • UpdateRunningSummaryTool     – live per-session summary for prompt context
    • AggregatePatientSummaryTool  – admin-only, merges all sessions of a patient
    • ImageAnalysisTool            – Gemini-Vision analysis
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain.tools import BaseTool

from medagent.models import (
    ChatMessage,
    SessionSummary,
    RunningSessionSummary,
    PatientSummary,
)
from medagent.talkbot_client import tb_chat, vision_analyze

# ----- constants -----
SOAP_KEYS: tuple[str, ...] = ("subjective", "objective", "assessment", "plan")

SYSTEM_PROMPT: str = (
    "You are an expert medical summarizer.\n"
    "Produce STRICT JSON with keys:\n"
    "  subjective, objective, assessment, plan\n"
    "No markdown, no extra keys."
)

# ----------------------------------------------------------------------
# 1) Final session summary
# ----------------------------------------------------------------------
class SummarizeSessionTool(BaseTool):
    """Generate a SOAP JSON summary when a visit ends and store it in DB."""

    name: str = "summarize_session"
    description: str = (
        "خلاصه‌سازی یک جلسه پس از اتمام در قالب SOAP و ذخیره در DB."
    )

    def _run(self, session_id: str) -> str:
        msgs_qs = ChatMessage.objects.filter(session_id=session_id).order_by("created_at")
        if not msgs_qs.exists():
            return "پیامی یافت نشد"

        chat_msgs: List[Dict[str, str]] = [
            {
                "role": m.role,
                "content": (
                    m.content
                    if isinstance(m.content, str)
                    else json.dumps(m.content, ensure_ascii=False)
                ),
            }
            for m in msgs_qs
        ]

        raw = tb_chat(
            [{"role": "system", "content": SYSTEM_PROMPT}, *chat_msgs],
            model="o3-mini",
        )

        try:
            parsed = json.loads(raw)
            structured = {k: str(parsed.get(k, "")).strip() for k in SOAP_KEYS}
        except Exception:
            structured = {
                SOAP_KEYS[0]: raw.strip(),
                **{k: "" for k in SOAP_KEYS[1:]},
            }

        SessionSummary.objects.update_or_create(
            session_id=session_id,
            defaults={
                "text_summary": structured["subjective"],
                "json_summary": structured,
                "tokens_used": len(raw) // 4,  # rough token estimate
            },
        )
        return "done"

    # async not supported
    def _arun(self, *args: Any, **kwargs: Any):
        raise NotImplementedError()


# ----------------------------------------------------------------------
# 2) Running (live) session summary
# ----------------------------------------------------------------------
class UpdateRunningSummaryTool(BaseTool):
    """
    Update the live SOAP summary for an ongoing session.
    """

    name: str = "update_running_summary"
    description: str = "به‌روزرسانی خلاصهٔ زندهٔ یک جلسه با پیام جدید."

    def _run(self, session_id: str, new_message: str) -> str:
        running, _ = RunningSessionSummary.objects.get_or_create(session_id=session_id)

        prompt = (
            "Update the ongoing SOAP summary JSON below with ONE new message.\n\n"
            f"Existing summary:\n{running.text_summary or '{}'}\n\n"
            f"New message:\n{new_message}\n\n"
            "Return UPDATED JSON with keys: subjective, objective, assessment, plan."
        )

        updated = tb_chat([{"role": "user", "content": prompt}], model="o3-mini")
        running.text_summary = updated
        running.save(update_fields=["text_summary", "updated_at"])
        return "ok"

    def _arun(self, *args: Any, **kwargs: Any):
        raise NotImplementedError()


# ----------------------------------------------------------------------
# 3) Aggregate patient summary (admin)
# ----------------------------------------------------------------------
class AggregatePatientSummaryTool(BaseTool):
    """
    Merge all SessionSummary objects of a patient into one SOAP JSON.
    Admin-only action.
    """

    name: str = "aggregate_patient_summary"
    description: str = "تجمیع خلاصهٔ تمام جلسات بیمار برای ادمین."

    def _run(self, patient_id: str) -> str:
        sessions = SessionSummary.objects.filter(
            session__patient_id=patient_id
        ).order_by("generated_at")

        aggregate = {k: "" for k in SOAP_KEYS}
        for summ in sessions:
            js = summ.json_summary
            aggregate.update({k: js.get(k, aggregate[k]) for k in SOAP_KEYS})

        PatientSummary.objects.update_or_create(
            patient_id=patient_id,
            defaults={"json_summary": aggregate},
        )
        return "ok"

    def _arun(self, *args: Any, **kwargs: Any):
        raise NotImplementedError()


# ----------------------------------------------------------------------
# 4) Image analysis via Gemini Vision
# ----------------------------------------------------------------------
class ImageAnalysisTool(BaseTool):
    """Send an image + prompt to the Gemini Vision endpoint (TalkBot)."""

    name: str = "analyze_image"
    description: str = (
        "تحلیل تصویر پزشکی با مدل Gemini. "
        "ورودی: {'image': <url|path|datauri>, 'prompt': <str>}، خروجی JSON."
    )

    @property
    def args(self) -> Dict[str, Dict[str, str]]:
        return {
            "image": {
                "type": "string",
                "description": "File path, URL یا data:image;base64,…",
            },
            "prompt": {
                "type": "string",
                "description": "سؤال کاربر دربارهٔ تصویر",
            },
        }

    def _run(self, image: str, prompt: str) -> str:
        result = vision_analyze(image=image, prompt=prompt)
        return json.dumps(result, ensure_ascii=False)

    def _arun(self, *args: Any, **kwargs: Any):
        raise NotImplementedError()
