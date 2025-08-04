from django.contrib import admin
from .models import Doctor
from django.core.exceptions import ValidationError
from django.forms import ModelForm

class DoctorAdminForm(ModelForm):
    def clean(self):
        cleaned = super().clean()
        is_oncall = cleaned.get('is_oncall', False)

        if is_oncall:
            qs = Doctor.objects.filter(is_oncall=True).exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('در هر لحظه تنها یک پزشک می‌تواند on-call باشد.')
        return cleaned

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display  = ('first_name', 'last_name', 'email', 'specialty', 'is_oncall')
    list_filter   = ('specialty', 'is_oncall')
    search_fields = ('first_name', 'last_name', 'specialty')
    form          = DoctorAdminForm
