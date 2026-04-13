# Agent 编制与审核主链带读教程

本文配合 `agent_runtime_interactive.html` 使用，用来手把手带读者走完当前 Agent 主链。目标读者是有 LangGraph / Agent 开发经验、但不熟悉线路工程施工方案业务的开发者。

读完本文后，你应该能看懂三件事：主链为什么只覆盖“编制 + 审核”；哪些节点是 Agent，哪些只是策略执行器或 SDK 工具；当前 demo 如何逐步演进成 LangGraph 多节点系统。

## 1. 先打开 Agent 主链网页

在项目根目录执行：

```powershell
cd "D:\Engineering Projects\Scrivai-main"
Start-Process ".\docs\agent_architecture\agent_runtime_interactive.html"
```

如果你想从总入口进入，也可以打开：

```powershell
Start-Process ".\docs\agent_architecture\agent_architecture_preview.html"
```

网页打开后先做四件事：

1. 点击左上角 `重置`，恢复默认视角。
2. 用鼠标滚轮缩放图，按住图区域拖拽平移。
3. 点击 `Generation Planner`，确认右侧卡片切换。
4. 在右侧卡片里点击 `上游`、`下游` 或 `SDK Tool 依赖` 中的节点标签，确认左侧图会同步跳转选中节点。

这张图要这样读：实线表示工作流状态的主流转，虚线表示 SDK 工具依赖。右侧卡片是解释每个节点边界的主入口。

## 2. 先看颜色，不要先看业务细节

图里颜色表示节点类型，不表示业务重要性。

| 图中类型 | 读法 |
|----------|------|
| `Agent node` | 需要语义判断、规划或结构化推理的节点 |
| `Strategy executor` | 具体生成策略执行器，职责收敛，通常不自由发挥 |
| `Conditional gate` | 条件判断节点，优先规则判断 |
| `SDK tool` | 母项目 SDK 工具，供节点调用，不是 Agent |
| `Output` | 最终交付包 |

请特别注意两个容易误读的点：

| 节点 | 正确理解 |
|------|----------|
| `Assembler` | 它是独立汇合节点，但仍是 `Strategy executor`，不是一个新类型 Agent |
| `Revision Planner` / `Revision Agent` | 它们属于审核修订阶段的 Agent node，不需要单独一种颜色 |

## 3. 用一条状态对象理解整张图

如果你熟悉 LangGraph，可以先把图理解为围绕一个 `PlanState` 逐步更新。

```python
class PlanState(TypedDict):
    request: dict
    normalized_request: dict
    subtypes: list[str]
    scenes: list[str]
    form_schema: dict
    form_data: dict
    missing_fields: list[dict]
    chapter_plan: list[dict]
    chapter_outputs: dict[str, str]
    assembled_document: str
    context_summary: dict
    consistency_findings: list[dict]
    compliance_findings: list[dict]
    revision_tasks: list[dict]
    publish_pack: dict
```

实线节点更新这个状态。SDK 工具只在节点内部被调用，不应该自己改主状态。

## 4. 第一段：需求理解与表单规划

请按顺序点击：

```text
Start Request
-> Intake Agent
-> Subtype + Scene Classifier
-> Form Planner Agent
-> 关键信息完整?
-> Clarification Agent
```

### `Start Request`

它只是入口。你可以把它理解成用户提交了一个任务：要生成某个线路工程施工方案，并可能附带项目资料、客制化要求或已有表格。

它不做推理，不调用模型，也不生成正文。

### `Intake Agent`

这个节点把用户输入归一成标准任务对象。例如用户说“我要做架线方案，涉及跨越某线路，工期 20 天”，它要整理成后续节点能读的结构。

它的输出应该接近：

```python
state["normalized_request"] = {
    "project_type": "线路工程",
    "user_goal": "生成施工方案",
    "raw_requirements": "...",
    "attachments": [...]
}
```

不要让 `Classifier` 和 `FormPlanner` 直接处理杂乱自然语言和附件说明，这会让后续每个节点都变复杂。

### `Subtype + Scene Classifier`

这个节点识别施工子类型和工况。正式版数据包含：

```text
基础 / 架线 / 跨越 / 立塔 / 消缺
```

