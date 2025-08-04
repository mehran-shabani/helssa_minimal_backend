from django.contrib import admin
from django.utils.html import format_html

from .models import CustomUser, Visit, Transaction, Blog, Comment, BoxMoney, Order


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'phone_number', 'email', 'is_active']
    list_filter = ['is_active', 'is_staff']
    search_fields = ['username', 'phone_number', 'email']
    list_per_page = 20


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'urgency', 'created_at']
    list_filter = ['urgency', 'created_at']
    search_fields = ['name', 'description']
    list_per_page = 20

    def get_readonly_fields(self, request, obj=None):
        if obj:  # در حالت ویرایش
            return ['created_at']
        return []


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['trans_id', 'card_num']
    list_per_page = 20
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'preview_image1', 'preview_image2', 'created_at']
    list_filter = ['created_at', 'author']
    search_fields = ['title', 'content']
    readonly_fields = ['preview_image1_large', 'preview_image2_large']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'content', 'author')
        }),
        ('تصویر اول', {
            'fields': ('image1', 'preview_image1_large')
        }),
        ('تصویر دوم', {
            'fields': ('image2', 'preview_image2_large')
        }),
    )

    def preview_image1(self, obj):
        if obj.image1:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image1)
        return '❌'
    preview_image1.short_description = 'تصویر اول'

    def preview_image2(self, obj):
        if obj.image2:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image2)
        return '❌'
    preview_image2.short_description = 'تصویر دوم'

    def preview_image1_large(self, obj):
        if obj.image1:
            return format_html('<img src="{}" width="400" style="max-width: 100%;" />', obj.image1)
        return 'تصویری انتخاب نشده است'
    preview_image1_large.short_description = 'پیش‌نمایش تصویر اول'

    def preview_image2_large(self, obj):
        if obj.image2:
            return format_html('<img src="{}" width="400" style="max-width: 100%;" />', obj.image2)
        return 'تصویری انتخاب نشده است'
    preview_image2_large.short_description = 'پیش‌نمایش تصویر دوم'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'blog', 'likes', 'created_at']
    list_filter = ['created_at']
    search_fields = ['comment']
    list_per_page = 20


@admin.register(BoxMoney)
class BoxMoneyAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount']
    search_fields = ['user__username', 'user__phone_number']
    list_per_page = 20

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['user', 'first_name', 'last_name', 'national_code', 'order_number', 'disease_name', 'download_url']
    list_filter = ['order_number']
    search_fields = ['first_name', 'last_name', 'national_code', 'order_number', 'disease_name']
    list_per_page = 20
    