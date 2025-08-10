# chatbot/roots.py
from django.urls import path
from .views import ChatView

urlpatterns = [
    path("msg/", ChatView.as_view(), name="chat_msg"),
]