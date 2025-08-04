from django.urls import path
from .views import OnCallDoctorAPIView

urlpatterns = [
    path('oncall/', OnCallDoctorAPIView.as_view(), name='doctor-oncall'),
]