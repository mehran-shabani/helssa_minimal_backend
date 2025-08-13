from __future__ import annotations
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from chatbot.models import UsageLog
from .models import TokenTopUp
from .services import get_active_subscription

@receiver(post_save, sender=UsageLog)
def consume_topup_if_needed(sender, instance: UsageLog, created: bool, **kwargs):
    if not created:
        return
    user = instance.user
    sub = get_active_subscription(user)
    if not sub:
        return
    plan = sub.plan
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_chars = UsageLog.objects.filter(user=user, created_at__gte=start).aggregate(
        c=Sum("input_chars") + Sum("output_chars")
    )["c"] or 0
    overflow = max(0, total_chars - plan.daily_char_limit)
    if overflow <= 0:
        return
    with transaction.atomic():
        topups = TokenTopUp.objects.select_for_update().filter(user=user, char_balance__gt=0).order_by("id")
        remain = overflow
        for t in topups:
            if remain <= 0:
                break
            take = min(t.char_balance, remain)
            t.char_balance -= take
            t.save(update_fields=["char_balance"])
            remain -= take
