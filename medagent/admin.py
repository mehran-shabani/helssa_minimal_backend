# medagent/admin.py
"""
Django-admin configuration for MedAgent (سازگار با مدل CustomUser).

امکانات:
────────
▪ فهرست و جست‌وجوی سشن‌ها، پیام‌ها و خلاصه‌ها
▪ اکشن «Build / update MedAgent history summary» در لیست کاربران
"""

from __future__ import annotations

import json
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from medagent.models import (
    ChatMessage,
    ChatSession,
    SessionSummary,
    PatientSummary,
    RunningSessionSummary,
)
from medagent.tools import AggregatePatientSummaryTool

# -------------------------------------------------------------------
# 1) اکشن مدیریتی روی کاربران
# -------------------------------------------------------------------
@admin.action(description="Build / update MedAgent history summary for selected users")
def build_patient_summary(modeladmin, request, queryset):
    for user in queryset:
        AggregatePatientSummaryTool()._run(str(user.id))
    modeladmin.message_user(
        request, _("✅ Summaries updated for %(count)s user(s).") % {"count": queryset.count()}
    )


# -------------------------------------------------------------------
# 2) UserAdmin سفارشی (برای telemedicine.CustomUser)
# -------------------------------------------------------------------
CustomUser = get_user_model()


class CustomUserAdmin(BaseUserAdmin):
    """Minimal columns + اکشن ساخت خلاصه."""

    ordering = ("id",)
    actions = [build_patient_summary]

    # ستون‌ها در لیست کاربران
    list_display = (
        "id",
        "username",
        "phone_number",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_doctor",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "is_doctor")
    search_fields = ("username", "phone_number", "email")

    # فیلدها در صفحهٔ جزئیات
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("phone_number", "email", "is_doctor")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login",)}),
    )

    # فیلدها در فرم «Add user»
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "phone_number",
                    "email",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_doctor",
                ),
            },
        ),
    )


# ثبت UserAdmin سفارشی
try:
    admin.site.unregister(CustomUser)
except admin.sites.NotRegistered:
    pass
admin.site.register(CustomUser, CustomUserAdmin)

# -------------------------------------------------------------------
# 3) ChatSession
# -------------------------------------------------------------------
@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "name", "started_at", "ended_at", "is_active")
    list_select_related = ("patient",)
    list_filter = ("ended_at",)
    search_fields = ("id", "patient__username", "patient__phone_number", "patient__email", "name")
    date_hierarchy = "started_at"
    readonly_fields = ("started_at", "ended_at")

# -------------------------------------------------------------------
# 4) ChatMessage
# -------------------------------------------------------------------
@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "short_content", "created_at")
    list_select_related = ("session", "session__patient")
    list_filter = ("role",)
    search_fields = ("session__id", "content")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)

    @admin.display(description="content")
    def short_content(self, obj):
        text = obj.content if isinstance(obj.content, str) else json.dumps(obj.content)
        return text[:80] + ("…" if len(text) > 80 else "")

# -------------------------------------------------------------------
# 5) SessionSummary
# -------------------------------------------------------------------
@admin.register(SessionSummary)
class SessionSummaryAdmin(admin.ModelAdmin):
    list_display = ("session", "generated_at", "tokens_used")
    list_select_related = ("session", "session__patient")
    search_fields = ("session__id",)
    date_hierarchy = "generated_at"
    readonly_fields = ("generated_at", "pretty_json")

    @admin.display(description="SOAP JSON")
    def pretty_json(self, obj):
        pretty = json.dumps(obj.json_summary, ensure_ascii=False, indent=2)
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", pretty)

# -------------------------------------------------------------------
# 6) PatientSummary
# -------------------------------------------------------------------
@admin.register(PatientSummary)
class PatientSummaryAdmin(admin.ModelAdmin):
    list_display = ("patient", "updated_at")
    list_select_related = ("patient",)
    search_fields = ("patient__username", "patient__phone_number", "patient__email")
    readonly_fields = ("updated_at", "pretty_json")

    @admin.display(description="SOAP JSON")
    def pretty_json(self, obj):
        pretty = json.dumps(obj.json_summary, ensure_ascii=False, indent=2)
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", pretty)

# -------------------------------------------------------------------
# 7) RunningSessionSummary
# -------------------------------------------------------------------
@admin.register(RunningSessionSummary)
class RunningSessionSummaryAdmin(admin.ModelAdmin):
    list_display = ("session", "updated_at", "short_text")
    list_select_related = ("session", "session__patient")
    search_fields = ("session__id",)
    readonly_fields = ("updated_at", "text_summary")

    @admin.display(description="summary")
    def short_text(self, obj):
        text = obj.text_summary or ""
        return text[:80] + ("…" if len(text) > 80 else "")
