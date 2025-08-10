# chatbot/apps.py
from django.apps import AppConfig


class ChatBotConfig(AppConfig):
    """Application configuration for the chatbot app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "chatbot"


