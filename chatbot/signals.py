from django.db.models.signals import post_save
from django.dispatch import receiver

from chatbot.models import ChatMessage, ChatSummary
from .tasks import rebuild_session_summary, rebuild_global_summary


@receiver(post_save, sender=ChatMessage)
def on_new_message(sender, instance: ChatMessage, created: bool, **kwargs):
    if not created:
        return

    session = instance.session
    # Mark existing session summary stale or create a placeholder
    summary = session.summaries.order_by("-updated_at").first()
    if summary:
        if not summary.is_stale:
            summary.is_stale = True
            summary.save(update_fields=["is_stale"])
    else:
        ChatSummary.objects.create(
            user=session.user,
            session=session,
            raw_text="",
            rewritten_text="",
            structured_json={},
            is_stale=True,
        )
    try:
        rebuild_session_summary.apply_async(kwargs={"session_id": session.id}, countdown=60)
    except Exception:
        pass

    # Schedule global summary rebuild with a longer delay
    try:
        rebuild_global_summary.apply_async(kwargs={"user_id": session.user_id}, countdown=120)
    except Exception:
        pass
