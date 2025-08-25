from django.db import models
import uuid
from django.utils import timezone
from telemedicine.models import BoxMoney, Transaction
from django.db.models import F
from django.conf import settings

class CrazyMinerPayment(models.Model):
    """مدل برای ذخیره تراکنش‌های شارژ کیف پول CrazyMiner"""
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('wallet_charge', 'شارژ کیف پول'),
        ('service_payment', 'پرداخت خدمات'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crazyminer_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=0)  # مبلغ به ریال
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='wallet_charge')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # تشخیص پرداخت برای SOAPify
    is_soapify = models.BooleanField(default=False, help_text="آیا این پرداخت برای SOAPify است؟")
    soapify_user_id = models.CharField(max_length=255, blank=True, help_text="ID کاربر در SOAPify")
    
    # فیلدهای مربوط به درگاه پرداخت
    gateway_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    gateway_reference_id = models.CharField(max_length=255, blank=True, null=True)
    gateway_tracking_code = models.CharField(max_length=255, blank=True, null=True)
    
    # توضیحات و URLs
    description = models.TextField(blank=True, default="شارژ کیف پول")
    callback_url = models.URLField(blank=True)
    redirect_url = models.URLField(blank=True)
    
    # زمان‌ها
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "شارژ کیف پول CrazyMiner"
        verbose_name_plural = "شارژ‌های کیف پول CrazyMiner"
    
    def __str__(self):
        return f"شارژ {self.id} - {self.user.phone_number} - {self.amount} ریال - {self.get_status_display()}"
    
    def mark_completed(self):
        """تکمیل تراکنش و شارژ کیف پول"""
        from django.db import transaction
        
        with transaction.atomic():
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save()
            
            # شارژ کیف پول کاربر
            box_money, created = BoxMoney.objects.get_or_create(
                user=self.user,
                defaults={'balance': 0}
            )
            box_money.balance = F('balance') + self.amount
            box_money.save()
            
            # ثبت در جدول Transaction برای سازگاری
            Transaction.objects.create(
                user=self.user,
                amount=self.amount,
                status='completed',
                trans_id=self.gateway_reference_id or str(self.id)
            )
    
    def mark_failed(self):
        """علامت‌گذاری به عنوان ناموفق"""
        self.status = 'failed'
        self.save()


class CrazyMinerPaymentLog(models.Model):
    """لاگ فعالیت‌های پرداخت"""
    
    LOG_TYPE_CHOICES = [
        ('request', 'درخواست پرداخت'),
        ('callback', 'بازگشت از درگاه'),
        ('verification', 'تایید پرداخت'),
        ('user_fetch', 'دریافت اطلاعات کاربر'),
        ('error', 'خطا'),
    ]
    
    payment = models.ForeignKey(
        CrazyMinerPayment, 
        on_delete=models.CASCADE, 
        related_name='logs'
    )
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES)
    message = models.TextField()
    raw_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "لاگ پرداخت"
        verbose_name_plural = "لاگ‌های پرداخت"
    
    def __str__(self):
        return f"{self.get_log_type_display()} - {self.payment.id} - {self.created_at}"