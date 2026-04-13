# 知识构建层带读教程

本文不是抽象架构说明，而是配合 `knowledge_construction_interactive.html` 使用的带读教程。目标读者是有 LangGraph / Agent 开发经验、但不熟悉电网施工方案业务的开发者。

读完本文后，你应该能回答三个问题：正式版数据为什么不能直接塞进一个向量库；知识层为什么要拆成 `Slot / Passage / Template / Rule / Evidence` 五类资产；运行期 Agent 为什么通过 `KnowledgeStore` 调用这些资产，而不是自己解析原始文件。

## 1. 先打开知识构建层网页

在项目根目录执行：

```powershell
cd "D:\Engineering Projects\Scrivai-main"
Start-Process ".\docs\agent_architecture\knowledge_construction_interactive.html"
```

如果你只是想先看入口页，也可以打开：

```powershell
Start-Process ".\docs\agent_architecture\agent_architecture_preview.html"
```

网页打开后先做三件事：

1. 点击页面左上角的 `重置`，让图回到默认视角。
2. 用鼠标滚轮缩放，按住图区域拖拽平移，确认你能移动画布。
3. 点击任意节点，例如 `Processed 章节树`，观察右侧卡片是否切换。

右侧卡片是读图入口。每张卡片重点看这些区块：`节点类型`、`所属阶段`、`在整体流程中的作用`、`上游`、`下游`、`输入`、`输出`、`技术边界`。卡片里的节点标签可以点击，点击后左侧图也会同步切到对应节点。

## 2. 先从三类输入资产开始

请在网页上依次点击 `Raw 原始工程包`、`Processed 章节树`、`任务书 / 标准规范`。

### 第一步：点击 `Processed 章节树`

这个节点对应项目里的：

```text
data/Formal_Version_Data_Processed/
```

你要把它理解成主建库输入，而不是“已经可以直接生成最终方案的模板”。它的价值在于已经处理成章节树 JSON，并且能区分 `text / table / image` 内容块。

在正式版数据里，线路工程有五类子类型：

```text
基础 / 架线 / 跨越 / 立塔 / 消缺
```

读图时要特别注意：这些子类型后续更适合做多标签，而不是单选分类。比如一个施工方案可能以架线为主，但也包含跨越场景；一个消缺方案可能同时涉及停电、带电、现场勘察、风险评估表等材料。

### 第二步：点击 `Raw 原始工程包`

这个节点对应项目里的：

```text
data/Formal_Version_Data_Raw/
```

Raw 的角色不是直接给模型生成正文，而是提供原始证据。Raw 里可能包含 Word、PDF、Excel、审批表、现场勘察表、照片、压缩包等。它更适合承担三件事：

| 用途 | 说明 |
|------|------|
| 证据底座 | 生成或审核结果需要能追溯到原文件 |
| 补充抽取 | Processed 缺字段或缺附件时可以回 Raw 再抽取 |
| 外部审核输入 | 审核时可以比对原文、附件和表格证据 |

这也是为什么图里 Raw 先进入 `Document Parse Agent`，而不是直接进入 `KnowledgeStore`。

### 第三步：点击 `任务书 / 标准规范`

这个节点告诉你系统目标不是“帮用户写一篇像样的文档”这么简单。任务书提出的是智能编制、精准审核、动态管控等终态能力。当前 Agent 主图只展开“编制 + 审核”，但知识层要提前把规则、证据和治理能力设计进去。

读到这里，你应该形成第一个判断：`Processed` 是主建库输入，`Raw` 是证据与补充来源，`TaskBook` 是规则和系统目标来源。三者不能混成一个文本池。

## 3. 跟着箭头走结构归一化层

请按下面顺序点击节点：

```text
Raw 原始工程包
-> Document Parse Agent
-> Structure Normalizer
-> Chunk & Dedup Agent
-> Subtype + Scene Tagger
```

然后再点击：

```text
Processed 章节树
-> Structure Normalizer
```

### `Document Parse Agent`

这个节点处理 Raw 资料。它要把 Word、PDF、Excel、附件等解析成可进入统一链路的片段。对开发者来说，它类似一个预处理 Agent 或文档 pipeline 节点。

它不负责判断哪些内容能复用，也不负责生成模板。它只把非结构化资料变成可被下一步归一化的材料，并保留来源。

