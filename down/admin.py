# down/admin.py

from django.contrib import admin
from .models import AppUpdate

@admin.register(AppUpdate)
class AppUpdateAdmin(admin.ModelAdmin):
    list_display = [
        'version', 
        'is_update_available', 
        'force_update', 
        'created_at',
        'get_status'
    ]
    
    list_filter = [
        'is_update_available', 
        'force_update', 
        'created_at'
    ]
    
    search_fields = ['version', 'release_notes']
    
    readonly_fields = ['created_at', 'updated_at']
    
    list_editable = ['is_update_available', 'force_update']
    
    ordering = ['-created_at']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('version', 'is_update_available', 'force_update'),
            'classes': ('wide',)
        }),
        ('توضیحات آپدیت', {
            'fields': ('release_notes',),
            'classes': ('wide',)
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'اطلاعات تاریخ و زمان'
        }),
    )
    
    def get_status(self, obj):
        if obj.is_update_available:
            if obj.force_update:
                return "🔴 آپدیت اجباری"
            else:
                return "🟡 آپدیت در دسترس"
        return "🟢 غیرفعال"
    
    get_status.short_description = 'وضعیت'
    get_status.admin_order_field = 'is_update_available'
    
    def save_model(self, request, obj, form, change):
        # اگر این آپدیت فعال شد، بقیه رو غیرفعال کن
        if obj.is_update_available:
            AppUpdate.objects.exclude(pk=obj.pk).update(is_update_available=False)
        
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """نمایش آپدیت‌های جدید اول"""
        return super().get_queryset(request).order_by('-created_at')
    
    actions = ['activate_update', 'deactivate_update', 'make_force_update']
    
    def activate_update(self, request, queryset):
        """فعال کردن آپدیت انتخاب شده"""
        if queryset.count() > 1:
            self.message_user(request, "فقط می‌توانید یک آپدیت را فعال کنید", level='ERROR')
            return
        
        # غیرفعال کردن همه آپدیت‌ها
        AppUpdate.objects.all().update(is_update_available=False)
        
        # فعال کردن آپدیت انتخاب شده
        updated = queryset.update(is_update_available=True)
        
        self.message_user(request, f"{updated} آپدیت فعال شد")
    
    activate_update.short_description = "فعال کردن آپدیت انتخاب شده"
    
    def deactivate_update(self, request, queryset):
        """غیرفعال کردن آپدیت‌ها"""
        updated = queryset.update(is_update_available=False)
        self.message_user(request, f"{updated} آپدیت غیرفعال شد")
    
    deactivate_update.short_description = "غیرفعال کردن آپدیت‌ها"
    
    def make_force_update(self, request, queryset):
        """تبدیل به آپدیت اجباری"""
        updated = queryset.update(force_update=True)
        self.message_user(request, f"{updated} آپدیت اجباری شد")
    
    make_force_update.short_description = "تبدیل به آپدیت اجباری"



# اضافه کردن گروه‌بندی در Admin
class AdminConfig:
    def __init__(self):
        admin.site.site_header = "Management Panel"
        admin.site.site_title = "Medogram Admin"
        admin.site.index_title = "Welcome to Medogram admin panel"
        admin.site.enable_nav_sidebar = True
        admin.site.site_url = 'https://helssa.ir'
admin_config = AdminConfig()
