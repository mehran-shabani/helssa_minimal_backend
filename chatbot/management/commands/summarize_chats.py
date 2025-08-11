# chatbot / management / commands / summarize_chats.py

# ==============================
# management/commands/summarize_chats.py
# ==============================
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from chatbot.tasks import rebuild_global_summary
from chatbot.utils.text_summary import get_or_create_global_summary

User = get_user_model()

class Command(BaseCommand):
    help = "Create or refresh a global ChatSummary for given user (optionally limit sessions)."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username to summarise")
        parser.add_argument("--limit", type=int, default=None, help="Limit to last N sessions")

    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(str(exc))

        # Ensure a summary exists and rebuild it synchronously
        get_or_create_global_summary(user)
        rebuild_global_summary(user.id, limit_sessions=options["limit"])
        self.stdout.write(self.style.SUCCESS("Summary generated."))