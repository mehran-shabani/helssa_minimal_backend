# doctor_online/serializers.py
from rest_framework import serializers
from .models import Doctor


class DoctorOnCallSerializer(serializers.ModelSerializer):
    """
    خروجی:
        id          : int
        full_name   : str  ← first_name + last_name
        specialty   : str
        image       : str  ← آدرس مطلق یا "" اگر عکسی نباشد
    """
    full_name = serializers.SerializerMethodField()
    image     = serializers.SerializerMethodField()

    class Meta:
        model  = Doctor
        fields = ("id", "full_name", "specialty", "image")
        read_only_fields = fields

    # ---------- سازنده‌ی full_name ----------
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    # ---------- سازنده‌ی URL عکس ----------
    def get_image(self, obj):
        if obj.image and hasattr(obj.image, "url"):
            request = self.context.get("request")
            url = obj.image.url
            return request.build_absolute_uri(url) if request else url
        return ""