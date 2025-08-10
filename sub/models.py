# sub / models.py
"""
Minimal subscription models used for testing the medagent application.

A SubscriptionPlan represents purchasable plans with a duration and price.
A Subscription associates a user with a plan and uses start/end dates to
determine whether it is active.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from telemedicine.models import BoxMoney

User = settings.AUTH_USER_MODEL


class SubscriptionPlan(models.Model):
    """
    Represents a purchasable subscription plan. Each plan has a duration in days
    and a price. For example, a 31-day plan might cost 300 units.
    """
    name = models.CharField(max_length=50)
    days = models.PositiveIntegerField(help_text="Duration of the subscription in days")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.days}d, {self.price})"


class SubscriptionTransaction(models.Model):
    """
    ثبت هر خرید اشتراک. رکورد ابتدا به حالت PENDING ایجاد می‌شود و در پایان
    SUCCESS/FAILED می‌گردد. نیازی به رووت ندارد و برای گزارش داخلی/لاگ استفاده می‌شود.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscription_transactions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscription_transactions")

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="مبلغ کسر شده از کیف پول/درگاه",
    )
    currency = models.CharField(max_length=8, default="IRR")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    description = models.CharField(max_length=255, blank=True)

    # برای مشاهده اثر خرید روی تاریخ پایان اشتراک
    before_end_date = models.DateTimeField(null=True, blank=True)
    after_end_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Tx#{self.id} user={self.user} plan={self.plan} status={self.status}"


class Subscription(models.Model):
    """
    Associates a user with a subscription plan and keeps track of start and end dates.

    A subscription is considered active if the current time is before the end_date.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()

    
    def __str__(self):
        plan_label = self.plan.name if self.plan else "WELCOME_GIFT"
        return f"Subscription({self.user.username}, plan={plan_label}, active={self.is_active})"

    @property
    def is_active(self) -> bool:
        now = timezone.now()
        return self.start_date <= now <= self.end_date

    @classmethod
    def buy_plan(cls, user, plan):
        """
        خرید پلن با در نظر گرفتن موجودی کاربر و تمدید/ایجاد اشتراک جدید.
        هر خرید در SubscriptionTransaction ثبت می‌شود. هیچ رووت جدیدی ندارد.
        اتمیک: کسر از کیف‌پول + تغییر اشتراک + لاگ تراکنش یا همه باهم انجام می‌شوند یا هیچ‌کدام.
        """
        now = timezone.now()

        with transaction.atomic():
            # 1) ایجاد تراکنش PENDING
            tx = SubscriptionTransaction.objects.create(
                user=user,
                plan=plan,
                amount=plan.price,
                currency="IRR",
                status=SubscriptionTransaction.Status.PENDING,
                description="Wallet purchase",
            )

            # 2) قفل روی کیف پول برای اجتناب از Race Condition
            box_money = BoxMoney.objects.select_for_update().get(user=user)
            if not box_money.has_sufficient_balance(plan.price):
                tx.status = SubscriptionTransaction.Status.FAILED
                tx.description = "موجودی کافی نیست"
                tx.completed_at = now
                tx.save(update_fields=["status", "description", "completed_at"])
                raise ValueError("موجودی کافی نیست")

            # در صورت نیاز به int (مطابق پیاده‌سازی فعلی شما)
            box_money.deduct_amount(int(plan.price))

            # 3) بروزرسانی/ایجاد اشتراک با قفل
            try:
                subscription = cls.objects.select_for_update().get(user=user)
                tx.before_end_date = subscription.end_date

                if subscription.is_active:
                    subscription.end_date += timedelta(days=plan.days)
                else:
                    subscription.plan = plan
                    subscription.start_date = now
                    subscription.end_date = now + timedelta(days=plan.days)

                subscription.plan = plan
                subscription.save()
            except cls.DoesNotExist:
                subscription = cls.objects.create(
                    user=user,
                    plan=plan,
                    start_date=now,
                    end_date=now + timedelta(days=plan.days)
                )
                tx.before_end_date = None  # قبلاً اشتراک نداشته

            # 4) تکمیل تراکنش
            tx.after_end_date = subscription.end_date
            tx.status = SubscriptionTransaction.Status.SUCCESS
            tx.completed_at = timezone.now()
            tx.save(update_fields=["before_end_date", "after_end_date", "status", "completed_at"])

        return subscription