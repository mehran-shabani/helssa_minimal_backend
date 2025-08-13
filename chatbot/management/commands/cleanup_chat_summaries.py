# chatbot / management / commands / cleanup_chat_summaries.py

# ==============================
# management/commands/cleanup_chat_summaries.py
# ==============================
from django.core.management.base import BaseCommand
from django.db.models import Max
from chatbot.models import ChatSummary


class Command(BaseCommand):
    help = "Remove duplicate ChatSummary records, keeping the newest per (user, session)."

    def handle(self, *args, **options):
        keep_ids = list(
            ChatSummary.objects.values("user_id", "session_id")
            .annotate(latest_id=Max("id"))
            .values_list("latest_id", flat=True)
        )
        deleted, _ = ChatSummary.objects.exclude(id__in=keep_ids).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} duplicate summaries."))
