# apps.py یا signals.py در اپلیکیشن مورد نظر

from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import SubscriptionPlan

@receiver(post_migrate)
def create_default_plans(sender, **kwargs):
    plans = [
        {"name": "یک‌ماهه آزمایشی", "days": 31, "price": 40000},
        {"name": "سه‌ماهه فصلی", "days": 90, "price": 890000},
        {"name": "شش‌ماهه مراقبتی", "days": 180, "price": 1690000},
        {"name": "یک‌ساله سالیانه", "days": 365, "price": 3690000},
    ]
    for plan in plans:
        SubscriptionPlan.objects.get_or_create(
            name=plan["name"],
            defaults={"days": plan["days"], "price": plan["price"]}
        )