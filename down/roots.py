# down/status

from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.AppUpdateStatusView.as_view(), name='app_update_status'),
]