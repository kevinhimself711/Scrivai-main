"""共享测试 fixtures 和配置。"""

import os

import pytest
from dotenv import load_dotenv

from core.llm import LLMClient, LLMConfig

load_dotenv()


def has_real_api() -> bool:
    """检查是否存在可用的真实 API 配置。"""
    api_key = os.getenv("API_KEY") or os.getenv("LLM_API_KEY")
    return bool(api_key and os.getenv("MODEL_NAME") and os.getenv("BASE_URL"))


skip_if_no_api = pytest.mark.skipif(
    not has_real_api(),
    reason="需要设置 API_KEY/LLM_API_KEY、MODEL_NAME、BASE_URL 环境变量",
)


@pytest.fixture
def real_llm_client() -> LLMClient:
    """创建真实 LLM 客户端，使用较低输出长度。"""
    config = LLMConfig(
        model=os.getenv("MODEL_NAME", "qwen3-max"),
        temperature=0.3,
        max_tokens=256,
        api_base=os.getenv("BASE_URL"),
        api_key=os.getenv("API_KEY") or os.getenv("LLM_API_KEY"),
    )
    return LLMClient(config)


@pytest.fixture
def real_llm_client_long() -> LLMClient:
    """创建支持较长输出的真实 LLM 客户端。"""
    config = LLMConfig(
        model=os.getenv("MODEL_NAME", "qwen3-max"),
        temperature=0.3,
        max_tokens=512,
        api_base=os.getenv("BASE_URL"),
        api_key=os.getenv("API_KEY") or os.getenv("LLM_API_KEY"),
    )
    return LLMClient(config)
