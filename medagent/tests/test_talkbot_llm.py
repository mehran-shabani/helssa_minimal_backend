import importlib
import json
import pytest
import medagent.talkbot_llm as tl


def reload_module():
    importlib.reload(tl)


def test_llm_call_success(monkeypatch):
    reload_module()

    # پچ روی نسخهٔ داخل tl (نه ماژول اصلی)
    monkeypatch.setattr(
        tl, "tb_chat",
        lambda *a, **k: json.dumps(
            {"text_summary": "mock summary", "token_count": 42}
        )
    )
    llm = tl.TalkBotLLM()
    data = json.loads(llm._call("hi"))
    assert data["text_summary"] == "mock summary"
    assert data["token_count"] == 42


def test_llm_call_failure(monkeypatch):
    reload_module()
    monkeypatch.setattr(tl, "tb_chat", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    llm = tl.TalkBotLLM()
    with pytest.raises(RuntimeError):
        llm._call("hi")
