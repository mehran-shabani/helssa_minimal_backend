# doctor_online/views.py
from django.utils.decorators    import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .models      import Doctor
from .serializers import DoctorOnCallSerializer


class OnCallDoctorAPIView(generics.GenericAPIView):
    """
    GET /doc/oncall/

    برمی‌گرداند یک شیء JSON شامل نام کامل، تخصص و تصویر
    پزشک آن‌کال. در صورت نبودِ پزشک فعال، پاسخ ۴۰۴ به‌همراه
    پیام مناسب ارسال می‌شود.

    • احراز هویت لازم نیست  →  AllowAny  
    • برای جلوگیری از اسپم، یک Throttle ساده برای کاربران ناشناس فعال شده است  
    • نتیجهٔ موفق برای ۶۰ ثانیه کش می‌شود (می‌توانید تغییر دهید)
    """
    serializer_class  = DoctorOnCallSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [AnonRateThrottle]     #  default rate:  anon 100/day
    queryset           = Doctor.objects.filter(is_oncall=True)

    @method_decorator(cache_page(60))           # ثانیه
    def get(self, request, *args, **kwargs):
        doctor = self.get_queryset().first()
        if not doctor:
            return Response(
                {'detail': 'هیچ پزشکی در حال on-call نیست.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(doctor, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)