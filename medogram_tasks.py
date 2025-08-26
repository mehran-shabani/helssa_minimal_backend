# medogram_tasks.py
from celery import shared_task
from django.core.management import call_command
from django.conf import settings

User = settings.AUTH_USER_MODEL

@shared_task
def close_open_sessions_task(hours=12):
    """
    معادل اجرای:
    python manage.py close_open_sessions --hours=<hours>
    """
    call_command('close_open_sessions', f'--hours={hours}')

@shared_task
def summarize_chats_for_username_task(username: str, limit=None):
    """
    معادل:
    python manage.py summarize_chats <username> [--limit N]
    """
    if limit is not None:
        call_command('summarize_chats', username, '--limit', str(limit))
    else:
        call_command('summarize_chats', username)

@shared_task
def summarize_all_users_chats_task(limit=None):
    """
    برای همه کاربران فعال، کامند summarize_chats را اجرا می‌کند.
    """
    if limit is not None:
        call_command('summarize_chats', '--all', '--limit', str(limit))
    else:
        call_command('summarize_chats', '--all')