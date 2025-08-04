from rest_framework import serializers
from .models import AppUpdate

class AppUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppUpdate
        fields = ['version', 'release_notes', 'force_update', 'created_at']

class AppUpdateStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    update_available = serializers.BooleanField()
    version = serializers.CharField(required=False)
    release_notes = serializers.CharField(required=False, allow_blank=True)
    force_update = serializers.BooleanField(required=False)
    message = serializers.CharField()