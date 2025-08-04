# down/models.py

from django.db import models

class AppUpdate(models.Model):
    version = models.CharField(max_length=20, help_text="e.g., 1.2.3")
    is_update_available = models.BooleanField(default=False, help_text="آیا آپدیت جدید موجود است؟")
    release_notes = models.TextField(blank=True, help_text="توضیحات آپدیت")
    force_update = models.BooleanField(default=False, help_text="آیا آپدیت اجباری است؟")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "App Update"
        verbose_name_plural = "App Updates"

    def __str__(self):
        return f"Version {self.version} - Available: {self.is_update_available}"