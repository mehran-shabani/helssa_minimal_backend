import json
import pytest
from django.contrib.auth import get_user_model
from medagent.models import ChatSession, ChatMessage
from medagent.tools import SummarizeSessionTool, ImageAnalysisTool

User = get_user_model()


@pytest.mark.django_db
def test_summarize_session_error(monkeypatch):
    """ابزار—even در پاسخ خطادار—رشتهٔ ثابتی بازمی‌گرداند؛ همان را انتظار داریم."""
    monkeypatch.setattr(
        "medagent.talkbot_client.tb_chat",
        lambda *a, **k: json.dumps({"text_summary": "", "error": "fail"}),
    )
    user = User.objects.create_user(username="e1", email="e1@x.com", password="p")
    session = ChatSession.objects.create(user=user)
    ChatMessage.objects.create(session=session, role="owner", content="x")

    tool = SummarizeSessionTool()
    out = tool._run(str(session.id))
    assert out == "خلاصه‌سازی انجام شد"


@pytest.mark.django_db
def test_image_analysis_tool_failure(monkeypatch):
    def fake_vision(*_a, **_k):
        raise RuntimeError("vision down")

    monkeypatch.setattr("medagent.talkbot_client.vision_analyze", fake_vision)
    tool = ImageAnalysisTool()
    with pytest.raises(RuntimeError):
        tool._run("/tmp/not_exists.png")
