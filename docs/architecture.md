# Scrivai 架构设计

## 1. 核心定位

可配置的通用文档生成与审核框架（Python 库）。面向横向项目中反复出现的两类需求：
- **审核**：基于规章制度/标准，逐要点审核文档合规性，输出审核报告
- **生成**：基于用户输入 + 历史案例库，按固定章节模板生成长文档，保证全文连贯

设计原则：
- **库优先**：核心交付物是 Python 包，硕士们 `import scrivai` 直接用
- **原子化**：每个组件独立可用，不强制组合
- **可配置**：不同项目通过配置文件接入，不改框架代码
- **MVP**：先跑通一个项目，再泛化

## 2. 系统总览

```
┌─────────────────────────────┐
│      Project (入口)         │  ← 极简配置加载 + 组件组装
│   .llm / .store / .gen /    │
│   .ctx / .audit             │
└──────────────┬──────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
┌───────┴────┐  ┌────┴────────┐
│  生成引擎  │  │   审核引擎    │  ← 两个独立、解耦的核心引擎
│ Generation │  │    Audit     │
└───────┬────┘  └────┬────────┘
        │             │
┌───────┴───┐   ┌────┴───────┐
│ 上下文工具 │   │            │  ← 独立的上下文管理组件
│   Context │   │            │
└───────┬───┘   └────────────┘
        │
┌───────┴─────────────────────┐
│         LLM 调用层           │  ← 统一 LLM 封装（litellm）
│        LLM Client           │
└──────────────┬──────────────┘
               │
┌──────────────┴──────────────┐
│         知识库               │  ← 基于 qmd 的统一检索
│    Knowledge Store          │
│  (案例/规则统一管理)        │
└─────────────────────────────┘

┌─────────────────┐   ┌─────────────────┐
│   切片工具      │   │   Doc Pipeline  │  ← 旁路工具
└─────────────────┘   └─────────────────┘
```

## 3. LLM 调用层

基于 litellm 的薄封装，支持多 provider。

```python
class LLMClient:
    def chat(self, messages: list[dict]) -> str
    def chat_with_template(self, template: str, variables: dict) -> str
```

**不使用 Agent 框架**——Scrivai 的编排逻辑由代码控制，LLM 只负责内容生成和判断。

## 4. Prompt 模板管理

统一使用 Jinja2 管理所有 prompt 模板，采用 **j2 + md 分离模式**。

### 模板文件结构

```
templates/prompts/
├── base.j2              # 基础骨架模板（包含 {{ prompt_content }} 变量）
├── summarize.j2         # 摘要模板骨架
├── summarize.md         # 摘要模板内容（实际指令）
├── extract_terms.j2     # 术语提取骨架
├── extract_terms.md     # 术语提取内容
├── extract_references.j2
├── extract_references.md
├── audit.j2
├── audit.md
├── clean.j2
└── clean.md
```

### j2 + md 分离模式

每个 prompt 由两个文件组成：
- **`.j2` 文件**：Jinja2 骨架模板，包含 `{{ prompt_content }}` 变量占位
- **`.md` 文件**：实际的 prompt 指令内容

加载时，`_load_template()` 函数将 `.md` 内容注入 `.j2` 骨架，生成完整 prompt。

### 模板类型

| 类型 | 用途 | 文件 |
|------|------|------|
| 摘要提取 | 前文摘要 | `summarize.j2` + `summarize.md` |
| 术语提取 | 术语表构建 | `extract_terms.j2` + `extract_terms.md` |
| 引用提取 | 交叉引用 | `extract_references.j2` + `extract_references.md` |
| 审核 | checkpoint 判定 | `audit.j2` + `audit.md` |
| 清洗 | 文档清洗 | `clean.j2` + `clean.md` |

### 章节生成模板变量

用户自定义章节模板时，可使用以下变量：

```jinja2
## 工程概况

请根据以下信息撰写本章：

### 用户输入
{{ user_inputs | tojson }}

### 相关历史案例
{% for case in retrieved_cases %}
--- 案例 {{ loop.index }} ---
{{ case.content }}
{% endfor %}

### 前文摘要
{{ previous_summary }}

### 术语表
{{ glossary | tojson }}
```

