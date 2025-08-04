import json
import pytest
from django.contrib.auth import get_user_model
from medagent.models import PatientSummary, AccessHistory, ChatSession, ChatMessage, SessionSummary
from medagent.tools import GetPatientSummaryTool, SummarizeSessionTool, ImageAnalysisTool, ProfanityCheckTool

User = get_user_model()

@pytest.mark.django_db
def test_get_patient_summary_tool_requires_access(monkeypatch):
    user = User.objects.create_user(username="doc", email="doc@example.com", password="pwd")
    summary_data = {"height": 180}
    PatientSummary.objects.create(user=user, json_data=summary_data)
    tool = GetPatientSummaryTool()

    input_data = {"user_id": str(user.id), "patient_id": str(user.id)}

    # No access history yet -> should raise
    with pytest.raises(PermissionError):
        tool._run(input_data)

    # Grant access
    AccessHistory.objects.create(doctor=user, patient=user)

    result = tool._run(input_data)
    assert json.loads(result) == summary_data

@pytest.mark.django_db
def test_summarize_session_tool_creates_summary(monkeypatch):
    def fake_tb_chat(messages, model="o3-mini"):
        return json.dumps({
            "text_summary": "short summary",
            "chief_complaint": "headache",
            "token_count": 50
        })
    monkeypatch.setattr("medagent.talkbot_client.tb_chat", fake_tb_chat)
    user = User.objects.create_user(username="sumdoc", email="sum@example.com", password="pwd")
    session = ChatSession.objects.create(user=user)
    ChatMessage.objects.create(session=session, role="owner", content="hi")
    ChatMessage.objects.create(session=session, role="assistant", content="hello")
    tool = SummarizeSessionTool()
    result = tool._run(str(session.id))
    assert result == "خلاصه‌سازی انجام شد"  # یا "Summary stored" اگر کد ابزار شما انگلیسی است
    summary = SessionSummary.objects.get(session=session)
    assert summary.text_summary == "short summary"
    assert summary.json_summary.get("chief_complaint") == "headache"
    assert summary.tokens_used == 50

@pytest.mark.django_db
def test_image_analysis_tool(monkeypatch):
    def fake_vision(image_path: str, prompt: str | None = None, model="flux-ai"):
        return {"label": "X-ray", "finding": "normal"}
    monkeypatch.setattr("medagent.talkbot_client.vision_analyze", fake_vision)
    tool = ImageAnalysisTool()
    result = tool._run("/tmp/x.png", prompt="P")
    assert json.loads(result) == {"label": "X-ray", "finding": "normal"}

def test_profanity_check_tool(monkeypatch):
    monkeypatch.setattr("medagent.talkbot_client.profanity", lambda text: {"contains_profanity": True})
    tool = ProfanityCheckTool()
    assert tool._run("bad words") == "True"
    monkeypatch.setattr("medagent.talkbot_client.profanity", lambda text: {"contains_profanity": False})
    assert tool._run("good words") == "False"
