"""core 包的安全导入测试。"""


def test_core_lazy_exports_available_without_optional_dependencies() -> None:
    """在缺少 qmd/litellm 等可选依赖时，core 顶层导出仍应可访问。"""
    import core

    assert core.LLMClient.__name__ == "LLMClient"
    assert core.KnowledgeStore.__name__ == "KnowledgeStore"