## 5. 知识库（Knowledge Store）

统一基于 qmd 构建，**不区分子库**，通过 metadata 字段区分案例/规则。

### namespace

每个项目一个 namespace，物理隔离。一个 db_path 可有多个 namespace。

### 核心接口

```python
class KnowledgeStore:
    def add(self, texts: list[str], metadatas: list[dict]) -> int
    def search(self, query: str, top_k: int, filters: dict | None) -> list[SearchResult]
    def count(self, filters: dict | None) -> int
    def delete(self, filters: dict) -> int
```

### 入库预处理

```python
split_by_heading(text, level=2)   # 按标题切（案例文档）
split_by_clause(text, pattern)    # 按条款切（规章制度）
```

### 检索模式

- 案例检索：纯语义，`store.search(query, top_k=3)`
- 规则检索：过滤+语义，`store.search(query, top_k=5, filters={"type": "rule", "status": "active"})`

### qmd 依赖

| 能力 | 说明 |
|------|------|
| metadata 存储 | documents 表加 `metadata TEXT` 列 |
| 入库传 metadata | `index_document()` 接受 metadata 参数 |
| 过滤检索 | search(filters) 转为 json_extract 条件 |
| 非文件入库 | 直接接收文本+元数据 |

## 6. 生成引擎（Generation Engine）

两层设计：单章生成（原子操作）+ 上下文工具（独立辅助函数）。

### 单章生成

```python
class GenerationEngine:
    def generate_chapter(self, template: str, variables: dict) -> str
```

variables: `user_inputs`, `retrieved_cases`, `previous_summary`, `glossary`

### 上下文工具

```python
class GenerationContext:
    def summarize(self, text: str) -> str                      # 前文摘要
    def extract_terms(self, text: str, existing: dict) -> dict  # 术语表
    def extract_references(self, text: str) -> list[dict]      # 交叉引用
```

### 连贯性保障

长文档（8-10章）生成时 LLM 上下文窗口有限，通过以下机制保证连贯：

1. **术语表**：每章生成后提取术语，合并到全局字典，后续章节注入
2. **前文摘要**：每章生成后压缩上下文为摘要，后续章节携带
3. **交叉引用追踪**：记录跨章节引用，后续章节引用时强制一致

### 典型用法

```python
glossary, summary = {}, ""
for ch in chapters:
    cases = store.search(ch.topic, top_k=3)
    text = gen.generate_chapter(ch.tpl, {"user_inputs": i, "retrieved_cases": cases, "previous_summary": summary, "glossary": glossary})
    summary = ctx.summarize(text)
    glossary = ctx.extract_terms(text, glossary)
```

## 7. 审核引擎（Audit Engine）

原子操作：单要点审核 + 批量便利方法。**四种检查统一走同一个接口**，差异在 checkpoint 配置层面解决。

### 核心接口

```python
class AuditEngine:
    def check_one(self, document: str, checkpoint: dict) -> AuditResult
    def check_many(self, document: str, checkpoints: list[dict]) -> list[AuditResult]
    def load_checkpoints(self, path: str) -> list[dict]
```

### AuditResult

```python
@dataclass
class AuditResult:
    passed: bool
    severity: str              # error / warning / info
    checkpoint_id: str
    chapter_id: str | None
    finding: str
    evidence: str
    suggestion: str
```

### checkpoint 配置

```python
{
    "id": "...",
    "description": "...",
    "severity": "error",
    "scope": "full",                    # "full" | "chapter:ch03"
    "prompt_template": "...",
    "rule_refs": [                       # 支撑条文
        {"source": "GB50150", "clause_id": "3.2.1"},
        {"query": "变压器安装要求"},
    ]
}
```

### 四维检查处理

| 维度 | 处理方式 |
|------|----------|
| 结构合规 | checkpoint prompt 模板写"检查章节完整性" |
| 引用有效性 | checkpoint 配 rule_refs，自动检索验证 |
| 语义合规 | checkpoint prompt + rule_refs |
| 内部一致性 | scope=full，prompt 让 LLM 检查前后矛盾 |

