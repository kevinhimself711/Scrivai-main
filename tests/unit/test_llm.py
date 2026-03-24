"""LLMClient unit tests."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from core.llm import LLMClient, LLMConfig


def _make_config(**overrides) -> LLMConfig:
    defaults = {
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 1024,
        "api_base": None,
        "api_key": None,
    }
    defaults.update(overrides)
    return LLMConfig(**defaults)


def _mock_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


@patch("core.llm.litellm.completion")
def test_chat_basic(mock_completion):
    mock_completion.return_value = _mock_response("你好世界")
    client = LLMClient(_make_config())

    messages = [{"role": "user", "content": "你好"}]
    result = client.chat(messages)

    assert result == "你好世界"
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["messages"] == messages
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["max_tokens"] == 1024


@patch("core.llm.litellm.completion")
def test_chat_with_template_string(mock_completion):
    mock_completion.return_value = _mock_response("回答")
    client = LLMClient(_make_config())

    result = client.chat_with_template("请分析：{{ topic }}", {"topic": "AI"})

    assert result == "回答"
    sent_content = mock_completion.call_args[1]["messages"][0]["content"]
    assert sent_content == "请分析：AI"


@patch("core.llm.litellm.completion")
def test_chat_with_template_file(mock_completion):
    mock_completion.return_value = _mock_response("文件模板回答")
    client = LLMClient(_make_config())

    with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False, encoding="utf-8") as file:
        file.write("项目名称：{{ name }}")
        tmp_path = file.name

    try:
        result = client.chat_with_template(tmp_path, {"name": "Scrivai"})
        assert result == "文件模板回答"
        sent_content = mock_completion.call_args[1]["messages"][0]["content"]
        assert sent_content == "项目名称：Scrivai"
    finally:
        os.unlink(tmp_path)


@patch("core.llm.litellm.completion")
def test_chat_with_template_variables(mock_completion):
    mock_completion.return_value = _mock_response("ok")
    client = LLMClient(_make_config())

    variables = {
        "items": ["变电站", "输电线路"],
        "meta": {"author": "张三", "version": 2},
    }
    template = "项目：{% for i in items %}{{ i }} {% endfor %}作者：{{ meta.author }}"
    result = client.chat_with_template(template, variables)

    assert result == "ok"
    sent = mock_completion.call_args[1]["messages"][0]["content"]
    assert "变电站" in sent
    assert "输电线路" in sent
    assert "张三" in sent


@patch("core.llm.litellm.completion")
def test_config_api_key_passthrough(mock_completion):
    mock_completion.return_value = _mock_response("ok")
    client = LLMClient(_make_config(api_key="sk-test-123"))

    client.chat([{"role": "user", "content": "test"}])

    assert mock_completion.call_args[1]["api_key"] == "sk-test-123"


@patch("core.llm.litellm.completion")
def test_config_api_base(mock_completion):
    mock_completion.return_value = _mock_response("ok")
    client = LLMClient(_make_config(api_base="https://custom.api.com/v1"))

    client.chat([{"role": "user", "content": "test"}])

    assert mock_completion.call_args[1]["api_base"] == "https://custom.api.com/v1"


@patch("core.llm.litellm.completion")
def test_dashscope_compatible_mode_adds_openai_prefix(mock_completion):
    mock_completion.return_value = _mock_response("ok")
    client = LLMClient(
        _make_config(
            model="qwen3-max",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    )

    client.chat([{"role": "user", "content": "test"}])

    assert mock_completion.call_args[1]["model"] == "openai/qwen3-max"


@patch.dict(os.environ, {}, clear=True)
def test_http_session_disables_system_proxy_by_default():
    client = LLMClient(_make_config())

    session = client._build_http_session()

    assert session.trust_env is False


@patch.dict(os.environ, {"LLM_USE_SYSTEM_PROXY": "true"}, clear=True)
def test_http_session_can_enable_system_proxy():
    client = LLMClient(_make_config())

    session = client._build_http_session()

    assert session.trust_env is True


@patch("core.llm.requests.Session")
@patch("core.llm.litellm.completion", side_effect=ModuleNotFoundError("litellm is not installed"))
def test_missing_litellm_falls_back_to_openai_compatible(mock_completion, mock_session_cls):
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = False
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "fallback ok"}}],
    }
    mock_session.post.return_value = mock_response
    mock_session_cls.return_value = mock_session

    client = LLMClient(
        _make_config(
            model="qwen3-max",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="sk-test",
        )
    )

    result = client.chat([{"role": "user", "content": "test"}])

    assert result == "fallback ok"
    assert mock_session.trust_env is False
    assert mock_session.post.call_args[0][0] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert mock_session.post.call_args[1]["json"]["model"] == "qwen3-max"
    assert mock_session.post.call_args[1]["headers"]["Authorization"] == "Bearer sk-test"