这里必须按多标签设计。例如一个用户任务可能是“架线”，但涉及“跨越高速”或“跨越带电线路”；也可能是“消缺”，但同时包含“停电更换”和“现场勘察”材料。

它的输出应该接近：

```python
state["subtypes"] = ["架线", "跨越"]
state["scenes"] = ["跨越带电线路", "导引绳展放"]
```

这个结果会影响三件事：表单字段、知识检索过滤条件、审核规则加载范围。

### `Form Planner Agent`

这个节点基于 `SlotStore` 生成表单 schema。它的目标不是复刻某一份原始方案里的占位符，而是生成语义化字段。

它的输出应该接近：

```python
state["form_schema"] = {
    "fields": [
        {"id": "project_name", "label": "工程名称", "required": True},
        {"id": "voltage_level", "label": "电压等级", "required": True},
        {"id": "tower_range", "label": "施工杆塔范围", "required": True}
    ],
    "editable_tables": [...]
}
```

这就是当前 demo 中“既定 schema 表单”的终态升级方向：表单仍然结构化，但字段来自 `SlotStore`，而不是写死在 Streamlit 页面里。

### `关键信息完整?`

这是条件门，不是普通 Agent。它判断当前字段是否足够进入生成链路。

判断依据应优先来自规则：

| 判断项 | 例子 |
|--------|------|
| 必填字段 | 工程名称、电压等级、施工范围 |
| 策略必需字段 | `fill_only` 模板要求的参数 |
| 审核触发字段 | 是否涉及跨越、停电、带电作业 |
| 表格完整性 | 基础参数表、施工机具表是否缺关键列 |

如果不完整，走 `Clarification Agent`；如果完整，进入 `Generation Planner`。

### `Clarification Agent`

这个节点只负责最小补问。它不是 chatbox，也不是让用户随便聊。

一个合理补问应该是：

```text
当前缺少“施工杆塔范围”和“是否涉及带电跨越”。请补充这两项后继续生成。
```

补问完成后回到 `Form Planner Agent`，重新更新 schema 或字段值。

## 5. 第二段：章节生成策略层

请按顺序点击：

```text
Generation Planner
-> Chapter Router
-> fill_only
-> select_and_fill
-> controlled_compose
-> derive_by_rules
-> Assembler
```

### `Generation Planner`

这是章节策略规划节点。它不直接写正文，而是为每个章节决定使用哪条生成策略。

它会综合使用：

| 资产 | 来源 |
|------|------|
| 模板骨架 | `TemplateStore` |
| 可复用段落 | `PassageStore` |
| 参数字段 | `SlotStore` |
| 规则检查点 | `RuleStore` |
| 证据链 | `EvidenceStore` |

它的输出应该接近：

```python
state["chapter_plan"] = [
    {"chapter_id": "ch01", "strategy": "select_and_fill"},
    {"chapter_id": "ch03", "strategy": "fill_only", "rewrite_enabled": False},
    {"chapter_id": "safety", "strategy": "derive_by_rules"},
    {"chapter_id": "custom_notes", "strategy": "controlled_compose"}
]
```

请在右侧卡片里看它的 `SDK Tool 依赖`。它依赖 `KnowledgeStore`，因为策略规划要知道哪些章节有模板、哪些章节有候选段落、哪些内容受规则约束。

### `Chapter Router`

这个节点只做分发。它读 `chapter_plan`，然后把每个章节送到对应策略执行器。

从 LangGraph 实现角度，这里可能是一个路由函数或一个轻量节点，不一定需要强模型能力。

不要让它重新判断章节策略，也不要让它写正文。策略判断已经在 `Generation Planner` 完成。

### `fill_only`

这是最稳定的策略。它用于固定模板、禁改章节和强结构表格。

当前规划里“施工技术措施”这类章节如果被标记为纯模板填参，就应该走这里。它使用 `GenerationEngine` 做模板渲染，不进入 LLM 改写。

典型输入：

```python
{
    "template_id": "line/ch03",
    "form_data": state["form_data"],
    "editable_tables": {...}
}
```

典型输出：

```python
state["chapter_outputs"]["ch03"] = "第三章 施工技术措施..."
```

