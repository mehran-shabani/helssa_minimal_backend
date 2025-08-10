from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings
from django.conf.urls.static import static

schema_view = get_schema_view(
    openapi.Info(
        title="API Documentation",
        default_version='v1',
        description="API documentation for the project",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path('api/', include('telemedicine.roots'), name='home'),
                  path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
                  path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
                  path('chat/', include('chatbot.roots')),
                  path('certificate/', include('certificate.roots')),
                  path('down/', include('down.roots')),
                  path('doc/', include('doctor_online.roots')),
                  path('sub/', include('sub.roots'))

                ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
