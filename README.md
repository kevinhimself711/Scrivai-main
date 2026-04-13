# Scrivai-main

Scrivai-main 是一个面向电网线路工程施工方案生成、审核与后续 Agent 化演进的 Python 项目。

当前 `Start-up` 分支的重点不是部署，而是帮助协作同学快速理解项目架构：尤其是 `docs/agent_architecture` 中已经完成的知识构建层和 Agent 编制审核主链网页，以及配套的带读教程。

## 1. 推荐先读什么

如果你刚接触这个项目，建议按下面顺序阅读。

### 第一步：打开架构入口页

在项目根目录执行：

```powershell
cd "D:\Engineering Projects\Scrivai-main"
Start-Process ".\docs\agent_architecture\agent_architecture_preview.html"
```

入口页会跳转到两张交互式架构图：

- `knowledge_construction_interactive.html`：知识构建层
- `agent_runtime_interactive.html`：Agent 编制与审核主链

### 第二步：跟着带读教程看图

这两份文档是当前最推荐的学习入口：

- `docs/agent_architecture/配套文档/knowledge_layer_guide.md`
  手把手带读知识构建层网页，解释 Raw / Processed / 任务书如何沉淀成 Slot、Passage、Template、Rule、Evidence 五类知识资产。
- `docs/agent_architecture/配套文档/agent_layer_guide.md`
  手把手带读 Agent 主链网页，解释从用户输入、表单规划、章节策略、四类生成策略、组装、审核到修订闭环的完整流转。

阅读方式建议：

1. 打开对应 HTML。
2. 按教程里的节点顺序逐个点击图中节点。
3. 看右侧卡片里的 `节点类型`、`上游`、`下游`、`SDK Tool 依赖`、`输入`、`输出`。
4. 点击右侧卡片中的节点标签，观察左侧图如何同步切换。

### 第三步：再看报告和 Mermaid 源

- `docs/agent_architecture/agent_architecture_report.md`
  当前架构图的整体说明和两张 Mermaid 图的静态版本。
- `docs/agent_architecture/knowledge_construction_layer.mmd`
  知识构建层 Mermaid 源。
- `docs/agent_architecture/agent_runtime_architecture.mmd`
  Agent 主链 Mermaid 源。

这些文件由 `scripts/render_agent_architecture.py` 生成。若要更新交互网页，应优先改脚本，而不是手改派生 HTML。

## 2. 当前架构图覆盖范围

当前架构图分为两层。

### 知识构建层

知识层更接近终态设计。它表达的是如何把南网正式版资料变成运行期 Agent 可查询、可追溯、可治理的知识资产。

核心输入：

- `data/Formal_Version_Data_Processed/`
  已处理的正式版章节树 JSON，是主建库输入。
- `data/Formal_Version_Data_Raw/`
  南网提供的未处理原始施工方案、附件、审批表、图片、表格等，是证据底座和补充抽取源。
- `附录2：南方电网公司基建新技术研究项目计划任务书-v70318.doc`
  项目目标、审核与动态管控要求的重要来源。

正式版线路工程数据包含五类子类型：

- 基础
- 架线
- 跨越
- 立塔
- 消缺

这些子类型建议按多标签理解，而不是一份文档只能属于一个类型。一个真实方案可能同时包含架线、跨越、停电、带电、高塔、深基坑等工况特征。

知识层最终沉淀五类资产：

| 资产 | 作用 |
|------|------|
| `SlotStore` | 参数槽、字段别名、单位、必填和校验规则 |
| `PassageStore` | 可复用施工段落及适用条件 |
| `TemplateStore` | 固定模板骨架、禁改章节、章节结构规则 |
| `RuleStore` | 风险触发条件、审核检查点、必写措施 |
| `EvidenceStore` | 原文路径、章节路径、附件引用和版本证据 |

运行期通过 `KnowledgeStore` 查询这些资产。`KnowledgeStore` 是 SDK 工具入口，不是 Agent。

### Agent 编制与审核主链

Agent 主图当前只覆盖“编制 + 审核”主链，不把发布后的现场协同、动态管控、检查表回填和异常闭环画进主图。

主链分为三段：

1. `需求理解与表单规划`
   `Start -> Intake -> Subtype + Scene Classifier -> Form Planner -> Completeness -> Clarification`
2. `章节生成策略层`
   `Generation Planner -> Chapter Router -> fill_only / select_and_fill / controlled_compose / derive_by_rules -> Assembler`
3. `审核与修订闭环`
   `Context -> Consistency -> Compliance -> Pass -> Revision Planner -> Revision -> Output`

图中的虚线表示 SDK 工具依赖：

- `KnowledgeStore`
- `GenerationEngine`
- `LLMClient`
- `GenerationContext`
- `AuditEngine`

这些是母项目 SDK 工具，不是 Agent 节点。

## 3. 当前 Demo 能力

项目中仍保留一个可运行的本地 Streamlit Demo，用于演示线路工程施工方案生成。

Demo 流程：

1. 选择工程类型：当前只有 `线路工程`
2. 选择模板：`模板A / 模板B / 模板C`
3. 填写线路工程关键字段和可编辑表格
4. 可选填写客制化要求
5. 生成施工方案 Markdown

