# certificate/urls.py
from django.urls import path
from .views import (
    CertificateDownloadView,
    VerifyCertificateView,
)

urlpatterns = [
    path('download/<str:certificate_national_code>/', CertificateDownloadView.as_view(), name='certificate_download'),
    path('verify/<str:certificate_national_code>/', VerifyCertificateView.as_view(), name='verify_certificate'),
]