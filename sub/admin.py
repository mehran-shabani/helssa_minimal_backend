from django.contrib import admin
from .models import Plan, Subscription, Specialty, SpecialtyAccess, TokenTopUp

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code",
        "name",
        "monthly_price",
        "daily_char_limit",
        "daily_requests_limit",
        "max_tokens_per_request",
        "allow_vision",
        "max_images",
        "allow_agent_tools",
    )
    search_fields = ("code", "name")

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "active", "started_at", "expires_at")
    list_filter = ("active", "plan")

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    search_fields = ("code", "name")

@admin.register(SpecialtyAccess)
class SpecialtyAccessAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "specialty", "active", "expires_at")
    list_filter = ("active",)

@admin.register(TokenTopUp)
class TokenTopUpAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "char_balance", "created_at", "note")
