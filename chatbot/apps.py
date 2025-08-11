# chatbot/apps.py
from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    """Application configuration for the chatbot app.

    Loads signal handlers on startup so that summaries are marked stale and
    background rebuild tasks are scheduled whenever a new message is stored.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "chatbot"

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401


