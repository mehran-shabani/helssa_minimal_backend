# sub/models.py
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from telemedicine.models import BoxMoney

User = settings.AUTH_USER_MODEL


class SubscriptionPlan(models.Model):
    """
    پلن‌های قابل خرید. هر پلن طول (روز) و قیمت مشخصی دارد.
    مثال: «ماهانه ۳۱ روز – ۳۰۰٬۰۰۰ ریال».
    """
    name  = models.CharField(max_length=50)
    days  = models.PositiveIntegerField(help_text="مدت پلن (روز)")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ("days",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.days}d / {self.price})"


class Subscription(models.Model):
    """
    اتصال کاربر به پلن اشتراک همراه با تاریخ‌های شروع و پایان.

    فعال بودن بر پایهٔ end_date بررسی می‌شود.
    """
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    plan       = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date   = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    # ---------- خواندنی‌ها ---------- #
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user} – {self.plan.name} (active={self.is_active})"

    @property
    def is_active(self) -> bool:
        """اگر end_date تهی باشد یا گذشته باشد، اشتراک فعال نیست."""
        return bool(self.end_date and timezone.now() <= self.end_date)

    # برای نمایش بولی و عنوان مناسب در ادمین
    is_active.fget.short_description = "is Active??"
    is_active.fget.boolean = True

    # ---------- منطق ذخیره ---------- #
    def save(self, *args, **kwargs):
        """
        اگر end_date هنوز تنظیم نشده باشد، براساس پلن محاسبه می‌شود.
        """
        if self.end_date is None and self.plan:
            base = self.start_date or timezone.now()
            self.end_date = base + timedelta(days=self.plan.days)
        super().save(*args, **kwargs)

    # ---------- متد کمکی خرید / تمدید ---------- #
    @classmethod
    def buy_plan(cls, user, plan: SubscriptionPlan) -> "Subscription":
        """
        خرید یا تمدید اشتراک با کسر مبلغ از کیف پول (BoxMoney).

        - اگر اشتراک فعال باشد: فقط end_date تمدید می‌شود.
        - اگر اشتراک منقضی باشد یا وجود نداشته باشد: اشتراک جدید/مجدد ساخته می‌شود.
        """
        # قفل برای جلوگیری از شرایط مسابقه
        with transaction.atomic():
            box_money = BoxMoney.objects.select_for_update().get(user=user)

            if not box_money.has_sufficient_balance(plan.price):
                raise ValueError("موجودی کیف پول کافی نیست.")

            # کسر مبلغ (فرض می‌شود deduct_amount از Decimal پشتیبانی می‌کند)
            box_money.deduct_amount(Decimal(plan.price))
            box_money.save(update_fields=["amount"])

            now = timezone.now()
            try:
                subscription = cls.objects.select_for_update().get(user=user)
                if subscription.is_active:
                    subscription.end_date += timedelta(days=plan.days)
                else:
                    subscription.start_date = now
                    subscription.end_date   = now + timedelta(days=plan.days)
                subscription.plan = plan
                subscription.save()
            except cls.DoesNotExist:
                subscription = cls.objects.create(
                    user=user,
                    plan=plan,
                    start_date=now,
                    end_date=now + timedelta(days=plan.days),
                )

        return subscription
