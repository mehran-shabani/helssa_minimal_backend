# telemedicine/signals.py
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver, Signal
from django.template.loader import render_to_string
from kavenegar import KavenegarAPI
from telemedicine.models import BoxMoney, Transaction, Visit, APKDownloadStat
from django.utils import timezone
from django.db.models import F



# ──────────────────────────────
# تنظیمات ثابت
# ──────────────────────────────
User = get_user_model()   # ← مدل کاربر فعلی پروژه
TOPUP_AMOUNT = 300000   # 


# ──────────────────────────────
# ۱) قبل از ذخیرهٔ کاربر
# ──────────────────────────────
@receiver(pre_save, sender=User)
def set_username_to_phone(sender, instance, **kwargs):
    """
    اگر username تهی باشد و phone_number موجود باشد،
    قبل از ذخیره آن را برابر شمارهٔ موبایل قرار می‌دهیم.
    """
    if not instance.username and getattr(instance, "phone_number", None):
        instance.username = str(instance.phone_number)


# ──────────────────────────────
# ۲) پس از ایجاد کاربر جدید
# ──────────────────────────────

@receiver(post_save, sender=User)
def init_wallet_and_send_welcome_sms(sender, instance, created, **kwargs):
    """
    هنگام ایجاد کاربر:
      • کیف پول با مبلغ 300000 تومان ساخته می‌شود.
      • پیامک قالب first_log ارسال می‌شود.
      • رکورد محدودیت پیام چت‌بات ساخته می‌شود.
    """
    if not created:  # فقط در اولین ایجاد
        return
    
    BoxMoney.objects.create(user=instance, amount=TOPUP_AMOUNT)



    
    


# ──────────────────────────────
# ۳) افزایش موجودی پس از تراکنش موفق
# ──────────────────────────────
@receiver(post_save, sender=Transaction)
def update_wallet_after_transaction(sender, instance, **kwargs):
    """
    هرگاه وضعیت تراکنش 'successful' شد،
    مبلغ تراکنش به کیف پول افزوده می‌شود.
    """
    if instance.status != "successful":
        return

    wallet, _ = BoxMoney.objects.get_or_create(user=instance.user)
    wallet.amount += instance.amount
    wallet.save(update_fields=["amount"])


# ──────────────────────────────
# ۴) ایمیل جزئیات ویزیت
# ──────────────────────────────

@receiver(post_save, sender=Visit)
def send_visit_email(sender, instance, created, **kwargs):
    if created:
        html_content = render_to_string('visit_email.html', {'visit': instance})
        email = EmailMessage(
            subject=f"Visit Details: {instance.name}",
            body=html_content,
            from_email='info@medogram.ir',
            to=['shabanimehran@gmail.com'],
        )
        email.content_subtype = "html"
        email.send()


# ──────────────────────────────
# ۵) پیامک تأیید ایجاد ویزیت
# ──────────────────────────────
@receiver(post_save, sender=Visit)
def sms_visit_created(sender, instance, created, **kwargs):
    if not created:
        return

    phone = getattr(instance.user, "phone_number", None)
    if phone:
        try:
            api = KavenegarAPI(settings.KAVEH_NEGAR_API_KEY)
            api.verify_lookup({
                "receptor": phone,
                "token": random.randint(100000, 999999),
                "template": "register-visit",
            })
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Kavenegar register-visit SMS failed: {exc}")

            
apk_downloaded = Signal()

@receiver(apk_downloaded)
def on_apk_downloaded(sender, **kwargs):
    # اگر ردیف وجود ندارد، بساز
    APKDownloadStat.objects.get_or_create(key="helssa_apk")
    # افزایش اتمیک و ثبت زمان آخرین دانلود
    APKDownloadStat.objects.filter(key="helssa_apk").update(
        total=F('total') + 1,
        last_download_at=timezone.now()
    )