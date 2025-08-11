import pytest
from django.contrib.auth import get_user_model

from chatbot import generateresponse as gr
from chatbot.generateresponse import generate_gpt_response

User = get_user_model()


class DummySummary:
    rewritten_text = "summary"


@pytest.mark.django_db
def test_generate_gpt_response_basic(monkeypatch):
    user = User.objects.create_user(username="u4", password="p", auth_code="888888", phone_number="0914")

    def fake_post(url, payload):
        model = payload.get("model")
        if model == "gpt-4-vision-preview":
            return {"choices": [{"message": {"content": "vision"}}]}
        return {"choices": [{"message": {"content": "reply"}}]}

    monkeypatch.setattr("chatbot.generateresponse._safe_post", fake_post)
    monkeypatch.setattr("chatbot.generateresponse.clean_bot_message", lambda x: x)
    monkeypatch.setattr("chatbot.generateresponse.get_or_create_global_summary", lambda u: DummySummary())
    monkeypatch.setattr("chatbot.generateresponse.get_or_update_session_summary", lambda s: DummySummary())

    out = generate_gpt_response(user, "سلام", image_b64_list=["data:image/jpeg;base64,AAAA"], new_session=True)
    assert "reply" in out


def test_safe_post_and_build_images(monkeypatch, tmp_path):
    calls = {"count": 0}

    class DummyResp:
        def __init__(self, ok=True, status=200, text="", data=None):
            self.ok = ok
            self.status_code = status
            self.text = text
            self._data = data or {}

        def json(self):
            return self._data

    def fake_post(url, json, headers, timeout):
        calls["count"] += 1
        if calls["count"] < 2:
            raise gr.requests.RequestException("fail")
        return DummyResp(data={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(gr.requests, "post", fake_post)
    res = gr._safe_post("u", {})
    assert res["choices"][0]["message"]["content"] == "ok"

    file_path = tmp_path / "a.jpg"
    file_path.write_bytes(b"data")
    with file_path.open("rb") as f:
        parts = gr._build_user_content_with_images("t", image_files=[f])
    assert parts[-1]["text"] == "t"
