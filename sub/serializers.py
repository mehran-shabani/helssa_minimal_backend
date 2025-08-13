from rest_framework import serializers
from .models import Plan, Subscription, Specialty, TokenTopUp, SpecialtyAccess

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ("code","name","monthly_price","daily_char_limit","daily_requests_limit","max_tokens_per_request","allow_vision","max_images","allow_agent_tools","priority")

class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ("code","name","description")

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer()
    class Meta:
        model = Subscription
        fields = ("id","plan","started_at","expires_at","active")

class TokenTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = TokenTopUp
        fields = ("id","char_balance","created_at","note")
