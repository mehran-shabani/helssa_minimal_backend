# sub / admin py
from django.contrib import admin
from .models import SubscriptionPlan, Subscription, SubscriptionTransaction

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'days', 'price')



@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_display', 'start_date', 'end_date', 'is_active')
    readonly_fields = ('is_active',)

    def plan_display(self, obj):
        return obj.plan.name if obj.plan else "WELCOME_GIFT"
    plan_display.short_description = 'plan'
    

@admin.register(SubscriptionTransaction)
class SubscriptionTransactionAdmin(admin.ModelAdmin):
    list_display  = ('id', 'user', 'plan', 'amount', 'currency', 'status', 'created_at', 'completed_at')
    list_filter   = ('status', 'currency', 'plan')
    search_fields = ('id', 'user__username', 'description')
    readonly_fields = ('created_at', 'completed_at')