`check_many()` 返回 `list[AuditResult]`，即为审核报告。汇总格式/输出渲染由用户自行处理。

### 引用有效性检查流程

```
文档引用 "GB50150 第3.2.1条"
  → LLM 提取引用列表（source + clause）
  → 查规则库：
    - 找到 + status=active     → ✅ 通过
    - 找到 + status=superseded → ⚠️ 建议更新
    - 找到 + status=revoked    → ❌ 引用已废止
    - 未找到                   → ⚠️ 可能库不全，不直接判错
```

## 8. Doc Pipeline（旁路）

独立的文档预处理工具，将原始文档转换为 Markdown。

```
PDF / Word / 扫描件 → OCR → 清洗 → 结构化解析
```

用途：历史文档入库、待审文档预处理。不在主引擎调用链上。

## 9. Project 入口

极简入口：配置加载 + 组件组装。不做 magic，用户可自由访问底层组件。

```python
class Project:
    def __init__(self, config_path: str):
        self.llm = LLMClient(...)           # LLM 客户端
        self.store = KnowledgeStore(...)    # 知识库（可选）
        self.gen = GenerationEngine(...)    # 生成引擎
        self.ctx = GenerationContext(...)   # 上下文工具（独立组件）
        self.audit = AuditEngine(...)       # 审核引擎
```

**属性说明**：
- `llm`: LLMClient，统一的 LLM 调用层
- `store`: KnowledgeStore | None，知识库实例（配置中未指定则不初始化）
- `gen`: GenerationEngine，章节生成引擎
- `ctx`: GenerationContext，上下文管理工具（摘要、术语、引用提取）
- `audit`: AuditEngine，文档审核引擎

**环境变量**：
- `LLM_API_KEY`：API 密钥（优先）
- `API_KEY`：API 密钥（备选）

## 10. 不包含的内容

- **Orchestrator**：GenerationEngine + AuditEngine 原子接口已够用，用户自己写循环
- **Agent 框架**：流程确定，代码控制即可，不需要 LLM 自主决策
- **CLI**：MVP 阶段不做，SDK 做扎实后 CLI 是 thin wrapper

## 11. 文件结构

```
Scrivai/
├── core/
│   ├── llm.py              # LLMClient
│   ├── knowledge/          # 知识库子包
│   │   ├── __init__.py
│   │   └── store.py        # KnowledgeStore, SearchResult
│   ├── chunkers.py         # split_by_heading, split_by_clause
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── engine.py       # GenerationEngine
│   │   └── context.py      # GenerationContext
│   ├── audit/
│   │   ├── __init__.py
│   │   └── engine.py       # AuditEngine, AuditResult
│   └── project.py          # Project
├── templates/
│   └── prompts/            # Prompt 模板（j2 + md 分离）
│       ├── base.j2         # 基础骨架模板
│       ├── summarize.j2 / summarize.md
│       ├── extract_terms.j2 / extract_terms.md
│       ├── extract_references.j2 / extract_references.md
│       ├── audit.j2 / audit.md
│       └── clean.j2 / clean.md
├── utils/
│   ├── __init__.py
│   └── doc_pipeline.py     # OCRAdapter, MarkdownCleaner, DocPipeline
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── architecture.md
│   ├── sdk_design.md
│   └── ...
├── CLAUDE.md
├── REVIEW_GUIDE.md
└── .gitignore
```

## 12. 与南网项目的关系

南网项目是 Scrivai 的**第一个实例项目**：

| 南网已有 | Scrivai 抽象 |
|----------|-------------|
| MonkeyOCR + 清洗管道 | Doc Pipeline（借鉴） |
| ChromaDB 知识库 | KnowledgeStore（重做，统一用 qmd） |
| 9 Agent 串行生成 | Generation Engine（抽象） |
| 三维度检测 | Audit Engine（抽象） |
| LangChain + LangGraph | 不使用（litellm + 代码编排） |
