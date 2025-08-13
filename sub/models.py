from __future__ import annotations
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Specialty(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True, default="")
    system_prompt_ext = models.TextField(blank=True, default="")
    enabled_tools = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Plan(models.Model):
    code = models.SlugField(max_length=30, unique=True)  # starter/pro/business
    name = models.CharField(max_length=80)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # محدودیت‌ها
    daily_char_limit = models.IntegerField(default=20_000)
    daily_requests_limit = models.IntegerField(default=50)
    max_tokens_per_request = models.IntegerField(default=800)
    allow_vision = models.BooleanField(default=False)
    max_images = models.IntegerField(default=0)
    allow_agent_tools = models.BooleanField(default=True)
    priority = models.CharField(max_length=20, default="normal")

    specialties = models.ManyToManyField(Specialty, blank=True, related_name="plans")

    def __str__(self):
        return f"Plan {self.name} ({self.code})"

    # --- خرید پلن (ساده / بدون درگاه) ---
    def buy(self, user, months: int = 1, start_at=None, auto_renew=True) -> "Subscription":
        """
        تراکنش سادهٔ خرید: اشتراک فعال قبلی را غیرفعال نمی‌کنیم، بلکه جدید را اضافه می‌کنیم.
        اگر start_at None باشد، از الان محاسبه می‌شود.
        """
        start = start_at or timezone.now()
        expires = start + timedelta(days=30 * months)
        with transaction.atomic():
            sub = Subscription.objects.create(
                user=user, plan=self, started_at=start, expires_at=expires, auto_renew=auto_renew, active=True
            )
        return sub


class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at"])]

    @property
    def is_active(self) -> bool:
        return self.active and self.expires_at > timezone.now()

    def __str__(self):
        return f"{self.user_id}->{self.plan.code} active={self.is_active}"


class SpecialtyAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="specialty_access")
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "specialty")]

    @classmethod
    def buy(cls, user, specialty: Specialty, months: int = 1) -> "SpecialtyAccess":
        with transaction.atomic():
            now = timezone.now()
            exists = cls.objects.select_for_update().filter(user=user, specialty=specialty).first()
            if exists and exists.expires_at > now:
                exists.expires_at += timedelta(days=30 * months)
                exists.active = True
                exists.save(update_fields=["expires_at", "active"])
                return exists
            expires = now + timedelta(days=30 * months)
            return cls.objects.create(user=user, specialty=specialty, expires_at=expires, active=True)


class TokenTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="token_topups")
    char_balance = models.IntegerField(default=0)  # به کاراکتر
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=120, blank=True, default="")

    def __str__(self):
        return f"TopUp user={self.user_id} chars={self.char_balance}"

    @classmethod
    def buy(cls, user, chars: int, note: str = "") -> "TokenTopUp":
        return cls.objects.create(user=user, char_balance=max(0, int(chars)), note=note or "purchase")
