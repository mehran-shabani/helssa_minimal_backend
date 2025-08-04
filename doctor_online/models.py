# doctor_online/models.py
from django.core.exceptions import ValidationError
from django.db import models

class Doctor(models.Model):
    first_name = models.CharField('نام', max_length=50)
    last_name  = models.CharField('نام خانوادگی', max_length=50)
    email = models.EmailField('Email', unique=True)
    specialty  = models.CharField('تخصص', max_length=100)
    image      = models.ImageField('عکس', upload_to='doctors/')
    is_oncall  = models.BooleanField('آن‌کال', default=False)

    # ----------- NEW -----------
    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()
    
    @classmethod
    def oncall_email(cls):
        """
        ایمیل تنها پزشک آن‌کال را برمی‌گرداند.
        - اگر کسی آن‌کال نباشد: None
        - اگر به‌اشتباه چند نفر آن‌کال باشند: ایمیل اولین رکورد
        """
        try:
            return cls.objects.get(is_oncall=True).email
        except cls.DoesNotExist:
            return None
        except cls.MultipleObjectsReturned:
            return (
                cls.objects.filter(is_oncall=True)
                .values_list("email", flat=True)
                .first()
            )
    # ----------------------------

    class Meta:
        verbose_name        = 'پزشک'
        verbose_name_plural = 'پزشکان'

    def clean(self):
        if self.is_oncall and Doctor.objects.filter(is_oncall=True).exclude(pk=self.pk).exists():
            raise ValidationError('فقط یک پزشک می‌تواند on-call باشد.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.full_name} - {self.specialty}'