# ==============================
# chatbot/management/commands/close_open_sessions.py
# ==============================
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model
from chatbot.models import ChatSession

User = get_user_model()


class Command(BaseCommand):
    help = "بستن همه‌ی سشن‌های باز قدیمی‌تر از --hours (پیش‌فرض: 12)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=12,
            help="حداکثر سن سشن (ساعت) برای باز ماندن؛ قدیمی‌تر از این بسته می‌شود.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="فقط شمارش/نمایش؛ تغییری روی دیتابیس اعمال نمی‌شود.",
        )
        parser.add_argument(
            "--username",
            default=None,
            help="(اختیاری) محدود به سشن‌های یک کاربر خاص.",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        dry_run = options["dry_run"]
        username = options.get("username")

        if hours <= 0:
            raise CommandError("--hours باید بزرگ‌تر از صفر باشد.")

        user = None
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"کاربری با username='{username}' یافت نشد.")

        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        qs = ChatSession.objects.filter(is_open=True, started_at__lt=cutoff)
        if user:
            qs = qs.filter(user=user)

        total = qs.count()
        if total == 0:
            scope = f"کاربر '{username}'" if user else "همهٔ کاربران"
            self.stdout.write(self.style.WARNING(f"هیچ سشنِ بازِ قدیمی برای {scope} پیدا نشد."))
            return

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"[DRY-RUN] {total} سشن باز قدیمی‌تر از {hours} ساعت یافت شد؛ تغییری اعمال نشد."
                )
            )
            return

        closed = 0
        for s in qs.iterator():
            try:
                s.end(cutoff)
                closed += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"خطا در بستن سشن #{s.pk}: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Closed {closed} sessions (older than {hours}h; cutoff={cutoff.isoformat()})."
            )
        )