这条链路解决的是“关键章节不漂移”。只靠 prompt 写“第三章不要改”不够可靠，策略层必须把它排除出改写路径。

### `select_and_fill`

这是半确定性策略。它用于有多个真实可复用段落可选的章节。

它会从 `KnowledgeStore` 检索候选段落，再根据当前子类型和工况选择合适段落，并注入参数。

典型调用：

```python
passages = store.search(
    query="跨越带电线路安全措施",
    top_k=5,
    filters={
        "asset_type": "passage",
        "subtypes": ["跨越"],
        "rewrite_policy": "select_and_fill"
    },
)
```

它不是自由写作。它的价值是让系统复用真实施工方案中的成熟表达。

### `controlled_compose`

这是受控开放写作策略。它可以调用 `LLMClient`，但不能无边界生成。

它适合处理用户客制化要求，例如：

```text
请强化跨越带电线路施工期间的监护安排，并补充夜间施工照明和应急联络要求。
```

但它必须同时带上模板风格、候选段落、禁改范围、项目参数和证据边界。它的 prompt 不能只写“根据用户要求生成一段内容”。

一个合理的输入结构应该接近：

```python
{
    "chapter_template": "...",
    "retrieved_passages": [...],
    "custom_requirements": "...",
    "locked_sections": ["ch03"],
    "style_policy": "规范严谨",
    "evidence_refs": [...]
}
```

### `derive_by_rules`

这是规则派生策略。它处理“由参数触发的必写内容”。

例如当 `scenes` 包含“跨越带电线路”时，规则库可能要求生成安全距离控制、跨越架验收、专人监护等措施。这个内容不是从某段相似文本随便改写，也不是由模型主观发挥，而是由 `RuleStore` 的触发条件推导。

它输出的内容应该能追溯到规则：

```python
{
    "chapter_id": "safety",
    "content": "...",
    "triggered_rules": ["rule_crossing_live_line_001"]
}
```

### `Assembler`

`Assembler` 是四条生成支路的汇合点。

它负责合并目录、章节顺序、表格位置、引用和版本信息。它不应重写正文，也不应调用模型“润色全文”。如果让它重新创作，就会破坏前面四条策略的边界。

读图时可以点击它的上游节点，观察它同时接收 `fill_only`、`select_and_fill`、`controlled_compose`、`derive_by_rules`。

## 6. 第三段：审核与修订闭环

请按顺序点击：

```text
Context Agent
-> Consistency Agent
-> Compliance Agent
-> 通过审核?
-> Revision Planner
-> Revision Agent
-> Output / Publish Pack
```

### `Context Agent`

它接收 `Assembler` 输出的整篇草稿，并把术语、摘要、引用关系和关键事实写入 `GenerationContext`。

它解决的是长文档一致性问题。例如工程名称、线路名称、杆塔范围、工期、数量、风险场景不能在不同章节出现不同说法。

### `Consistency Agent`

它检查跨章节事实是否一致。

典型输出：

```python
state["consistency_findings"] = [
    {
        "chapter_id": "ch02",
        "field": "tower_range",
        "finding": "第二章杆塔范围与封面不一致",
        "suggestion": "统一为 #12-#18"
    }
]
```

它和 `Compliance Agent` 的区别是：它主要查“文档内部有没有自相矛盾”，而不是查“是否符合规范或风险要求”。

### `Compliance Agent`

它调用 `KnowledgeStore` 和 `AuditEngine` 做结构化审核。它不是只给一个总分，而是输出可定位、可修订的问题清单。

典型输出：

```python
state["compliance_findings"] = [
    {
        "checkpoint_id": "crossing_live_line_guardian",
        "chapter_id": "safety",
        "severity": "high",
        "finding": "未说明跨越带电线路期间的专人监护安排",
        "evidence": ["rule_crossing_live_line_001"],
        "suggestion": "补充监护人员、监护位置和通信方式"
    }
]
```

如果你点击右侧卡片里的 `AuditEngine`，要注意它是 SDK 工具，不决定是否通过，也不负责修订。它只是执行检查点。

### `通过审核?`

这是条件门。它读取一致性问题和合规问题，决定进入 `Output` 还是进入修订链路。

它不应该让模型主观判断“看起来是否可以”。更合理的是基于结构化问题清单做规则判断，例如存在 high severity 问题就不通过。

