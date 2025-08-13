from __future__ import annotations
from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=120, blank=True, default="")
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    history = HistoricalRecords(inherit=True)

    def __str__(self) -> str:  # pragma: no cover - simple debug aid
        return f"{self.user_id}#{self.id} open={self.is_open}"

    def end(self, when: timezone.datetime | None = None) -> None:
        """Close the session and set the end time.

        Tests expect a lightweight ``end`` helper which marks the
        session as closed.  Some older test data relies on this method
        existing, so we implement it here instead of directly updating
        fields in the management command.
        """
        self.is_open = False
        self.ended_at = when or timezone.now()
        self.save(update_fields=["is_open", "ended_at"])

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    is_bot = models.BooleanField(default=False)
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["session","created_at"])]

class ChatSummary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_summaries")
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="summaries", null=True, blank=True)
    model_used = models.CharField(max_length=60, default="")
    raw_text = models.TextField(blank=True, default="")
    rewritten_text = models.TextField(blank=True, default="")
    structured_json = models.JSONField(default=dict, blank=True)
    last_message_id = models.IntegerField(default=0)
    is_stale = models.BooleanField(default=True)
    in_progress = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # فقط یک خلاصه به ازای هر جلسه / و حداکثر یکی global (session=NULL) در کد enforce می‌شود
        constraints = [
            models.UniqueConstraint(fields=["user","session"], name="uniq_summary_per_user_session")
        ]
        indexes = [models.Index(fields=["user","updated_at"])]

class UsageLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="usage_logs")
    session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True)
    model = models.CharField(max_length=60, default="")
    input_chars = models.IntegerField(default=0)
    output_chars = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class ToolCallLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="tool_logs")
    name = models.CharField(max_length=80)
    arguments = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
