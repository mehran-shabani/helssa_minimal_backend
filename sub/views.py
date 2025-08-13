from __future__ import annotations
from decimal import Decimal
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Plan, Subscription, Specialty, TokenTopUp, SpecialtyAccess
from .serializers import PlanSerializer, SubscriptionSerializer, SpecialtySerializer, TokenTopUpSerializer
from .services import get_active_subscription, get_today_usage, get_topup_balance, get_allowed_specialties

class PlanListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        qs = Plan.objects.all().order_by("monthly_price")
        return Response({"plans": PlanSerializer(qs, many=True).data})

class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        sub = get_active_subscription(request.user)
        if not sub:
            return Response({"detail":"اشتراک فعال ندارید."}, status=404)
        specs = get_allowed_specialties(request.user, sub.plan)
        return Response({
            "subscription": SubscriptionSerializer(sub).data,
            "specialties": SpecialtySerializer(specs, many=True).data
        })

class BuyPlanView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        code = request.data.get("plan_code")
        months = int(request.data.get("months") or 1)
        plan = Plan.objects.filter(code=code).first()
        if not plan:
            return Response({"detail":"پلن نامعتبر است."}, status=400)
        sub = plan.buy(request.user, months=months)
        return Response({"detail":"پلن خریداری شد.", "subscription": SubscriptionSerializer(sub).data}, status=200)

class BuyTopUpView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        chars = int(request.data.get("chars") or 0)
        if chars <= 0:
            return Response({"detail":"مقدار نامعتبر."}, status=400)
        t = TokenTopUp.buy(request.user, chars, note="topup")
        return Response({"detail":"تاپ‌آپ ثبت شد.", "topup": TokenTopUpSerializer(t).data})

class BuySpecialtyView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        code = request.data.get("specialty_code")
        months = int(request.data.get("months") or 1)
        s = Specialty.objects.filter(code=code).first()
        if not s:
            return Response({"detail":"تخصص نامعتبر."}, status=400)
        acc = SpecialtyAccess.buy(request.user, s, months=months)
        return Response({"detail":"تخصص فعال شد.", "specialty": SpecialtySerializer(s).data, "expires_at": acc.expires_at})

class MyUsageView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        usage = get_today_usage(request.user)
        topup = get_topup_balance(request.user)
        sub = get_active_subscription(request.user)
        return Response({
            "usage": usage, "topup_chars": topup,
            "plan": sub.plan.code if sub else None
        })
