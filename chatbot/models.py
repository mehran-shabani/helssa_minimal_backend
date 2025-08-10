# chatbot / models.py 

# ==============================
# models.py
# ==============================
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ChatSession(models.Model):
    """Represents a logical conversation ("session") between a user and the bot."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")
    title = models.CharField(max_length=120, blank=True, default="")
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_open = models.BooleanField(default=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Chat session"
        verbose_name_plural = "Chat sessions"

    def __str__(self) -> str:  # pragma: no cover
        status = "open" if self.is_open else "closed"
        return f"Session #{self.pk} – {self.user} ({status})"

    # ------------------------------------------------------------------
    def end(self, when: timezone.datetime | None = None) -> None:
        """Mark session as ended (idempotent)."""
        if not self.is_open:
            return
        self.is_open = False
        self.ended_at = when or timezone.now()
        self.save(update_fields=["is_open", "ended_at"])


class ChatMessage(models.Model):
    """Stores a single message exchanged inside a ChatSession."""

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_bot = models.BooleanField(default=False)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Chat message"
        verbose_name_plural = "Chat messages"

    def __str__(self) -> str:  # pragma: no cover
        role = "BOT" if self.is_bot else "USER"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {role}: {self.message[:40]}…"


class ChatSummary(models.Model):
    """Stores AI-generated rewrites / summaries of one session or the whole history."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_summaries")
    session = models.ForeignKey(ChatSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="summaries")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    model_used = models.CharField(max_length=32, default="zarin-1.0")

    raw_text = models.TextField(help_text="Full concatenated conversation text sent to rewriter API.")
    rewritten_text = models.TextField(help_text="Output produced by rewriter API.")
    structured_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Chat summary"
        verbose_name_plural = "Chat summaries"

    def __str__(self) -> str:  # pragma: no cover
        tgt = f"session {self.session_id}" if self.session_id else "global"
        return f"Summary #{self.pk} ({tgt})"