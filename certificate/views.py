# certificate/ views.py
import os
from django.shortcuts import render
from rest_framework import permissions
from django.contrib.auth import get_user_model
from django.http import FileResponse
from django.views.generic import TemplateView
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import MedicalCertificate

User = get_user_model()



class CertificateDownloadView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request, certificate_national_code):
        try:
            # پیدا کردن گواهی بر اساس کد ملی
            certificate = MedicalCertificate.objects.get(national_code=certificate_national_code)

            # بررسی اگر گواهی قابل دانلود نیست
            if not certificate.is_downloadable:
                return Response({"error": "این گواهی هنوز برای دانلود آماده نیست"}, status=403)

            # بررسی وجود فایل PDF
            if not os.path.exists(certificate.pdf_file_path):
                return Response({"error": "فایل PDF یافت نشد"}, status=404)

            # ارسال فایل PDF برای دانلود
            pdf_file = open(certificate.pdf_file_path, 'rb')
            response = FileResponse(pdf_file, as_attachment=True, filename=f'certificate_{certificate_national_code}.pdf')
            return response

        except MedicalCertificate.DoesNotExist:
            return Response({"error": "گواهی مورد نظر یافت نشد"}, status=404)


class VerifyCertificateView(TemplateView):
    template_name = 'certificate/verify_certificate.html'

    def get_context_data(self, **kwargs):
        certificate_national_code = kwargs.get('certificate_national_code')
        context = super().get_context_data(**kwargs)

        try:
            certificate = MedicalCertificate.objects.get(national_code=certificate_national_code)

            if certificate.is_downloadable:
                context.update({
                    "status": "valid",
                    "message": "This medical certificate is valid.",
                    "first_name": certificate.first_name,
                    "last_name": certificate.last_name,
                    "national_code": certificate.national_code,
                    "sick_days": certificate.sick_days,
                    "sick_name": certificate.sick_name
                })
            else:
                context.update({
                    "status": "not_downloadable",
                    "message": "This certificate is not downloadable yet."
                })
        except MedicalCertificate.DoesNotExist:
            context.update({
                "status": "invalid",
                "message": "This medical certificate is invalid or does not exist."
            })

        return context
    

def hamesterview(request):
    template = 'hamester.html'
    return render(request, template)
        