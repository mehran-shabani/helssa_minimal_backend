import json
import importlib
import pytest
import medagent.talkbot_client as tc


def reload_module():
    importlib.reload(tc)


class DummyResp:
    def __init__(self, data):
        self._data = data
        self.text = json.dumps(data)
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test__headers_without_token(monkeypatch):
    reload_module()
    monkeypatch.setattr(tc, "TALKBOT_TOKEN", None)
    h = tc._headers()
    assert h["Authorization"] == "Bearer None"


def test_tb_chat_success(monkeypatch):
    reload_module()
    payload = {"text_summary": "Diagnosis: OK", "token_count": 12}
    monkeypatch.setattr(
        tc,
        "requests",
        type("R", (), {"post": lambda *a, **k: DummyResp(payload)}),
    )
    res = tc.tb_chat([{"role": "user", "content": "hi"}])
    data = json.loads(res)
    assert data["text_summary"].startswith("Diagnosis")
    assert data["token_count"] == 12


def test_vision_analyze_success(monkeypatch, tmp_path):
    reload_module()
    img = tmp_path / "x.png"
    img.write_text("X")
    monkeypatch.setattr(tc, "encode_image_to_base64", lambda p: "DATA")
    monkeypatch.setattr(
        tc,
        "requests",
        type(
            "R",
            (),
            {
                "post": lambda *a, **k: DummyResp(
                    {"ok": True, "payload": k["json"]}
                )
            },
        ),
    )
    out = tc.vision_analyze(str(img), prompt="detail")
    msg = out["payload"]["messages"][0]["content"][0]
    assert out["ok"] is True
    assert msg["image_url"]["url"] == "DATA"
