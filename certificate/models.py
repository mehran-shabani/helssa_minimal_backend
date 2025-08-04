# certificate/models.py
from django.contrib.auth import get_user_model
from django.db import models

# دریافت مدل کاربر سفارشی
User = get_user_model()


class MedicalCertificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificate')
    first_name = models.CharField(max_length=100, verbose_name="نام")
    last_name = models.CharField(max_length=100, verbose_name="نام خانوادگی")
    national_code = models.CharField(max_length=100, verbose_name='کد ملی', null=True, blank=True)
    sick_days = models.IntegerField(verbose_name="تعداد روزهای بیماری")
    sick_name = models.CharField(max_length=255, verbose_name="نام بیماری")
    is_downloadable = models.BooleanField(default=False, verbose_name="قابل دانلود بودن")
    pdf_file_path = models.CharField(max_length=255, null=True, blank=True, verbose_name="مسیر فایل PDF")

    verification_link = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return f"گواهی {self.first_name} {self.last_name}"
