# chatbot / serializers.py

# ==============================
# serializers.py
# ==============================
from rest_framework import serializers
from chatbot.models import ChatSession, ChatMessage, ChatSummary


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "session",
            "user",
            "is_bot",
            "message",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "user", "is_bot")


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = (
            "id",
            "user",
            "title",
            "is_open",
            "started_at",
            "ended_at",
            "messages",
        )
        read_only_fields = ("id", "user", "started_at", "ended_at")


class ChatSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSummary
        fields = (
            "id",
            "user",
            "session",
            "model_used",
            "raw_text",
            "rewritten_text",
            "structured_json",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "user")