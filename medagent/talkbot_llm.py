# medagent/talkbot_llm.py
"""Minimal LangChain LLM wrapper around TalkBot chat completions."""

from __future__ import annotations

from typing import List

from langchain_core.language_models import BaseLLM
from langchain_core.outputs import Generation

from medagent.talkbot_client import tb_chat


class TalkBotLLM(BaseLLM):
    model: str = "o3-mini"

    def _call(self, prompt: str, stop: List[str] | None = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        return tb_chat(messages, model=self.model)

    def _generate(self, prompts: List[str], stop: List[str] | None = None):
        return [Generation(text=self._call(p, stop)) for p in prompts]

    @property
    def _llm_type(self) -> str:  # noqa: D401
        return "talkbot"
