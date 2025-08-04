"""
Custom permission classes for MedAgent.

- HasActiveSubscription : فقط کاربرانی را می‌پذیرد که یک Subscription فعال دارند.
- PatientHasActiveSubscription : بررسی می‌کند بیمار (از طریق پارامتر URL) اشتراک فعال دارد.
"""

from rest_framework.permissions import BasePermission
from django.shortcuts import get_object_or_404
from sub.models import Subscription
from django.contrib.auth import get_user_model

User = get_user_model()


class HasActiveSubscription(BasePermission):
    """
    دسترسی فقط برای کاربرانی که Subscription فعال دارند.
    AnonymousUser یا کاربران بدون Subscription → HTTP 403.
    """

    message = "You must have an active subscription."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        try:
            return user.subscription.is_active
        except (AttributeError, Subscription.DoesNotExist):
            return False

