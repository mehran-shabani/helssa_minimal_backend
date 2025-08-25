from rest_framework import serializers
from crazy_miner.models import CrazyMinerPayment, CrazyMinerPaymentLog



class CrazyMinerCreatePaymentSerializer(serializers.Serializer):
    """سریالایزر برای ایجاد درخواست شارژ کیف پول"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=0)
    description = serializers.CharField(required=False, allow_blank=True, default="شارژ کیف پول")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("مبلغ باید بیشتر از صفر باشد")
        if value < 10000:  # حداقل 10,000 ریال
            raise serializers.ValidationError("حداقل مبلغ شارژ 10,000 ریال است")
        return value

    amount = serializers.DecimalField(max_digits=10, decimal_places=0)
    description = serializers.CharField(required=False, allow_blank=True, default="شارژ کیف پول")
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("مبلغ باید بیشتر از صفر باشد")
        if value < 10000:  # حداقل 10,000 ریال
            raise serializers.ValidationError("حداقل مبلغ شارژ 10,000 ریال است")
        return value


class CrazyMinerPaymentCallbackSerializer(serializers.Serializer):
    """سریالایزر برای callback درگاه پرداخت"""
    trans_id = serializers.CharField()
    id_get = serializers.CharField()
    
    # فیلدهای اختیاری که ممکن است از درگاه بیاید
    amount = serializers.DecimalField(max_digits=10, decimal_places=0, required=False)
    status = serializers.CharField(required=False)
    tracking_code = serializers.CharField(required=False)


class CrazyMinerPaymentSerializer(serializers.ModelSerializer):
    """سریالایزر برای مدل CrazyMinerPayment"""
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CrazyMinerPayment
        fields = [
            'id', 'user', 'user_phone', 'amount', 'status', 'status_display',
            'gateway_transaction_id', 'gateway_reference_id', 'gateway_tracking_code',
            'description', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'gateway_transaction_id', 
            'gateway_reference_id', 'gateway_tracking_code',
            'created_at', 'updated_at', 'completed_at'
        ]


class CrazyMinerPaymentStatusSerializer(serializers.Serializer):
    """سریالایزر برای پاسخ وضعیت پرداخت"""
    transaction_id = serializers.UUIDField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=0)
    gateway_tracking_code = serializers.CharField(required=False)
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(required=False)
    payment_url = serializers.URLField(required=False)


class CrazyMinerPaymentLogSerializer(serializers.ModelSerializer):
    """سریالایزر برای مدل CrazyMinerPaymentLog"""
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    
    class Meta:
        model = CrazyMinerPaymentLog
        fields = ['id', 'payment', 'log_type', 'log_type_display', 'message', 'raw_data', 'created_at']
        read_only_fields = ['id', 'created_at']
