from rest_framework import serializers

from django.conf import settings
from .models import Visit, Transaction, CustomUser, Comment, Blog, BoxMoney

MAX_UPLOAD_SIZE = settings.MAX_UPLOAD_SIZE
class CustomUserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['username', 'email']


class CustomUserProfileJustUserNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['username']


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['phone_number', 'auth_code']


class VisitSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    drug_images = serializers.ImageField(
        max_length=None,
        allow_empty_file=False,
        use_url=True,
        required=False
    )

    class Meta:
        model = Visit
        fields = [
            'id',
            'user',
            'name',
            'urgency',
            'general_symptoms',
            'neurological_symptoms',
            'cardiovascular_symptoms',
            'gastrointestinal_symptoms',
            'respiratory_symptoms',
            'description',
            'created_at',
            'drug_images'
        ]

    def validate_drug_images(self, value):
        if value:
            self.validate_image_size(value)

        return value

    def validate_image_size(self, value):
        if value.size > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(
                f'حجم فایل نمی‌تواند بیشتر از {settings.MAX_UPLOAD_SIZE / 1048576:.1f} مگابایت باشد.'
            )





    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'trans_id', 'amount', 'status', 'created_at', 'updated_at']


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    blog = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'comment', 'likes', 'blog', 'created_at']


class BlogSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Blog
        fields = ['id', 'title', 'content', 'author', 'image1', 'image2', 'created_at', 'comments']


class BoxMoneySerializer(serializers.ModelSerializer):
    class Meta:
        model = BoxMoney
        fields = '__all__'