### `Structure Normalizer`

这个节点是 Raw 和 Processed 的汇合点。它把 Raw 解析结果和 Processed JSON 统一成同一种内部结构，例如章节路径、内容块类型、表格结构、图片引用、来源路径。

你可以把它想成知识层的 adapter。没有它，后面的节点就必须分别适配 Word、PDF、JSON 和 Excel，维护成本会很高。

### `Chunk & Dedup Agent`

这个节点负责切片和去重。这里的关键不是简单把文本切短，而是切片时保留章节路径、子类型、工况、来源路径和证据信息。

一个合理的中间 chunk 应该接近这样：

```python
{
    "chunk_id": "...",
    "source": "processed|raw|taskbook",
    "chapter_path": "3.2.1",
    "content_type": "text|table|image_ref",
    "subtypes": ["基础", "跨越"],
    "scenes": ["深基坑", "跨越带电线路"],
    "source_path": "..."
}
```

注意“去重不等于删掉归属”。同一段内容可能在多个子类型目录中出现，去重后仍然要保留它适用于哪些子类型和工况。

### `Subtype + Scene Tagger`

这个节点把切片标注为 `基础 / 架线 / 跨越 / 立塔 / 消缺` 等子类型，同时识别深基坑、高塔、跨越带电线路、停电作业、带电作业等工况。

从 LangGraph 视角看，它更像知识构建期的标注节点，不是运行期主链里的分类器。运行期也有 `Subtype + Scene Classifier`，但那个节点面对的是用户任务；这里面对的是历史资料和知识 chunk。

读到这里，你应该形成第二个判断：知识层不是直接从文件到向量库，而是先把资料变成带标签、带来源、带章节结构的标准 chunk。

## 4. 再走知识识别层

现在从 `Subtype + Scene Tagger` 出发，依次点击五个分支：

```text
Slot Miner
Passage Curator
Template Curator
Rule & Risk Extractor
Evidence Linker
```

这五个节点对应五种不同知识资产，不要把它们都理解成“文本切片”。

### `Slot Miner`

这个节点识别挖空项、表格字段和字段别名。它要把原文里的 `XXXX`、空表格、待补字段转换成语义字段。

比如不是保留“第 3 个 XXXX”，而是识别成：

```python
{
    "field_id": "project_name",
    "label": "工程名称",
    "aliases": ["项目名称", "线路工程名称"],
    "required": True,
    "source_chapters": ["封面", "1.1", "2.1"]
}
```

这个节点直接服务后续 `Form Planner Agent` 和 `fill_only`。如果字段没有统一，后续就会出现同一个工程名称在不同章节重复填写或不一致的问题。

### `Passage Curator`

这个节点提取可复用施工段落。它处理的是“有真实写法可以复用，但需要根据工况选择”的内容。

例如架线、跨越、立塔、消缺里可能存在大量通用安全措施、组织措施、施工流程说明。它们不一定适合固定成模板，但可以作为候选段落被 `select_and_fill` 或 `controlled_compose` 使用。

这个节点应该给段落打上适用条件：

```python
{
    "asset_type": "passage",
    "subtypes": ["架线"],
    "scenes": ["跨越高速", "导引绳展放"],
    "rewrite_policy": "select_and_fill",
    "evidence_id": "..."
}
```

### `Template Curator`

请重点点击这个节点。它是当前完整规划里非常关键的补充。

它负责把固定模板骨架、禁改章节、章节结构规则从普通段落里分离出来。比如 demo 中已经明确“施工技术措施”更接近纯模板填参，不应该进入 LLM 客制化改写。这类规则就应该沉淀到 `TemplateStore`，而不是只写在 prompt 里。

它的输出不是一段普通文本，而是带约束的模板资产：

```python
{
    "asset_type": "template",
    "chapter_id": "ch03",
    "rewrite_policy": "fill_only",
    "fixed_structure": True,
    "editable_slots": ["tower_no", "foundation_type"],
    "locked_sections": ["施工技术措施"]
}
```

如果没有 `Template Curator`，后续 Agent 很容易把“模板固定内容”和“可复用段落”混在一起，导致禁改章节被模型改写。

### `Rule & Risk Extractor`

