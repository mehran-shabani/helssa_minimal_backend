# ==============================
# chatbot/management/commands/summarize_chats.py
# ==============================
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from chatbot.utils.text_summary import summarize_user_chats

User = get_user_model()


class Command(BaseCommand):
    help = (
        "خلاصه‌سازی چت‌ها. "
        "می‌توانید username بدهید یا از --all برای همهٔ کاربران فعال استفاده کنید."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            nargs="?",
            help="نام کاربری هدف برای خلاصه‌سازی. در صورت استفاده از --all لازم نیست.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="محدود کردن به N سشن آخر (اختیاری).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="for_all",
            help="خلاصه‌سازی برای همهٔ کاربران فعال.",
        )
        parser.add_argument(
            "--model",
            default=None,
            help="(اختیاری) فقط برای لاگ؛ مدل واقعی از settings خوانده می‌شود.",
        )

    def handle(self, *args, **options):
        username = options.get("username")
        limit = options.get("limit")
        for_all = options.get("for_all")

        if for_all and username:
            raise CommandError("یا username بده یا --all؛ هر دو با هم قابل استفاده نیستند.")

        if not for_all and not username:
            raise CommandError("باید یا username بدهی یا از --all استفاده کنی.")

        if limit is not None and limit <= 0:
            raise CommandError("--limit باید مثبت باشد.")

        if for_all:
            qs = User.objects.filter(is_active=True).only("id", "username")
            total = qs.count()
            if total == 0:
                self.stdout.write(self.style.WARNING("هیچ کاربر فعالی یافت نشد."))
                return

            summarized = 0
            skipped_no_data = 0
            failed = 0

            for u in qs.iterator():
                try:
                    summarize_user_chats(u, limit_sessions=limit)
                    summarized += 1
                except ValueError as e:
                    skipped_no_data += 1
                    self.stdout.write(self.style.WARNING(f"'{u.username}': {e}"))
                except Exception as e:
                    failed += 1
                    self.stderr.write(self.style.ERROR(f"خطا برای کاربر '{u.username}': {e}"))

            msg = f"خلاصه‌سازی موفق برای {summarized} کاربر."
            if skipped_no_data:
                msg += f" (بدون داده: {skipped_no_data})"
            if failed:
                msg += f" (ناموفق: {failed})"
            self.stdout.write(self.style.SUCCESS(msg))
            return

        # حالت تک‌کاربره
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"کاربری با username='{username}' یافت نشد.")

        try:
            summary = summarize_user_chats(user, limit_sessions=limit)
        except ValueError as e:
            self.stdout.write(self.style.WARNING(f"{e}"))
            return
        except Exception as e:
            raise CommandError(f"خطا در خلاصه‌سازی کاربر '{username}': {e}")

        pk = getattr(summary, "pk", None)
        if pk:
            self.stdout.write(self.style.SUCCESS(f"Summary #{pk} برای کاربر '{username}' ایجاد/به‌روزرسانی شد."))
        else:
            self.stdout.write(self.style.SUCCESS(f"خلاصه برای کاربر '{username}' ایجاد/به‌روزرسانی شد."))