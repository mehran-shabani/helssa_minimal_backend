"""
App configuration for the medagent Django application.

This ensures that signal handlers are connected when the application
starts. The ready() method imports signal modules to register them.
"""

from django.apps import AppConfig

class MedAgentConfig(AppConfig):
    name = 'medagent'

