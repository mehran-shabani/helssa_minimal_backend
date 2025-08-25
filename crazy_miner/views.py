"""
Views برای دسترسی به اطلاعات بیماران
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import logging
from django.conf import settings
from .models import CrazyMinerPayment, CrazyMinerPaymentLog
from .serializers import (
    CrazyMinerCreatePaymentSerializer,
    CrazyMinerPaymentCallbackSerializer,
    CrazyMinerPaymentSerializer,
    CrazyMinerPaymentStatusSerializer
)
from .payment_gateway import crazy_gateway

logger = logging.getLogger(__name__)


class CrazyMinerCreateSOAPifyPaymentView(APIView):
    """ایجاد پرداخت برای کاربران SOAPify"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        amount = request.data.get('amount')
        soapify_user_id = request.data.get('soapify_user_id')
        description = request.data.get('description', 'پرداخت برای SOAPify')
        
        if not amount or not soapify_user_id:
            return Response(
                {'error': 'مبلغ و شناسه کاربر SOAPify الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # استفاده از همان gateway موجود
            from .payment_gateway import crazy_gateway
            from telemedicine.models import CrazyMinerPayment, CrazyMinerPaymentLog
            
            # ایجاد تراکنش با is_soapify=True
            payment = CrazyMinerPayment.objects.create(
                user=request.user,  # پزشک که پرداخت را انجام می‌دهد
                amount=amount,
                description=description,
                payment_type='service_payment',
                is_soapify=True,
                soapify_user_id=soapify_user_id,
                status='pending',
                redirect_url=getattr(settings, 'PAYMENT_REDIRECT_URL', 'https://medogram.ir/payment-redirect/'),
            )
            
            # لاگ
            CrazyMinerPaymentLog.objects.create(
                payment=payment,
                log_type='request',
                message=f'درخواست پرداخت برای SOAPify - کاربر: {soapify_user_id} - مبلغ: {amount}',
                raw_data={
                    'amount': str(amount),
                    'soapify_user_id': soapify_user_id,
                    'doctor_id': str(request.user.id)
                }
            )
            
            # ارسال به درگاه
            gateway_result = crazy_gateway.create_payment_request(
                amount=amount,
                order_id=payment.id,
                redirect_url=payment.redirect_url
            )
            
            if gateway_result['success']:
                payment.gateway_transaction_id = gateway_result['payment_id']
                payment.status = 'processing'
                payment.save()
                
                return Response({
                    'transaction_id': payment.id,
                    'payment_url': gateway_result['payment_url'],
                    'amount': amount,
                    'soapify_user_id': soapify_user_id,
                    'status': payment.status
                }, status=status.HTTP_201_CREATED)
            else:
                payment.status = 'failed'
                payment.save()
                
                return Response(
                    {'error': 'خطا در ایجاد پرداخت'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"خطا در ایجاد پرداخت SOAPify: {str(e)}")
            return Response(
                {'error': 'خطای سیستمی'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CrazyMinerCreatePaymentView(APIView):
    """ایجاد درخواست شارژ کیف پول"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CrazyMinerCreatePaymentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': 'داده‌های نامعتبر', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        amount = validated_data['amount']
        description = validated_data.get('description', 'شارژ کیف پول')
        
        try:
            # ایجاد رکورد پرداخت
            payment = CrazyMinerPayment.objects.create(
                user=request.user,
                amount=amount,
                description=description,
                payment_type='wallet_charge',
                status='pending',
                redirect_url=getattr(settings, 'PAYMENT_REDIRECT_URL', 'https://medogram.ir/payment-redirect/'),
            )
            
            # لاگ ایجاد درخواست
            CrazyMinerPaymentLog.objects.create(
                payment=payment,
                log_type='request',
                message=f'درخواست شارژ کیف پول ایجاد شد - مبلغ: {amount} ریال',
                raw_data={'amount': str(amount), 'user_id': str(request.user.id)}
            )
            
            # ارسال درخواست به درگاه پرداخت
            gateway_result = crazy_gateway.create_payment_request(
                amount=amount,
                order_id=payment.id,
                redirect_url=payment.redirect_url
            )
            
            if gateway_result['success']:
                # به‌روزرسانی اطلاعات پرداخت
                payment.gateway_transaction_id = gateway_result['payment_id']
                payment.status = 'processing'
                payment.save()
                
                # لاگ ارسال موفق به درگاه
                CrazyMinerPaymentLog.objects.create(
                    payment=payment,
                    log_type='info',
                    message='درخواست با موفقیت به درگاه ارسال شد',
                    raw_data=gateway_result
                )
                
                # آماده‌سازی پاسخ
                response_data = {
                    'transaction_id': payment.id,
                    'payment_url': gateway_result['payment_url'],
                    'amount': amount,
                    'status': payment.status,
                    'status_display': payment.get_status_display()
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                # خطا در ارسال به درگاه
                payment.status = 'failed'
                payment.save()
                
                CrazyMinerPaymentLog.objects.create(
                    payment=payment,
                    log_type='error',
                    message=f"خطا در ارسال به درگاه: {gateway_result.get('error')}",
                    raw_data=gateway_result
                )
                
                return Response(
                    {'error': 'خطا در ایجاد پرداخت', 'details': gateway_result.get('error')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در ایجاد پرداخت: {str(e)}")
            return Response(
                {'error': 'خطای سیستمی در ایجاد پرداخت'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CrazyMinerPaymentCallbackView(APIView):
    """دریافت callback از درگاه پرداخت"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = CrazyMinerPaymentCallbackSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"داده‌های نامعتبر در callback: {serializer.errors}")
            return Response(
                {'error': 'داده‌های نامعتبر'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        trans_id = validated_data['trans_id']
        id_get = validated_data['id_get']
        
        try:
            # یافتن پرداخت
            payment = CrazyMinerPayment.objects.filter(
                gateway_transaction_id=id_get
            ).first()
            
            if not payment:
                logger.error(f"پرداخت یافت نشد برای id_get: {id_get}")
                return Response(
                    {'error': 'پرداخت یافت نشد'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # لاگ دریافت callback
            CrazyMinerPaymentLog.objects.create(
                payment=payment,
                log_type='callback',
                message='دریافت callback از درگاه',
                raw_data=request.data
            )
            
            # تایید پرداخت با درگاه
            verify_result = crazy_gateway.verify_payment(trans_id, id_get)
            
            if verify_result['success'] and verify_result['verified']:
                # پرداخت موفق
                payment.gateway_reference_id = trans_id
                payment.gateway_tracking_code = validated_data.get('tracking_code', '')
                payment.mark_completed()
                
                CrazyMinerPaymentLog.objects.create(
                    payment=payment,
                    log_type='verification',
                    message=f'پرداخت با موفقیت تایید شد - مبلغ: {verify_result["amount"]} ریال',
                    raw_data=verify_result
                )
                
                return Response({
                    'success': True,
                    'message': 'پرداخت با موفقیت انجام شد',
                    'transaction_id': payment.id,
                    'tracking_code': payment.gateway_tracking_code
                }, status=status.HTTP_200_OK)
            else:
                # پرداخت ناموفق
                payment.mark_failed()
                
                CrazyMinerPaymentLog.objects.create(
                    payment=payment,
                    log_type='verification',
                    message=f'پرداخت تایید نشد: {verify_result.get("error", "Unknown error")}',
                    raw_data=verify_result
                )
                
                return Response({
                    'success': False,
                    'message': 'پرداخت تایید نشد',
                    'error': verify_result.get('error')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"خطا در پردازش callback: {str(e)}")
            return Response(
                {'error': 'خطای سیستمی در پردازش callback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CrazyMinerPaymentStatusView(APIView):
    """بررسی وضعیت پرداخت"""
    permission_classes = [AllowAny]
    
    def get(self, request, transaction_id):
        try:
            payment = get_object_or_404(CrazyMinerPayment, id=transaction_id)
            
            # آماده‌سازی داده‌های پاسخ
            status_data = {
                'transaction_id': payment.id,
                'status': payment.status,
                'status_display': payment.get_status_display(),
                'amount': payment.amount,
                'gateway_tracking_code': payment.gateway_tracking_code,
                'created_at': payment.created_at,
                'completed_at': payment.completed_at
            }
            
            # اگر هنوز در حال پردازش است، URL پرداخت را هم برگردان
            if payment.status == 'processing' and payment.gateway_transaction_id:
                status_data['payment_url'] = f"{crazy_gateway.base_url}/payment/gateway-{payment.gateway_transaction_id}-get"
            
            serializer = CrazyMinerPaymentStatusSerializer(data=status_data)
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"خطا در دریافت وضعیت پرداخت {transaction_id}: {str(e)}")
            return Response(
                {'error': 'خطا در دریافت وضعیت پرداخت'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CrazyMinerPaymentListView(APIView):
    """لیست پرداخت‌های یک کاربر"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # دریافت پرداخت‌های کاربر
            payments = CrazyMinerPayment.objects.filter(
                user=request.user
            ).order_by('-created_at')[:20]  # آخرین 20 پرداخت
            
            serializer = CrazyMinerPaymentSerializer(payments, many=True)
            
            return Response({
                'count': payments.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"خطا در دریافت لیست پرداخت‌ها: {str(e)}")
            return Response(
                {'error': 'خطا در دریافت لیست پرداخت‌ها'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )