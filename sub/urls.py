from django.urls import path
from .views import PlanListView, MySubscriptionView, BuyPlanView, BuyTopUpView, BuySpecialtyView, MyUsageView

urlpatterns = [
    path("plans/", PlanListView.as_view()),
    path("me/", MySubscriptionView.as_view()),
    path("buy/", BuyPlanView.as_view()),
    path("topup/", BuyTopUpView.as_view()),
    path("specialty/", BuySpecialtyView.as_view()),
    path("usage/", MyUsageView.as_view()),
]