### `Revision Planner`

这个节点把审核问题拆成修订任务。它的价值是控制修订范围。

典型输出：

```python
state["revision_tasks"] = [
    {
        "target_chapter": "safety",
        "finding_id": "crossing_live_line_guardian",
        "allowed_action": "append_paragraph",
        "locked_chapters": ["ch03"]
    }
]
```

它要明确哪些章节不能改，哪些章节只能局部追加。比如 `fill_only` 锁定章节不应被 Revision Agent 重写。

### `Revision Agent`

它只执行定向修订，不重写整篇。

修订完成后回到 `Consistency Agent`，重新检查一致性，再进入 `Compliance Agent`。这就是审核修订闭环。

### `Output / Publish Pack`

这是当前主图终点。它输出施工方案正文、审核报告、版本记录和证据链。

终态系统里的现场协同、动态管控、检查表回填和异常闭环，可以从这个节点继续扩展，但本轮主图没有展开。

## 7. 专门看 SDK 工具依赖

现在请依次点击图中的 SDK 工具：

```text
KnowledgeStore
GenerationEngine
LLMClient
GenerationContext
AuditEngine
```

### `KnowledgeStore`

它给 `Generation Planner`、`select_and_fill`、`derive_by_rules`、`Compliance Agent` 提供知识检索。它不是 Agent，不做业务决策。

### `GenerationEngine`

它服务 `fill_only` 和部分 `select_and_fill`。它的职责是模板渲染和确定性填充，不做开放式创作。

### `LLMClient`

它主要服务 `controlled_compose`，未来也可以服务补问或定向修订。它统一 provider、超时、错误处理和模型调用接口。

### `GenerationContext`

它服务 `Context Agent`，承载摘要、术语、引用和跨章状态。它不是判断节点。

### `AuditEngine`

它服务 `Compliance Agent`，执行检查点并返回结构化结果。它不是评分器，也不负责最终通过与否。

## 8. 按这一遍路线带新同事读图

如果你要向团队讲这张图，建议按下面顺序点击：

```text
Start Request
Intake Agent
Subtype + Scene Classifier
Form Planner Agent
关键信息完整?
Clarification Agent
Generation Planner
Chapter Router
fill_only
select_and_fill
controlled_compose
derive_by_rules
Assembler
Context Agent
Consistency Agent
Compliance Agent
通过审核?
Revision Planner
Revision Agent
Output / Publish Pack
KnowledgeStore
GenerationEngine
LLMClient
GenerationContext
AuditEngine
```

讲解时抓住一条主线：用户任务先变成结构化状态，再被规划成章节策略，四条策略生成章节后汇合成全文，最后进入一致性审核、合规审核和定向修订闭环。

## 9. 和当前 demo 的对应关系

当前 Streamlit demo 可以理解为终态 Agent 系统的简化版。

| 当前 demo | Agent 主链里的对应能力 |
|-----------|------------------------|
| 选择线路工程 | `Start Request` + `Subtype Classifier` 的极简版本 |
| 固定表单 schema | `Form Planner Agent` + `SlotStore` 的静态版本 |
| A/B/C 模板 | `TemplateStore` + `Generation Planner` 的静态版本 |
| 第三章只填空 | `fill_only` 策略 |
| 客制化要求改写 | `controlled_compose` 策略 |
| Markdown 生成 | `Assembler` + `Output` 的简化版本 |

所以后续不是推翻 demo，而是逐步把 demo 里的硬编码配置替换成知识资产和 LangGraph 编排。

## 10. 读完后的检查问题

| 问题 | 期望答案 |
|------|----------|
| `Assembler` 是 Agent 吗？ | 不是，它是策略层的确定性组装节点 |
| `Revision Agent` 为什么不是单独颜色？ | 因为修订是业务阶段，它本质仍是 Agent node |
| `fill_only` 和 `controlled_compose` 最大区别是什么？ | 前者只模板填空，后者允许受控 LLM 写作 |
| SDK 虚线边代表什么？ | 工具依赖，不是状态流转顺序 |
| `Compliance Agent` 是评分器吗？ | 不是，它输出结构化问题、证据和整改建议 |

