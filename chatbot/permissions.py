from rest_framework.permissions import BasePermission
from sub.services import get_active_subscription, compute_caps_for_request

class HasActiveSubscription(BasePermission):
    message = "اشتراک فعال نیست."

    def has_permission(self, request, view):
        sub = get_active_subscription(request.user)
        if not sub or not sub.is_active:
            self.message = "اشتراک شما فعال نیست یا منقضی شده. لطفاً پلن تهیه/تمدید کنید."
            return False
        caps = compute_caps_for_request(request.user, sub, request)
        if not caps.get("ok"):
            request._caps_error = caps
            self.message = caps.get("reason", "محدودیت پلن.")
            return False
        request._caps = caps
        return True
