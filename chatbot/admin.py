# chatbot/admin.py
# ==============================
# admin.py
# ==============================
from django.contrib import admin
from chatbot.models import ChatSession, ChatMessage, ChatSummary


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_open", "started_at")
    list_filter = ("is_open", "started_at")
    search_fields = ("user__username", "user__email")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "user", "is_bot", "short_msg", "created_at")
    list_filter = ("is_bot", "created_at")
    search_fields = ("message", "user__username")
    ordering = ("-created_at",)

    @admin.display(description="Message")
    def short_msg(self, obj):
        return (obj.message[:60] + "…") if len(obj.message) > 60 else obj.message


@admin.register(ChatSummary)
class ChatSummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session", "model_used", "updated_at")
    list_filter = ("model_used", "updated_at")
    search_fields = ("rewritten_text", "user__username")