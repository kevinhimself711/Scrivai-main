"""Scrivai SDK 核心模块。

顶层导出采用延迟加载，避免在仅使用部分能力时强制导入可选依赖。
"""

from importlib import import_module

__all__ = [
    "Project",
    "ProjectConfig",
    "LLMClient",
    "LLMConfig",
    "KnowledgeStore",
    "SearchResult",
    "GenerationEngine",
    "GenerationContext",
    "AuditEngine",
    "AuditResult",
]

_EXPORT_MAP = {
    "Project": ("core.project", "Project"),
    "ProjectConfig": ("core.project", "ProjectConfig"),
    "LLMClient": ("core.llm", "LLMClient"),
    "LLMConfig": ("core.llm", "LLMConfig"),
    "KnowledgeStore": ("core.knowledge.store", "KnowledgeStore"),
    "SearchResult": ("core.knowledge.store", "SearchResult"),
    "GenerationEngine": ("core.generation.engine", "GenerationEngine"),
    "GenerationContext": ("core.generation.context", "GenerationContext"),
    "AuditEngine": ("core.audit.engine", "AuditEngine"),
    "AuditResult": ("core.audit.engine", "AuditResult"),
}


def __getattr__(name: str):
    """按需加载导出符号。"""
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module 'core' has no attribute {name!r}")

    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
