# medagent/serializers.py
"""DRF serializers for MedAgent endpoints."""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from medagent.models import ChatSession, ChatMessage, SessionSummary

User = get_user_model()


class CreateSessionSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=120,
        allow_blank=True,
        required=False,
        default="",
        help_text="عنوان اختیاری جلسه که فرانت می‌فرستد.",
    )

    def validate_patient_id(self, value: int) -> int:
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("Patient not found.")
        return value


class ChatMessageSerializer(serializers.ModelSerializer):
    session_id = serializers.IntegerField()
    class meta:
        fields = ['content']

    
        


class EndSessionSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()


class SessionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionSummary
        fields = ["text_summary", "json_summary", "tokens_used", "generated_at"]