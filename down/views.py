# down/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import AppUpdate
from .serializers import AppUpdateStatusSerializer, AppUpdateSerializer

class AppUpdateStatusView(APIView):
    """
    API endpoint برای چک کردن وضعیت آپدیت اپلیکیشن
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            # گرفتن آخرین آپدیت موجود
            latest_update = AppUpdate.objects.filter(is_update_available=True).first()
            
            if latest_update:
                # سریالایز کردن داده‌های آپدیت
                update_data = AppUpdateSerializer(latest_update).data
                
                response_data = {
                    'status': 'success',
                    'update_available': True,
                    'version': update_data['version'],
                    'release_notes': update_data['release_notes'],
                    'force_update': update_data['force_update'],
                    'message': f'نسخه جدید {update_data["version"]} موجود است!'
                }
            else:
                response_data = {
                    'status': 'success',
                    'update_available': False,
                    'message': 'شما از آخرین نسخه استفاده می‌کنید'
                }
            
            # سریالایز کردن پاسخ
            serializer = AppUpdateStatusSerializer(data=response_data)
            if serializer.is_valid():
                return Response(serializer.validated_data, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'error',
                    'message': 'خطا در پردازش داده‌ها'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'خطا در بررسی آپدیت',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)