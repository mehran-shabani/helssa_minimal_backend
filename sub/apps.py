"""
App configuration for the medagent Django application.

This ensures that signal handlers are connected when the application
starts. The ready() method imports signal modules to register them.
"""

from django.apps import AppConfig

class SubConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sub'
    verbose_name = "مدیریت اشتراک"

    def ready(self):

        import sub.signals


    
