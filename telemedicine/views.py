import requests
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
import random
import os
from rest_framework import status, permissions
from django.http import FileResponse
import logging
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from kavenegar import APIException, HTTPException, KavenegarAPI
from medogram.settings import BITPAY_API_KEY
from .models import APKDownloadStat, Comment, Blog, Order, Transaction, Visit, BoxMoney
from .serializers import (CustomUserProfileSerializer, BlogSerializer, BoxMoneySerializer, VisitSerializer,
                          CommentSerializer, CustomUserProfileJustUserNameSerializer)
from telemedicine.signals import apk_downloaded


User = get_user_model()

logger = logging.getLogger(__name__)


class RegisterOrLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response(
                {'error': 'Phone number is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user, created = User.objects.get_or_create(phone_number=phone_number)

        # Generate a random 6-digit authentication code
        code = random.randint(100000, 999999)
        user.auth_code = str(code)
        user.save(update_fields=['auth_code'])

        # Send SMS with the authentication code
        try:
            api = KavenegarAPI(settings.KAVEH_NEGAR_API_KEY)
            params = {
                'receptor': user.phone_number,
                'token': user.auth_code,
                'template': 'users'  # Ensure this template exists in Kaveh Negar
            }
            api.verify_lookup(params)
        except (APIException, HTTPException) as e:
            logger.error(f"Failed to send SMS to {user.phone_number}: {e}")
            return Response(
                {'error': 'Failed to send authentication code. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'message': 'کد احراز هویت به شماره موبایل شما ارسال شد.'},
            status=status.HTTP_200_OK
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone_number = request.data.get('phone_number')
        code = request.data.get('code')

        try:
            user = User.objects.get(phone_number=phone_number)
            if user.auth_code == int(code):
                refresh = RefreshToken.for_user(user)
                response = Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_200_OK)
                
                
                # ─── پیامک خوش‌آمد فقط اگر هیچ ویزیتی ندارد ───
                if not Visit.objects.filter(user=user).exists():
                    try:
                        api = KavenegarAPI(settings.KAVEH_NEGAR_API_KEY)
                        api.verify_lookup({
                            'receptor': user.phone_number,
                            'token'   : 300000,   # مبلغ یا مقدار دل‌خواه
                            'template': 'first-log',
                        })
                    except (APIException, HTTPException) as exc:
                        logger.warning(f"Welcome SMS failed for {user.phone_number}: {exc}")

                return response

            return Response({'message': 'کد وارد شده صحیح نیست.'},
                            status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'message': 'کاربری با این شماره موبایل پیدا نشد.'},
                            status=status.HTTP_404_NOT_FOUND)


class CreateTransaction(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        payment_data = {
            'api': BITPAY_API_KEY,
            'amount': request.data['amount'],
            'redirect': 'https://medogram.ir/payment-redirect/',
        }
        response = requests.post('https://bitpay.ir/payment/gateway-send', data=payment_data)
        id_get = response.text
        if int(id_get) > 0:
            transaction = Transaction.objects.create(
                user=request.user,
                amount=request.data['amount'],
                card_num=id_get
            )
            payment_url = f"https://bitpay.ir/payment/gateway-{id_get}-get"
            return Response({'payment_url': payment_url}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Error from BitPay: ' + id_get}, status=status.HTTP_400_BAD_REQUEST)


class VerifyPaymentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        trans_id = request.data.get('trans_id')
        id_get = request.data.get('id_get')
        if not trans_id or not id_get:
            return Response({'error': 'trans_id or id_get missing'}, status=status.HTTP_400_BAD_REQUEST)

        verify_data = {
            'api': settings.BITPAY_API_KEY,
            'trans_id': trans_id,
            'id_get': id_get,
            'json': 1
        }
        response = requests.post('https://bitpay.ir/payment/gateway-result-second', data=verify_data)
        result = response.json()
        if result.get('status') == 1:
            transaction = Transaction.objects.get(card_num=id_get)
            transaction.status = 'successful'
            transaction.factor_id = trans_id
            transaction.save()
            return Response({'message': 'Payment verified successfully'}, status=status.HTTP_200_OK)
        elif result.get('status') == 11:
            return Response({'message': 'Transaction verified in the past'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)


class CreateVisit(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # بررسی موجودی کیف پول
        box_money = BoxMoney.objects.select_for_update().get(user=request.user)
        visit_cost = 398000
        if not box_money.has_sufficient_balance(visit_cost):
            # اگر موجودی کافی نیست، برگرداندن پاسخ خطا
            logger.error(f"User {request.user.id} has insufficient balance for visit cost: {visit_cost}")
            return Response(
                {'error': 'موجودی کیف پول شما برای این ویزیت کافی نیست.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ایجاد سریالایزر با داده‌های ارسالی
        serializer = VisitSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            # کم کردن هزینه از کیف پول
            box_money.amount -= visit_cost
            box_money.save()

            # ذخیره ویزیت
            try:
                visit = serializer.save()
                return Response({
                    'message': 'ویزیت با موفقیت ثبت شد.',
                    'visit_id': visit.id,
                    'visit_data': VisitSerializer(visit).data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                # در صورت خطا، برگرداندن پول به کیف پول
                logger.error(f"Error saving visit for user {request.user.id}: {e} - Reverting box money update for {visit_cost}")
                box_money.amount += visit_cost
                box_money.save()
                return Response({
                    'error': 'خطا در ثبت ویزیت',
                    'details': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            print(serializer.error)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        visits = Visit.objects.filter(user=request.user).order_by('-created_at')
        serializer = VisitSerializer(visits, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CustomUserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CustomUserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BlogListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        blogs = Blog.objects.all()
        serializer = BlogSerializer(blogs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BlogCommentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, blog_id):
        blog = get_object_or_404(Blog, pk=blog_id)
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(blog=blog, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommentLikeDislikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, comment_id, actions):
        comment = get_object_or_404(Comment, id=comment_id)
        if actions == 'like':
            comment.likes += 1
        elif actions == 'dislike':
            comment.likes = max(0, comment.likes - 1)
        comment.save()

        return Response({'message': f'{actions.capitalize()} added', 'likes': comment.likes}, status=status.HTTP_200_OK)

class ShowBoxMoneyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        box_money = BoxMoney.objects.get(user=request.user)
        serializer = BoxMoneySerializer(box_money)
        return Response(serializer.data, status=status.HTTP_200_OK)



class DownloadAPKView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        # مسیر فایل APK نسبت به همین اپ
        current_directory = os.path.dirname(__file__)
        file_path = os.path.join(current_directory, 'apps', 'app-release.apk')

        if not os.path.exists(file_path):
            return Response({"error": "File not found"}, status=404)

        # ارسال سیگنال شمارش (بدون IP — فقط ثبت شمارش)
        apk_downloaded.send(sender=self.__class__)

        # پاسخ دانلود فایل
        response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename='helssa.apk')

        # اختیاری: جلوگیری از cache سمت کلاینت/پراکسی تا شمارش واقعی بماند
        response["Cache-Control"] = "no-store"

        # اختیاری: عدد فعلی را در هدر برگردان (برای مانیتورینگ کلاینتی)
        try:
            stat = APKDownloadStat.objects.only("total").get(key="helssa_apk")
            response["X-Helssa-Downloads"] = str(stat.total)
        except APKDownloadStat.DoesNotExist:
            response["X-Helssa-Downloads"] = "0"

        return response
            
        
class CreateSuperVisit(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, cost):
        # بررسی موجودی کیف پول
        box_money = BoxMoney.objects.select_for_update().get(user=request.user)

        if box_money.amount < cost:
            return Response(
                {'error': 'موجودی کیف پول شما برای این ویزیت کافی نیست.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ایجاد سریالایزر با داده‌های ارسالی
        serializer = VisitSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            # کم کردن هزینه از کیف پول
            box_money.amount -= cost
            box_money.save()

            # ذخیره ویزیت
            try:
                visit = serializer.save()
                return Response({
                    'message': 'ویزیت با موفقیت ثبت شد.',
                    'visit_id': visit.id,
                    'visit_data': VisitSerializer(visit).data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                # در صورت خطا، برگرداندن پول به کیف پول
                box_money.amount += cost
                box_money.save()
                return Response({
                    'error': 'خطا در ثبت ویزیت',
                    'details': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
class UserProfileViewJustUserName(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CustomUserProfileJustUserNameSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
class UserProfileUpdateViewJustUserName(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CustomUserProfileJustUserNameSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






def order_verification(request, national_code):
    try:
        order = Order.objects.get(national_code=national_code)
        context = {'order': order, 'not_found': False}
    except Order.DoesNotExist:
        context = {'not_found': True, 'national_code': national_code}

    return render(request, 'telemedicine/verification_order.html', context)


class download_order_file(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, national_code):
        order = get_object_or_404(Order, national_code=national_code)
        if order:
            file_path = os.path.join(settings.MEDIA_ROOT, 'pdf', 'order', f'order_{national_code}.pdf')
            response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=f'order_{national_code}.pdf')
            return response
        else:
            return Response({"error": "Order not found"}, status=404)

