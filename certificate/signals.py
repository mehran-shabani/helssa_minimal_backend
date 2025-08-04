# certificate/signals.py
import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from kavenegar import *

from medogram import settings
from .models import MedicalCertificate

user = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=MedicalCertificate)
def send_certificate_sms(sender, instance, created, **kwargs):
    if created:
        try:
           
            api = KavenegarAPI(settings.KAVEH_NEGAR_API_KEY)
            params = {
                'receptor': instance.user.phone_number,
                'token': instance.first_name,                             
                'token2': instance.national_code,                         
                'template': 'certificate'                                 
            }
            api.verify_lookup(params)
            logger.info(f"SMS sent successfully to {instance.user.phone_number} and 09113078859 for certificate {instance.id}")

        except (APIException, HTTPException) as e:
            logger.error(f"Failed to send SMS to {instance.user.phone_number} and 09113078859 for certificate {instance.id}: {e}")

        except Exception as e:
            logger.error(f"An unexpected error occurred while sending SMS to {instance.user.phone_number} and 09113078859 for certificate {instance.id}: {e}")
            
            

@receiver(post_save, sender=MedicalCertificate)
def send_downloadable_sms(sender, instance, created, **kwargs):
    if not created and instance.is_downloadable:
        try:
            api = KavenegarAPI(settings.KAVEH_NEGAR_API_KEY)
            params = {
                'receptor': instance.user.phone_number,
                'token': instance.first_name,
                'token2': instance.national_code,
                'template': 'certificate2'
            }
            api.verify_lookup(params)
            logger.info(f"SMS sent successfully to {instance.user.phone_number} for downloadable certificate {instance.id}")

        except (APIException, HTTPException) as e:
            logger.error(f"Failed to send SMS to {instance.user.phone_number} for downloadable certificate {instance.id}: {e}")

        except Exception as e:
            logger.error(f"An unexpected error occurred while sending SMS to {instance.user.phone_number} for downloadable certificate {instance.id}: {e}")





