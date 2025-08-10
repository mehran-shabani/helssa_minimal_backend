# telemedicine/models.py
import time
from io import BytesIO

from PIL import Image
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.validators import URLValidator
from django.db import models
from pillow_heif import register_heif_opener
from rest_framework.exceptions import ValidationError


class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number=None, email=None, username=None, password=None, **extra_fields):
        if not phone_number and not email:
            raise ValueError('شماره موبایل یا ایمیل ضروری است')

        if not username:
            username = phone_number if phone_number else email

        user = self.model(phone_number=phone_number, email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if not email:
            raise ValueError('برای سوپر یوزر، ایمیل ضروری است')
        if not username:
            raise ValueError('برای سوپر یوزر، یوزرنیم ضروری است')

        return self.create_user(username=username, email=email, password=password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    username = models.CharField(max_length=15, unique=True, null=True, blank=True)
    auth_code = models.IntegerField(unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    is_doctor = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def get_full_name(self):
        return self.username

    def get_short_name(self):
        return self.username


def drug_image_path(instance, filename):
    return f'drug_images/{instance.user.id}/{int(time.time())}_{filename}'




# مدل Visit برای مدیریت اطلاعات ویزیت‌ها
class Visit(models.Model):
    URGENCY_CHOICES = [
        ('prescription', 'نسخه نویسی داروهای پر مصرف'),
        ('diet', 'رژیم درمانی'),
        ('addiction', 'ترک اعتیاد'),
        ('online_consultation', 'ویزیت و مشاوره آنلاین')
    ]

    GENERAL_SYMPTOMS = [
        ('fever', 'تب'),
        ('fatigue', 'خستگی'),
        ('weight_loss', 'کاهش وزن'),
        ('appetite_loss', 'کاهش اشتها'),
        ('night_sweats', 'تعریق شبانه'),
        ('general_pain', 'درد عمومی'),
        ('swollen_lymph_nodes', 'تورم غدد لنفاوی'),
        ('chills', 'لرز'),
        ('malaise', 'احساس ناخوشی عمومی')
    ]

    NEUROLOGICAL_CATEGORIES = [
        ('headache', 'سردرد'),
        ('dizziness', 'سرگیجه'),
        ('seizures', 'تشنج'),
        ('numbness', 'بی‌حسی'),
        ('weakness', 'ضعف عضلانی'),
        ('memory_loss', 'از دست دادن حافظه'),
        ('speech_difficulty', 'مشکل در تکلم'),
        ('vision_problems', 'مشکلات بینایی'),
        ('migraine', 'میگرن'),
        ('tremor', 'لرزش')
    ]

    CARDIOVASCULAR_CATEGORIES = [
        ('chest_pain', 'درد قفسه سینه'),
        ('palpitations', 'تپش قلب'),
        ('shortness_of_breath', 'تنگی نفس'),
        ('swelling', 'تورم'),
        ('high_blood_pressure', 'فشار خون بالا'),
        ('fatigue', 'خستگی'),
        ('fainting', 'غش کردن'),
        ('irregular_heartbeat', 'ضربان قلب نامنظم'),
        ('low_blood_pressure', 'فشار خون پایین')
    ]

    GASTROINTESTINAL_CATEGORIES = [
        ('nausea', 'حالت تهوع'),
        ('vomiting', 'استفراغ'),
        ('diarrhea', 'اسهال'),
        ('constipation', 'یبوست'),
        ('abdominal_pain', 'درد شکم'),
        ('bloating', 'نفخ'),
        ('heartburn', 'سوزش سر دل'),
        ('loss_of_appetite', 'بی‌اشتهایی'),
        ('indigestion', 'سوء هاضمه')
    ]

    RESPIRATORY_CATEGORIES = [
        ('cough', 'سرفه'),
        ('shortness_of_breath', 'تنگی نفس'),
        ('wheezing', 'خس خس سینه'),
        ('chest_tightness', 'سفتی قفسه سینه'),
        ('sore_throat', 'گلودرد'),
        ('runny_nose', 'آبریزش بینی'),
        ('fever', 'تب'),
        ('sneezing', 'عطسه'),
        ('difficulty_breathing', 'مشکل در تنفس')
    ]

    # فیلدهای مدل
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='visits')
    name = models.CharField(max_length=100)
    urgency = models.CharField(max_length=20)
    general_symptoms = models.CharField(max_length=50)
    neurological_symptoms = models.CharField(max_length=50, blank=True)
    cardiovascular_symptoms = models.CharField(max_length=50, blank=True)
    gastrointestinal_symptoms = models.CharField(max_length=50, blank=True)
    respiratory_symptoms = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    drug_images = models.ImageField(
        upload_to=drug_image_path,
        blank=True,
        null=True,
        verbose_name='تصاویر دارو'
    )

    def save(self, *args, **kwargs):
        """
        اگر فیلد drug_images به صورت بایت خام (bytes) باشد، آن را به فایل تبدیل می‌کنیم.
        سپس اگر فایل پسوند HEIC/HEIF داشته باشد، تلاش می‌کنیم آن را به JPEG تبدیل کنیم.
        در صورت خطا در تبدیل، از آن عبور می‌کنیم تا اصل ذخیره‌ی ویزیت مختل نشود.
        """
        # --- 1) اگر به صورت بایت خام آمده باشد، تبدیل به فایل می‌کنیم ---
        if isinstance(self.drug_images, bytes):
            # می‌توانید نام فایل را بسته به نیازتان تغییر دهید
            self.drug_images = ContentFile(self.drug_images, name='uploaded_image.jpg')

        # --- 2) اگر فایل آپلود شده پسوند HEIC/HEIF داشت، تبدیل به JPEG می‌کنیم ---
        if self.drug_images:
            file_name = self.drug_images.name.lower()
            # اگر بخواهید صرفاً براساس پسوند عمل کنید:
            if file_name.endswith(('.heic', '.heif')):
                try:
                    register_heif_opener()
                    img = Image.open(self.drug_images)
                    buffer = BytesIO()
                    img.convert('RGB').save(buffer, format='JPEG', quality=85)
                    buffer.seek(0)
                    new_name = file_name.rsplit('.', 1)[0] + '.jpg'
                    self.drug_images.save(new_name, ContentFile(buffer.getvalue()), save=False)
                except Exception as e:
                    # خطا در تبدیل فرمت از HEIC/HEIF؛ صرفاً رد می‌شویم تا عملیات سیو مختل نشود.
                    print(f"[WARN] تبدیل HEIC/HEIF به JPEG ناموفق بود: {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.id}"

    


class Transaction(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='transactions')
    trans_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.PositiveIntegerField()
    card_num = models.CharField(max_length=20, blank=True, null=True)  # شماره کارت
    factor_id = models.CharField(max_length=100, blank=True, null=True)  # شناسه فاکتور
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transaction {self.user.phone_number} - {self.amount} - {self.status}"


def validate_image_url(value):
    url_validator = URLValidator()
    try:
        url_validator(value)
        if not any(ext in value.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            raise ValidationError('لطفاً یک آدرس تصویر معتبر وارد کنید')
    except ValidationError:
        raise ValidationError('لطفاً یک آدرس URL معتبر وارد کنید')

class Blog(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    author = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='blogs')
    image1 = models.URLField(
        max_length=255, 
        null=True, 
        blank=True, 
        verbose_name='آدرس تصویر اول',
        validators=[validate_image_url],
        help_text='آدرس URL تصویر را وارد کنید (مثال: https://example.com/image.jpg)'
    )
    image2 = models.URLField(
        max_length=255, 
        null=True, 
        blank=True, 
        verbose_name='آدرس تصویر دوم',
        validators=[validate_image_url],
        help_text='آدرس URL تصویر را وارد کنید (مثال: https://example.com/image.jpg)'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']


class Comment(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='comments')
    comment = models.TextField(max_length=500, blank=True)  # حذف null=True
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name="comments")  # رابطه ForeignKey به Blog
    likes = models.PositiveIntegerField(default=0)  # تعداد لایک‌ها
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username}"

    def like(self):
        self.likes += 1
        self.save()


class BoxMoney(models.Model):
    """کیف پول کاربر برای خرید سرویس‌ها"""
    user = models.OneToOneField('CustomUser', on_delete=models.CASCADE, related_name='box_money')
    amount = models.PositiveIntegerField(default=0)

    def has_sufficient_balance(self, price: int) -> bool:
        """بررسی کافی بودن موجودی"""
        return self.amount >= price

    def deduct_amount(self, price: int) -> bool:
        """
        کم کردن مبلغ از کیف پول
        در صورت موفقیت True برمی‌گرداند
        """
        if self.has_sufficient_balance(price):
            self.amount -= price
            self.save(update_fields=['amount'])
            return True
        return False

    def add_amount(self, amount: int) -> None:
        """افزایش موجودی کیف پول"""
        self.amount += amount
        self.save(update_fields=['amount'])

    def get_balance(self) -> int:
        """دریافت موجودی فعلی"""
        return self.amount

    def __str__(self):
        return f"BoxMoney {self.user.phone_number} - {self.amount}"

class Order(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    national_code = models.CharField(max_length=12)
    order_number = models.CharField(max_length=255, unique=True)
    disease_name = models.CharField(max_length=50, null=True, blank=True)
    download_url = models.URLField(max_length=200, unique=True, blank=True)

    def save(self, *args, **kwargs):
        # ساخت خودکار مسیر دانلود
        if not self.download_url:  # اگر مسیر دانلود خالی بود
            self.download_url = f"https://api.medogram.ir/order/download/order_{self.national_code}.pdf"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    

class APKDownloadStat(models.Model):
    """
    شمارندهٔ دانلود فایل APK (Single-row / keyed).
    """
    key = models.CharField(max_length=50, unique=True, default="helssa_apk")
    total = models.PositiveBigIntegerField(default=0)
    last_download_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.key} -> {self.total}"