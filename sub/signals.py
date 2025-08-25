# sub / signals.py
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.utils import timezone

from sub.models import Subscription, SubscriptionPlan

User = get_user_model()


@receiver(post_save, sender=User)
def grant_welcome_subscription(sender, instance: User, created: bool, **kwargs):
  
    if not created:
        return

    # اگر قبلاً اشتراک دارد، هدیه‌ی ورود نساز
    if hasattr(instance, "subscription"):
        return

    plan = SubscriptionPlan.objects.get(id=5)
    Subscription.buy_plan(instance, plan)


@receiver(post_migrate)
def create_default_plans(sender, **kwargs):
    """
    پس از اعمال مایگریشن‌ها، پلن‌های پیش‌فرض را ایجاد می‌کند.
    با یک گارد ساده از اجرای ناخواسته در مایگریشن سایر اپ‌ها جلوگیری می‌شود.
    """
    # گارد: فقط وقتی نام اپ جاری با اپ SubscriptionPlan یکی باشد اجرا شود
    sender_name = getattr(sender, "name", "")  # مانند "subscription"
    if sender_name and sender_name.split(".")[-1] != SubscriptionPlan._meta.app_label:
        return

    plans = [
        {"name": "یک‌ماهه آزمایشی", "days": 31,  "price": 40000},
        {"name": "سه‌ماهه فصلی",   "days": 90,  "price": 890000},
        {"name": "شش‌ماهه مراقبتی","days": 180, "price": 1690000},
        {"name": "یک‌ساله سالیانه","days": 365, "price": 3690000},
    ]
    for plan in plans:
        SubscriptionPlan.objects.get_or_create(
            name=plan["name"],
            defaults={"days": plan["days"], "price": plan["price"]},
        )