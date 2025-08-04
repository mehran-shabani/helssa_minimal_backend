# medagent/models.py
"""Domain models for the MedAgent tele‑consultation system."""

from __future__ import annotations

import json
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatSession(models.Model):
    """A discrete conversation between a patient and the AI assistant."""

    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        help_text="Owner of this chat session.",
    )
    name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional title chosen by the patient.",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"Session {self.id} ({self.name or '—'})"

    @property
    def is_active(self) -> bool:
        return self.ended_at is None


class ChatMessage(models.Model):
    """Individual message exchanged inside a session."""

    ROLE_CHOICES = [
        ("owner", "Patient / Owner"),
        ("assistant", "Assistant / Agent"),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField(
        help_text="Plain text or a dict with keys 'image' and 'prompt'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:  # pragma: no cover
        snippet = (
            self.content if isinstance(self.content, str) else json.dumps(self.content)
        )[:40]
        return f"[{self.role}] {snippet}"


class SessionSummary(models.Model):
    """LLM‑generated summary associated with exactly one ChatSession."""

    session = models.OneToOneField(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="summary",
    )
    text_summary = models.TextField()
    json_summary = models.JSONField(default=dict)
    tokens_used = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"Summary <Session {self.session_id}>"
    


class PatientSummary(models.Model):
    """یک خلاصهٔ بلندمدت یک‌صفحه‌ای برای کل تاریخچهٔ بیمار."""
    patient      = models.OneToOneField(User, on_delete=models.CASCADE, related_name="summary")
    json_summary = models.JSONField(default=dict, blank=True)  # ساختار آزاد (مثلاً SOAP)
    updated_at   = models.DateTimeField(auto_now=True)

    def jsunsun(self, patient_id):
        cls = PatientSummary.objects.get(patient_id=patient_id)
        return cls.json_summary

class RunningSessionSummary(models.Model):
    """
    خلاصهٔ «در حال تکمیل» برای یک جلسهٔ فعال.
    هر بار پیام جدید می‌آید، خلاصه به‌روز می‌شود تا طول prompt کوتاه بماند.
    """
    session      = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name="running")
    text_summary = models.TextField(blank=True)
    updated_at   = models.DateTimeField(auto_now=True)