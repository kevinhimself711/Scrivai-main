"""LLM client wrapper.

Provides a thin wrapper around litellm and a direct OpenAI-compatible fallback.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import jinja2
import requests

try:
    import litellm
except ImportError:  # pragma: no cover - optional dependency
    class _MissingLiteLLM:
        @staticmethod
        def completion(**kwargs):  # noqa: ARG004
            raise ModuleNotFoundError("litellm is not installed")

    litellm = _MissingLiteLLM()

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM runtime config."""

    model: str
    temperature: float
    max_tokens: int
    api_base: Optional[str]
    api_key: Optional[str]


class LLMClient:
    """LLM client with litellm support and OpenAI-compatible fallback."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def chat(self, messages: list[dict]) -> str:
        """Send a chat request and return the generated text."""
        kwargs: dict = {
            "model": self._resolve_litellm_model_name(),
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        if self._config.api_base:
            kwargs["api_base"] = self._config.api_base
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key

        logger.debug("LLM request: model=%s messages=%d", kwargs["model"], len(messages))
        try:
            response = litellm.completion(**kwargs)
        except ModuleNotFoundError:
            if not self._can_use_openai_compatible_fallback():
                raise ModuleNotFoundError(
                    "未安装 litellm，且当前配置不足以走 OpenAI 兼容接口直连。"
                    " 请安装 litellm，或提供 api_base、api_key 和 model。"
                )
            logger.warning("litellm 不可用，回退到 OpenAI 兼容接口直连模式。")
            return self._chat_via_openai_compatible(messages)

        content = response.choices[0].message.content
        logger.debug("LLM response chars=%d", len(content) if content else 0)
        return content

    def chat_with_template(self, template: str, variables: dict) -> str:
        """Render a Jinja2 template and send it to the model."""
        if os.path.isfile(template):
            with open(template, encoding="utf-8") as file:
                template_text = file.read()
        else:
            template_text = template

        rendered = jinja2.Template(template_text).render(**variables)
        return self.chat([{"role": "user", "content": rendered}])

    def _resolve_litellm_model_name(self) -> str:
        model = (self._config.model or "").strip()
        api_base = (self._config.api_base or "").strip().lower()
        if model and "dashscope" in api_base and "compatible-mode" in api_base and "/" not in model:
            return f"openai/{model}"
        return model

    def _resolve_openai_compatible_model_name(self) -> str:
        model = (self._config.model or "").strip()
        if model.startswith("openai/"):
            return model.split("/", 1)[1]
        return model

    def _can_use_openai_compatible_fallback(self) -> bool:
        return bool(self._config.api_base and self._config.api_key and self._config.model)

    def _build_http_session(self) -> requests.Session:
        session = requests.Session()
        use_system_proxy = os.getenv("LLM_USE_SYSTEM_PROXY", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        session.trust_env = use_system_proxy
        if not use_system_proxy:
            session.proxies.clear()
        return session

    def _chat_via_openai_compatible(self, messages: list[dict]) -> str:
        endpoint = f"{self._config.api_base.rstrip('/')}/chat/completions"
        payload = {
            "model": self._resolve_openai_compatible_model_name(),
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        request_timeout = float(os.getenv("LLM_REQUEST_TIMEOUT", "180").strip() or "180")

        try:
            with self._build_http_session() as session:
                response = session.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=(20, request_timeout),
                )
                response.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            if getattr(exc, "response", None) is not None and exc.response is not None:
                detail = exc.response.text.strip()
            if detail:
                raise RuntimeError(f"OpenAI 兼容接口调用失败: {detail}") from exc
            raise RuntimeError(f"OpenAI 兼容接口调用失败: {exc}") from exc

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "".join(parts).strip()
        return str(content).strip()
