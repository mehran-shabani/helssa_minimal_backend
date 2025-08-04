import importlib
import sys

import medogram.settings as settings


def test_talkbot_api_key(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['manage.py', 'test'])
    reloaded = importlib.reload(settings)
    assert reloaded.TALKBOT_API_KEY == 'test-key'
