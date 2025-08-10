# chatbot / management / commands / close_open_sessions.py

# ==============================
# management/commands/close_open_sessions.py
# ==============================
from django.core.management.base import BaseCommand
from django.utils import timezone
from chatbot.models import ChatSession

class Command(BaseCommand):
    help = "Close all open chat sessions older than --hours (default: 12)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=12, help="Max session age in hours")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(hours=options["hours"])
        qs = ChatSession.objects.filter(is_open=True, started_at__lt=cutoff)
        count = qs.count()
        for s in qs:
            s.end(cutoff)
        self.stdout.write(self.style.SUCCESS(f"Closed {count} sessions."))