这个节点从任务书、规范和真实方案中抽取风险触发规则和审核检查点。

典型规则不是一个分数，而是结构化条件：

```python
{
    "asset_type": "rule",
    "trigger": {
        "scene": "跨越带电线路",
        "voltage_level": ">=220kV"
    },
    "required_measures": ["跨越架验收", "带电安全距离校核"],
    "checkpoints": ["方案是否说明跨越对象", "是否列出安全距离控制措施"]
}
```

它同时服务 `derive_by_rules` 和 `Compliance Agent`。前者在生成阶段补出必写措施，后者在审核阶段检查是否缺漏。

### `Evidence Linker`

这个节点把字段、段落、模板和规则回链到原始文件、章节路径、表格编号或附件。

它解决的是工程场景里的“可解释性”问题：当审核报告指出缺少某个措施，系统应该能说明这个检查点来自哪里；当某个段落被复用，系统应该能说明它参考了哪份历史方案。

读到这里，你应该形成第三个判断：知识识别层的关键不是“把文本喂给模型”，而是把资料拆成不同类型、不同约束、可追溯的知识资产。

## 5. 最后看五个 Store 和 KnowledgeStore

请点击以下节点：

```text
Slot Store
Passage Store
Template Store
Rule Store
Evidence Store
KnowledgeStore
Governance
```

### 五个 Store 的读法

你可以把五个 Store 理解成同一个知识库里的五类资产，也可以在实现上拆成不同 collection。关键不是物理存储方式，而是 metadata 必须能区分它们。

推荐最小 metadata：

```python
{
    "asset_type": "slot|passage|template|rule|evidence",
    "subtypes": ["基础"],
    "scenes": ["人工挖孔桩"],
    "chapter_path": "3",
    "rewrite_policy": "fill_only|select_and_fill|controlled_compose|derive_by_rules",
    "source_path": "...",
    "evidence_id": "..."
}
```

### `KnowledgeStore`

点击 `KnowledgeStore` 时要注意：它是 SDK 工具入口，不是 Agent。运行期 Agent 通过它查询模板、段落、字段、规则和证据。

一个典型调用不是“给我搜相似文本”，而应该更具体：

```python
store.search(
    query="跨越带电线路安全措施",
    top_k=5,
    filters={
        "asset_type": "passage",
        "subtypes": ["跨越"],
        "rewrite_policy": "select_and_fill"
    },
)
```

### `Governance`

`Governance` 管理版本、人工确认、证据链和变更记录。demo 阶段可能看不出它的价值，但正式系统会需要它来回答：

| 问题 | 依赖 |
|------|------|
| 这条模板规则什么时候更新的？ | 版本记录 |
| 这段内容来自哪份原始方案？ | 证据链 |
| 哪些字段经过人工确认？ | 审批状态 |
| 新数据入库后是否影响旧模板？ | 变更记录 |

## 6. 一遍完整读图路线

如果你要给新同事讲这张图，可以按下面顺序带他点击：

```text
Processed 章节树
Raw 原始工程包
任务书 / 标准规范
Document Parse Agent
Structure Normalizer
Chunk & Dedup Agent
Subtype + Scene Tagger
Slot Miner
Passage Curator
Template Curator
Rule & Risk Extractor
Evidence Linker
Slot Store
Passage Store
Template Store
Rule Store
Evidence Store
KnowledgeStore
Governance
```

讲解时只抓一条主线：资料先变成标准 chunk，再变成五类知识资产，最后通过 `KnowledgeStore` 被运行期 Agent 调用。

## 7. 读完后的检查问题

你可以用这几个问题检查自己是否真正看懂：

| 问题 | 期望答案 |
|------|----------|
| 为什么 `Processed` 是主建库输入？ | 因为它已经是章节树 JSON，适合切片、字段识别和模板化 |
| 为什么 `Raw` 不直接生成正文？ | 因为 Raw 噪声多，更适合作为证据、补充抽取和审核来源 |
| 为什么要有 `TemplateStore`？ | 因为要表达固定模板、禁改章节和章节结构规则 |
| 为什么子类型是多标签？ | 因为真实方案可能同时涉及多个施工子类型和工况 |
| `KnowledgeStore` 是不是 Agent？ | 不是，它是 SDK 检索工具入口 |

