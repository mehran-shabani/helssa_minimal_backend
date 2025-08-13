from django.urls import path
from .views import ChatView, SummaryView

urlpatterns = [
    path("msg/", ChatView.as_view()),
    path("summary/", SummaryView.as_view()),
]
