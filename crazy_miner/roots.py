"""
URL patterns برای دسترسی به اطلاعات بیماران
"""
from django.urls import path
from crazy_miner.views import (
    CrazyMinerCreateSOAPifyPaymentView,
    CrazyMinerCreatePaymentView,
    CrazyMinerPaymentCallbackView,
    CrazyMinerPaymentStatusView,
    CrazyMinerPaymentListView
)

app_name = 'crazy_miner'

urlpatterns = [
    # دسترسی به اطلاعات بیمار
   
     
    # پرداخت برای SOAPify
    path('soapify-payment/', CrazyMinerCreateSOAPifyPaymentView.as_view(), name='soapify_payment'),
    # ایجاد پرداخت جدید
    path('create/', CrazyMinerCreatePaymentView.as_view(), name='create'),
    
    # دریافت callback از درگاه
    path('callback/', CrazyMinerPaymentCallbackView.as_view(), name='callback'),
    
    # بررسی وضعیت پرداخت
    path('status/<uuid:transaction_id>/', CrazyMinerPaymentStatusView.as_view(), name='status'),
    
    # لیست پرداخت‌های کاربر
    path('list/', CrazyMinerPaymentListView.as_view(), name='list'),
]