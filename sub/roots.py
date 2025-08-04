# urls.py

from django.urls import path
from .views import SubscriptionPlanListAPIView, UserSubscriptionAPIView, PurchaseSubscriptionAPIView



urlpatterns = [
    path('plans/', SubscriptionPlanListAPIView.as_view(), name='subscription-plan-list'),
    path('my-subscription/', UserSubscriptionAPIView.as_view(), name='user-subscription'),
    path('buy/', PurchaseSubscriptionAPIView.as_view(), name='purchase-subscription'),
]