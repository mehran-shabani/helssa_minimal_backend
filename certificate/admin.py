# certificate/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
import os
import logging

from .models import MedicalCertificate
from .util import create_medical_certificate  # تابعی که PDF می‌سازد را اینجا ایمپورت کنید


@admin.register(MedicalCertificate)
class MedicalCertificateAdmin(admin.ModelAdmin):
    list_display = (
        'first_name', 'last_name', 'national_code', 'sick_days',
        'sick_name', 'is_downloadable',
    )
    list_filter = ('is_downloadable', 'sick_name')
    search_fields = ('first_name', 'last_name', 'national_code', 'sick_name')
    readonly_fields = ()

    def save_model(self, request, obj, form, change):
        # لینک تأیید را تنظیم کن
        obj.verification_link = f'https://api.medogram.ir/certificate/verify/{obj.national_code}/'

        super().save_model(request, obj, form, change)  # اول ذخیره کن تا ID ایجاد بشه

        # مسیر فایل PDF
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'pdf/certificates')
        if not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir)

        file_name = f'certificate_{obj.national_code}.pdf'
        file_path = os.path.join(pdf_dir, file_name)

        # ساخت PDF
        pdf_created = create_medical_certificate(
            obj.first_name, obj.last_name, obj.national_code,
            obj.sick_days, obj.sick_name, obj.verification_link
        )

        if pdf_created:
            obj.pdf_file_path = file_path
            obj.is_downloadable = True
        else:
            logging.warning(f"PDF creation failed for certificate {obj.id}")
            obj.is_downloadable = False

        # ذخیره نهایی پس از ساخت PDF
        obj.save()