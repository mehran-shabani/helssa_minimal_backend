# medagent/tests/conftest.py
import json
import random
import pytest

class DummyAgent:
    def __call__(self, *_, **__):
        return "mock assistant reply"
    invoke = __call__
    run = __call__

@pytest.fixture(autouse=True)
def auto_mock_external(monkeypatch):
    """Mock های عمومی برای تمام تست‌ها"""

    monkeypatch.setattr(
        "medagent.talkbot_client.profanity",
        lambda text: {"contains_profanity": False}
    )
    monkeypatch.setattr(
        "medagent.talkbot_client.vision_analyze",
        lambda url, *_, **__: {"label": "X-ray", "finding": "normal"}
    )
    monkeypatch.setattr(
        "medagent.talkbot_client.tb_chat",
        lambda messages, *_, **__: json.dumps({
            "text_summary": "mock summary",
            "chief_complaint": "mock complaint",
            "token_count": 42
        })
    )
    monkeypatch.setattr("medagent.agent_setup.agent", DummyAgent())
    monkeypatch.setattr("medagent.sms.send_sms", lambda *_, **__: True)
    monkeypatch.setattr(random, "randint", lambda *_, **__: 123456)