模板定位：

| 模板 | 风格 | 适用场景 |
|------|------|----------|
| 模板A | 规范严谨 | 正式报审、对外提交 |
| 模板B | 均衡通用 | 常规内部流转、一般评审 |
| 模板C | 执行展开 | 施工交底、现场执行说明 |

当前 Demo 已接入：

- 封面
- 审批页
- 目录
- 第 1 章 编制说明
- 第 2 章 工程概况
- 第 3 章 施工技术措施
- 第 4 章 施工组织措施
- 第 5 章 安全管理措施
- 第 6 章 质量控制措施
- 第 7 章 应急处置方案
- 第 8 章 环保水保措施

第 3 章在三套模板中都保持纯模板填空，不参与 LLM 客制化改写。

## 4. 快速运行 Demo

### 安装依赖

```powershell
pip install -e .
pip install -e .[demo]
```

如需运行测试：

```powershell
pip install -e .[dev]
```

### 配置环境变量

不要提交真实 `.env`。复制模板后在本地填写：

```powershell
Copy-Item .env.example .env
```

`.env.example` 中的默认配置使用阿里云百炼 OpenAI 兼容接口：

```env
MODEL_NAME=qwen3-max
REWRITE_MODEL=qwen3-max
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_api_key_here
LLM_API_KEY=your_api_key_here
```

如果本机启用了 Clash 且开启了 TUN，建议将 `dashscope.aliyuncs.com` 或 `aliyuncs.com` 配为 `DIRECT`。如只测试模板填充，不填写客制化要求即可避免调用 LLM。

### 启动

```powershell
streamlit run streamlit_app.py
```

## 5. 关键目录

```text
Scrivai-main/
├─ core/                         # SDK 基础能力：LLM、知识库、生成、上下文、审核
├─ demo/                         # 线路工程施工方案 Demo
│  ├─ app.py                     # Streamlit 页面
│  ├─ generator.py               # Markdown 生成服务
│  ├─ source_data.py             # data JSON 解析
│  ├─ config/
│  │  ├─ template_variants.yaml  # A/B/C 模板元数据
│  │  ├─ chapters.yaml           # 章节清单、source mapping、rewrite topics
│  │  └─ fields.yaml             # 表单 schema
│  ├─ templates/                 # 章节模板 fragments
│  └─ tools/
│     └─ inspect_source.py       # 新章节接入辅助工具
├─ data/
│  ├─ Formal_Version_Data_Processed/ # 正式版处理后章节树数据
│  ├─ Formal_Version_Data_Raw/       # 正式版原始资料
│  ├─ 2.json ... 8.json              # Demo 阶段章节数据
│  └─ 1/                             # Demo 图片资源
├─ docs/
│  ├─ architecture.md
│  ├─ sdk_design.md
│  └─ agent_architecture/        # 当前 Start-up 分支重点学习资料
│     └─ 配套文档/                # 两份带读教程
├─ scripts/
│  └─ render_agent_architecture.py # 架构图 HTML / SVG / MMD 生成脚本
├─ tests/
├─ streamlit_app.py
└─ pyproject.toml
```

## 6. 架构图如何重新生成

如果修改了 `scripts/render_agent_architecture.py`，运行：

```powershell
python scripts/render_agent_architecture.py
```

脚本会更新：

- `docs/agent_architecture/knowledge_construction_layer.mmd`
- `docs/agent_architecture/agent_runtime_architecture.mmd`
- `docs/agent_architecture/knowledge_construction_interactive.html`
- `docs/agent_architecture/agent_runtime_interactive.html`
- `docs/agent_architecture/agent_architecture_preview.html`
- `docs/agent_architecture/agent_architecture_report.md`
- 对应 SVG 文件

如果 Mermaid CLI 可用，脚本会预渲染 SVG；不可用时仍会保留可读的 HTML fallback。

## 7. 后续实现建议

当前 Demo 是终态 Agent 系统的简化版本：

| 当前 Demo | 终态 Agent 系统 |
|-----------|-----------------|
| 固定表单 schema | `Form Planner Agent` + `SlotStore` 动态规划 |
| A/B/C 模板 | `TemplateStore` 管理模板资产 |
| 第三章只填空 | `fill_only` 策略 |
| 客制化要求改写 | `controlled_compose` 受控开放写作 |
| Markdown 生成 | `Assembler` + `Output` |
| 手工模板配置 | 知识层自动/半自动沉淀模板、段落、规则和证据 |

建议分期：

1. 先把正式版 Processed 数据沉淀为 `slot / passage / template` 三类资产。
2. 再接入 `RuleStore / EvidenceStore`，支撑结构化审核。
3. 用 LangGraph 实现 `Intake -> FormPlanner -> Generation Planner -> Router -> Assembler` 最小生成链。
4. 再加入 `Consistency -> Compliance -> Revision` 审核修订闭环。
5. 最后扩展到现场协同和动态管控。

## 8. 安全说明

真实 API Key 只应保存在本地 `.env`，不要提交到 Git。

本分支提供 `.env.example` 作为配置模板。若历史提交中曾出现真实密钥，应在对应平台轮换密钥后继续开发。
