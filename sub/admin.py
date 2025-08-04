# sub/admin.py
from django.contrib import admin

from .models import Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "days", "price")
    ordering     = ("days",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display     = ("user", "plan", "start_date", "end_date", "is_active")
    readonly_fields  = ("is_active",)
    list_select_related = ("plan",)
    search_fields    = ("user__username", "user__email")
