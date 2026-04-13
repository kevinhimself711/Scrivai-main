"""Generate split interactive architecture pages for the line-project agent design.

The generated pages use local SVG output from Mermaid CLI when available. Each
page keeps the graph on the left and a fixed explanation card on the right.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


KNOWLEDGE_MERMAID = """flowchart LR
    subgraph Input["输入资产"]
        direction TB
        Raw["Raw 原始工程包"]
        Processed["Processed 章节树"]
        TaskBook["任务书 / 标准规范"]
    end
    subgraph Normalize["结构归一化"]
        direction TB
        RawParser["Document Parse Agent"]
        Normalizer["Structure Normalizer"]
        Chunker["Chunk & Dedup Agent"]
        Taxonomy["Subtype + Scene Tagger"]
    end
    subgraph Extract["知识识别"]
        direction TB
        SlotMiner["Slot Miner"]
        PassageCurator["Passage Curator"]
        TemplateCurator["Template Curator"]
        RuleExtractor["Rule & Risk Extractor"]
        EvidenceLinker["Evidence Linker"]
    end
    subgraph Stores["专题知识资产"]
        direction TB
        SlotStore["Slot Store"]
        PassageStore["Passage Store"]
        TemplateStore["Template Store"]
        RuleStore["Rule Store"]
        EvidenceStore["Evidence Store"]
    end
    subgraph Runtime["运行期入口与治理"]
        direction TB
        KnowledgeStore["KnowledgeStore"]
        Governance["Governance"]
    end
    Raw --> RawParser --> Normalizer
    Processed --> Normalizer
    Normalizer --> Chunker --> Taxonomy
    TaskBook --> RuleExtractor
    Taxonomy --> SlotMiner --> SlotStore
    Taxonomy --> PassageCurator --> PassageStore
    Taxonomy --> TemplateCurator --> TemplateStore
    Taxonomy --> RuleExtractor --> RuleStore
    Taxonomy --> EvidenceLinker --> EvidenceStore
    SlotStore --> KnowledgeStore
    PassageStore --> KnowledgeStore
    TemplateStore --> KnowledgeStore
    RuleStore --> KnowledgeStore
    EvidenceStore --> KnowledgeStore
    KnowledgeStore --> Governance
    classDef input fill:#FCE4D6,stroke:#B76E4C,color:#1f2d2a
    classDef normalize fill:#D9EAD3,stroke:#6A8F63,color:#1f2d2a
    classDef extract fill:#E2F0D9,stroke:#6A8F63,color:#1f2d2a
    classDef store fill:#DDEBF7,stroke:#5B8DB0,color:#1f2d2a
    classDef sdk fill:#EFE6D2,stroke:#9A825A,color:#1f2d2a
    class Raw,Processed,TaskBook input
    class RawParser,Normalizer,Chunker,Taxonomy normalize
    class SlotMiner,PassageCurator,TemplateCurator,RuleExtractor,EvidenceLinker extract
    class SlotStore,PassageStore,TemplateStore,RuleStore,EvidenceStore store
    class KnowledgeStore,Governance sdk
"""


AGENT_MERMAID = """flowchart TD
    Start(["Start Request"]) --> Intake
    subgraph IntakeLayer["需求理解与表单规划"]
        direction TB
        Intake["Intake Agent"]
        Classifier["Subtype + Scene Classifier"]
        FormPlanner["Form Planner Agent"]
        Completeness{"关键信息完整?"}
        Clarify["Clarification Agent"]
    end
    subgraph GenerationLayer["章节生成策略层"]
        direction LR
        GenPlanner["Generation Planner"]
        Router["Chapter Router"]
        FillOnly["fill_only"]
        SelectFill["select_and_fill"]
        Compose["controlled_compose"]
        DeriveRules["derive_by_rules"]
        Assembler["Assembler"]
    end
    subgraph ReviewLayer["审核与修订闭环"]
        direction TB
        Context["Context Agent"]
        Consistency["Consistency Agent"]
        Compliance["Compliance Agent"]
        Pass{"通过审核?"}
        RevisionPlanner["Revision Planner"]
        Revision["Revision Agent"]
        Output["Output / Publish Pack"]
    end
    subgraph SDKLayer["SDK 工具层"]
        direction LR
        LLMClient["LLMClient"]
        KnowledgeStore["KnowledgeStore"]
        GenerationEngine["GenerationEngine"]
        GenerationContext["GenerationContext"]
        AuditEngine["AuditEngine"]
    end
    Intake --> Classifier --> FormPlanner --> Completeness
    Completeness -- 否 --> Clarify --> FormPlanner
    Completeness -- 是 --> GenPlanner --> Router
    Router --> FillOnly --> Assembler
    Router --> SelectFill --> Assembler
    Router --> Compose --> Assembler
    Router --> DeriveRules --> Assembler
    Assembler --> Context --> Consistency --> Compliance --> Pass
    Pass -- 否 --> RevisionPlanner --> Revision --> Consistency
    Pass -- 是 --> Output
    GenerationEngine -.-> FillOnly
    GenerationEngine -.-> SelectFill
    KnowledgeStore -.-> GenPlanner
    KnowledgeStore -.-> SelectFill
    KnowledgeStore -.-> DeriveRules
    KnowledgeStore -.-> Compliance
    LLMClient -.-> Compose
    GenerationContext -.-> Context
    AuditEngine -.-> Compliance
    classDef agent fill:#D9EAD3,stroke:#6A8F63,color:#1f2d2a
    classDef policy fill:#EADCF8,stroke:#8B67A6,color:#1f2d2a
    classDef decision fill:#DDF4FF,stroke:#2F80A8,color:#1f2d2a
    classDef output fill:#DDEFD5,stroke:#6A8F63,color:#1f2d2a
    classDef sdk fill:#EFE6D2,stroke:#9A825A,color:#1f2d2a
    classDef input fill:#FCE4D6,stroke:#B76E4C,color:#1f2d2a
    class Start input
    class Intake,Classifier,FormPlanner,Clarify,GenPlanner,Router,Context,Consistency,Compliance agent
    class FillOnly,SelectFill,Compose,DeriveRules,Assembler policy
    class Completeness,Pass decision
    class RevisionPlanner,Revision agent
    class Output output
    class LLMClient,KnowledgeStore,GenerationEngine,GenerationContext,AuditEngine sdk
"""


MERMAID_CONFIG = {
    "theme": "base",
    "flowchart": {"htmlLabels": False, "curve": "basis", "nodeSpacing": 44, "rankSpacing": 58},
    "themeVariables": {
        "fontFamily": "Microsoft YaHei, SimHei, Noto Sans CJK SC, sans-serif",
        "fontSize": "13px",
        "primaryColor": "#D9EAD3",
        "primaryTextColor": "#1f2d2a",
        "primaryBorderColor": "#6A8F63",
        "lineColor": "#61736b",
        "clusterBkg": "#fffaf0",
        "clusterBorder": "#decfaa",
    },
}


def card(
    node_id,
    name,
    node_type,
    agentic,
    layer,
    summary,
    purpose,
    inputs,
    outputs,
    notes,
    graph_role="",
    phase_scope="",
    upstream=None,
    downstream=None,
    future_link="",
):
    return {
        "id": node_id,
        "name": name,
        "type": node_type,
        "agentic": agentic,
        "layer": layer,
        "summary": summary,
        "purpose": purpose,
        "inputs": inputs,
        "outputs": outputs,
        "notes": notes,
        "graph_role": graph_role,
        "phase_scope": phase_scope,
        "upstream": upstream or [],
        "downstream": downstream or [],
        "future_link": future_link,
    }


def merge_card_metadata(cards, metadata):
    merged = []
    for item in cards:
        extra = metadata.get(item["id"], {})
        merged.append({**item, **extra})
    return merged


def filter_cards(cards, excluded_ids):
    return [item for item in cards if item["id"] not in excluded_ids]


KNOWLEDGE_CARDS = [
    card("Raw", "Raw 原始资料", "输入资产", "否", "输入资产", "未处理的施工方案原文和附件集合。", "保留原始事实、证据和格式来源，作为后续抽取、复核和追溯依据。", ["doc/docx/pdf/xls/ppt/图片/压缩包", "文件名和目录结构"], ["原文证据", "附件引用", "版本来源"], "Raw 不应直接作为生成正文的唯一来源，更适合作为证据库和补充抽取来源。"),
    card("Processed", "Processed 章节树", "主输入资产", "否", "输入资产", "正式版处理数据，包含章节树和 text/table/image 内容块。", "作为建库主输入，因为它已经比 Raw 更接近可检索、可切片、可模板化的形态。", ["Formal_Version_Data_Processed", "基础/架线/跨越/立塔/消缺五类目录"], ["章节节点", "文本块", "表格块", "图片引用"], "当前建库重点是文本和表格；图片先保留引用，后续需要时再纳入生成。"),
    card("TaskBook", "计划任务书 / 标准规范", "规则来源", "否", "输入资产", "定义智能编制、精准审核、动态管控等目标。", "为知识库分类、生成策略和审核规则提供约束。", ["计划任务书", "施工规范", "管理制度"], ["体系目标", "审核维度", "风险规则来源"], "任务书要求区分模板固定内容、预置可选段落、关键参数填写项和人工补充。"),
    card("RawParser", "Document Parse Agent", "Agentic 解析节点", "是", "结构归一化", "解析 Raw 文档、表格和附件，并保留来源证据。", "把非结构化原文变成可进入统一处理链路的片段。", ["Raw 原始资料", "文件类型识别"], ["原文片段", "表格内容", "附件证据"], "解析结果不直接等于最终知识，需要再经过归一化、切片和人工抽查。"),
    card("Normalizer", "Structure Normalizer", "结构归一化节点", "规则优先", "结构归一化", "把 Raw 抽取结果和 Processed JSON 统一成同一套章节/内容块模型。", "消除不同来源格式差异，让后续节点只面对统一结构。", ["Raw 解析结果", "Processed 章节树"], ["统一节点路径", "统一内容块", "统一表格结构"], "这一步应尽量规则化，减少模型自由判断带来的不稳定。"),
    card("Chunker", "Chunk & Dedup Agent", "切片去重节点", "部分", "结构归一化", "按章节、段落、表格、图片引用切片，并对重复内容去重。", "解决多子类型目录中存在同名 JSON 和重复段落的问题。", ["统一章节树", "内容块", "子类型标签"], ["chunk id", "内容 hash", "多标签归属"], "去重时不能丢掉多标签关系，例如同一文件可能属于多个子类型。"),
    card("Taxonomy", "Taxonomy Tagger", "Agentic 标签节点", "是，可人工校正", "结构归一化", "标注子类型、工况、章节类别和风险场景。", "让检索和生成能按基础、架线、跨越、立塔、消缺精准过滤。", ["chunk", "章节标题", "子类型目录", "工况关键词"], ["子类型标签", "工况标签", "章节标签", "风险场景标签"], "标签体系是后续开放式写作和审核规则加载的基础。"),
    card("SlotMiner", "Slot Miner", "Agentic 参数槽识别节点", "是", "知识识别", "识别 XXXX、待补充、空表格项等挖空内容。", "把原文占位符映射成语义字段，避免表单绑定某一份原文的占位符顺序。", ["章节文本", "表格单元格", "占位符上下文"], ["字段 id", "字段别名", "单位", "必填规则"], "同一语义字段应统一，例如工程名称、起止点和工期不能重复维护。"),
    card("PassageCurator", "Passage Curator", "Agentic 段落整理节点", "是", "知识识别", "提取固定模板段落和预置可选段落。", "为 select_and_fill 和 controlled_compose 提供真实、可复用的写作素材。", ["章节段落", "子类型标签", "工况标签", "证据来源"], ["固定模板段落", "预置可选段落", "适用条件", "禁改/可改标记"], "开放式写作不应脱离段落库凭空生成。"),
    card("RuleExtractor", "Rule & Risk Extractor", "Agentic 规则识别节点", "是", "知识识别", "抽取深基坑、高塔、跨越、带电作业等风险触发条件。", "把计划任务书中的精准审核要求落到可执行规则。", ["计划任务书", "规范条文", "真实方案风险措施段落"], ["触发条件", "阈值", "必备措施", "审核检查点"], "规则应能解释触发原因，例如基础深度、高塔高度、跨越电压等级。"),
    card("EvidenceLinker", "Evidence Linker", "证据链接节点", "规则优先", "知识识别", "把参数、段落和规则回链到原始文件与章节路径。", "解决生成和审核中的可追溯问题。", ["chunk id", "文件路径", "章节路径", "表格编号"], ["证据引用", "来源版本", "复核线索"], "没有证据链的段落和规则不应直接进入正式知识库。"),
    card("SlotStore", "Schema / Slot Store", "专题知识库", "否", "专题知识库", "存放统一表单字段、单位、别名和校验规则。", "支撑动态表单和参数化生成，避免每套原文都产生独立表单。", ["字段 id", "字段标签", "单位", "来源占位符"], ["可复用字段 schema"], "这是知识资产，不是 Agent。"),
    card("PassageStore", "Reusable Passage Store", "专题知识库", "否", "专题知识库", "存放可复用施工段落及其适用条件。", "让开放式写作有真实素材来源。", ["固定模板段落", "预置可选段落", "适用条件", "证据链接"], ["段落候选", "段落元数据", "证据引用"], "段落应带禁改/可改标记。"),
    card("RuleStore", "Rule & Risk Store", "专题知识库", "否", "专题知识库", "存放审核检查点、风险触发条件和整改建议。", "支撑生成期的规则派生和审核期的合规检查。", ["风险规则", "阈值", "必备措施", "规范依据"], ["检查点", "风险等级", "整改建议"], "它不是单纯评分表，核心是结构化问题和证据。"),
    card("EvidenceStore", "Evidence Store", "专题知识库", "否", "专题知识库", "存放原文证据、附件引用、章节路径和版本来源。", "保证生成段落、参数字段和审核规则都能回溯。", ["原始文件", "章节路径", "表格编号", "版本信息"], ["证据索引", "来源追踪", "复核线索"], "证据链是避免模型黑箱写作的重要基础。"),
    card("KnowledgeStore", "KnowledgeStore", "SDK 工具", "否，供 Agent 调用", "SDK 索引与工具层", "母项目 SDK 中的统一知识检索入口。", "为 Agent 提供参数槽、段落、规则和证据的检索能力。", ["检索 query", "子类型/工况/章节过滤条件"], ["字段槽", "段落候选", "规则候选", "证据引用"], "KnowledgeStore 是工具，不是 Agent。"),
    card("SDKTools", "SDK Tools", "SDK 工具集合", "否，供 Agent 调用", "SDK 索引与工具层", "GenerationEngine、GenerationContext、AuditEngine、LLMClient 等能力集合。", "把母项目已有能力封装给 Agent 系统使用。", ["模板", "上下文", "规则", "模型配置"], ["模板填充", "上下文状态", "审核执行", "LLM 结果"], "SDK 是工具层，不应被误解为多 Agent 系统本身。"),
    card("Governance", "Governance", "治理与留痕节点", "否", "SDK 索引与工具层", "管理版本、证据链和人工确认状态。", "让知识更新和生成结果可追溯、可审计、可回滚。", ["知识库版本", "证据链", "人工确认记录"], ["版本记录", "审批状态", "变更留痕"], "正式系统里，治理层是控制知识库质量和责任边界的关键。"),
]


AGENT_CARDS = [
    card("Start", "开始", "入口节点", "否", "输入", "系统运行的触发点。", "接收用户选择的工程类型、子类型、项目资料和人工补充要求。", ["线路工程任务", "项目资料", "人工补充要求"], ["标准化任务请求"], "它不是 Agent，也不做推理。"),
    card("Intake", "Intake Agent", "Agentic 需求归一化节点", "是", "需求理解与表单规划", "把自然语言、附件说明和结构化输入整理成统一任务描述。", "让后续分类、表单规划和生成策略不用直接面对杂乱材料。", ["用户补充要求", "项目基础资料", "外部文档或表格说明"], ["标准化需求摘要", "约束清单", "待确认信息"], "只整理需求，不直接生成施工方案正文。"),
    card("Classifier", "Subtype Classifier", "Agentic 分类节点", "是，可人工覆盖", "需求理解与表单规划", "判断方案属于基础、架线、跨越、立塔、消缺中的哪一类，并识别关键工况。", "决定表单字段、段落检索范围和审核规则集合。", ["标准化需求摘要", "工程名称/施工内容", "Processed 数据标签"], ["工程子类型", "工况标签", "风险场景标签"], "分类结果必须允许用户确认或覆盖。"),
    card("FormPlanner", "Form Planner Agent", "Agentic 表单规划节点", "是", "需求理解与表单规划", "根据子类型、章节模板和字段槽生成表单 schema。", "让前端表单面向语义字段，而不是面向某一份原文的占位符顺序。", ["子类型和工况标签", "Schema / Slot Store", "模板章节策略"], ["必填字段", "可选字段", "可编辑表格字段", "字段校验规则"], "字段应来自受控字段库，不能临时发明不可追溯字段。"),
    card("Completeness", "关键信息是否完整？", "决策节点", "部分，规则优先", "需求理解与表单规划", "判断生成和审核所需关键参数是否足够。", "在进入生成前拦截缺失核心字段。", ["表单数据", "必填规则", "审核触发条件"], ["通过/不通过判断", "缺失字段清单"], "优先使用规则；语义不明确时才用 LLM 辅助。"),
    card("Clarify", "Clarification Agent", "Agentic 补问节点", "是", "需求理解与表单规划", "只针对影响生成或审核的缺失字段进行补问。", "减少用户一次性填写压力，同时避免开放式 chat 无限制追问。", ["缺失字段清单", "字段重要性", "当前输入"], ["补问问题", "补充后的字段值"], "补问必须短、具体、可回答。"),
    card("GenPlanner", "Generation Planner", "Agentic 生成规划节点", "是", "章节生成策略层", "为每个章节决定采用哪一种生成策略。", "规划哪些内容稳定、哪些内容可选、哪些内容可写、哪些内容由规则触发。", ["章节清单", "子类型和工况", "用户补充要求", "知识库检索摘要"], ["章节级生成策略计划", "禁改章节清单", "检索主题"], "这是规划节点，不同于 fill_only 这类具体策略执行节点。"),
    card("Router", "Chapter Router", "路由/编排节点", "弱 Agentic 或规则编排", "章节生成策略层", "按照 Generation Planner 的计划，把章节分派给对应策略节点。", "保持主流程可控，同时允许局部章节走不同处理路径。", ["章节级策略计划", "章节模板", "上下文状态"], ["策略任务分派"], "主要做编排和分派，不负责自己写正文。"),
    card("FillOnly", "fill_only", "确定性生成策略节点", "否", "章节生成策略层", "固定模板 + 参数填充，不调用 LLM 改写。", "用于高稳定、高风险、强工序约束章节，例如第三章施工技术措施。", ["章节模板", "表单字段", "可编辑表格数据"], ["已填参章节正文"], "这是策略执行节点，不是 Agent；禁止客制化改写。"),
    card("SelectFill", "select_and_fill", "检索选择型生成策略节点", "部分", "章节生成策略层", "从预置可选段落库中选择适合当前工况的段落，再执行参数填充。", "处理同一章节下存在多个真实可复用写法的情况。", ["章节主题", "子类型和工况标签", "Reusable Passage Store", "表单字段"], ["被选段落", "填参片段", "段落证据引用"], "候选段落必须来自知识库并带证据链。"),
    card("Compose", "controlled_compose", "受控写作策略节点", "是", "章节生成策略层", "在模板骨架、检索段落和用户补充要求约束下做有限写作。", "用于需要融合客制化要求、但又不能脱离真实方案素材的章节。", ["模板骨架", "检索段落", "人工补充要求", "禁改规则"], ["受控改写章节", "保留结构和参数", "引用证据"], "最接近开放式写作，但必须保留章节结构、表格、关键参数和证据来源。"),
    card("DeriveRules", "derive_by_rules", "规则派生策略节点", "部分，规则优先", "章节生成策略层", "根据工程参数触发安全、质量、应急和验收措施。", "把计划任务书要求的审核规则前置到生成阶段。", ["关键参数", "Rule & Risk Store", "章节上下文"], ["风险控制措施", "触发规则说明", "规范依据"], "输出应能追溯到规则，例如深基坑、高塔、跨越电压等级等条件。"),
    card("Assembler", "Assembler", "确定性组装节点", "否", "章节生成策略层", "合并目录、章节、表格、引用和版本信息。", "保证输出结构稳定，避免各节点直接拼整篇导致格式混乱。", ["各章节片段", "目录规则", "表格内容", "证据引用"], ["完整施工方案草稿"], "只组装，不重写正文。"),
    card("Context", "Context Agent", "Agentic 上下文管理节点", "是", "审核与修订闭环", "维护术语、摘要、关键参数和跨章状态。", "解决长文生成中的一致性问题。", ["完整草稿", "字段上下文", "章节摘要"], ["跨章上下文状态", "术语表", "关键事实索引"], "不替代审核，只为一致性和合规检查提供上下文。"),
    card("Consistency", "Consistency Agent", "Agentic 一致性检查节点", "是", "审核与修订闭环", "检查跨章节参数、表述和引用是否互相冲突。", "发现工程名称、起止点、数量、工期等长文一致性问题。", ["施工方案草稿", "上下文状态", "关键字段表"], ["一致性问题清单", "问题定位", "建议修订章节"], "问题必须尽量定位到章节和字段。"),
    card("Compliance", "Compliance Agent", "Agentic 合规审核节点", "是", "审核与修订闭环", "调用审核规则检查方案是否缺少必要控制措施、依据或关键参数。", "把精准审核落到结构化检查项和整改建议。", ["施工方案草稿", "Rule & Risk Store", "AuditEngine 检查点"], ["检查项结果", "问题分级", "证据", "整改建议"], "核心产物是可追溯的问题清单，不是单一总分。"),
    card("Pass", "是否通过审核？", "决策节点", "部分，规则优先", "审核与修订闭环", "根据一致性和合规检查结果判断是否进入交付或修订。", "形成可控闭环，避免有明确缺陷的方案直接输出。", ["一致性问题清单", "合规审核结果", "人工确认状态"], ["通过/不通过判断"], "不建议完全交给模型主观判断。"),
    card("RevisionPlanner", "Revision Planner", "Agentic 修订规划节点", "是", "审核与修订闭环", "把审核问题拆成具体、可执行、可定位的修订任务。", "避免 Revision Agent 重写整篇文档，只让它处理必要章节。", ["审核问题清单", "章节结构", "禁改章节清单"], ["修订任务列表", "目标章节", "禁止修改范围"], "必须尊重 fill_only 锁定章节。"),
    card("Revision", "Revision Agent", "Agentic 定向修订节点", "是", "审核与修订闭环", "根据修订任务只修改命中的章节或段落。", "让审核问题闭环，同时保持原模板结构和已通过内容稳定。", ["修订任务", "原章节内容", "上下文状态", "禁改规则"], ["修订后的章节", "变更说明"], "不能重写整篇，也不能修改 fill_only 锁定章节。"),
    card("Output", "最终交付", "输出节点", "否", "审核与修订闭环", "输出施工方案、审核报告和变更记录。", "把生成、审核、修订后的结果沉淀为可交付文件和可追溯记录。", ["通过审核的施工方案", "审核报告", "变更记录"], ["Markdown/Word 施工方案", "结构化审核报告", "版本与证据链"], "后续可扩展为现场检查表和闭环记录。"),
    card("LLMClient", "LLMClient", "SDK 工具", "否，供 Agent 调用", "SDK 工具层", "母项目中的 LLM 调用封装。", "统一模型调用方式，避免各 Agent 散落调用不同 provider。", ["Prompt", "上下文", "模型配置"], ["模型返回文本或结构化结果"], "它本身不是 Agent，不做任务规划。"),
    card("KnowledgeStore", "KnowledgeStore", "SDK 工具", "否，供 Agent 调用", "SDK 工具层", "母项目中的知识库检索入口。", "查参数槽、可复用段落、规则和证据。", ["检索 query", "子类型/工况/章节过滤条件"], ["字段槽", "段落候选", "审核规则", "证据引用"], "它是 SDK 工具，不是多 Agent 系统本身。"),
    card("GenerationEngine", "GenerationEngine", "SDK 工具", "否，供 Agent 调用", "SDK 工具层", "母项目中的模板生成工具。", "承接确定性模板渲染，保持生成结果格式稳定。", ["模板", "上下文变量", "章节配置"], ["渲染后的章节文本"], "适合支撑 fill_only 和部分 select_and_fill 场景。"),
    card("GenerationContext", "GenerationContext", "SDK 工具", "否，供 Agent 调用", "SDK 工具层", "母项目中的上下文管理工具。", "保存摘要、术语、引用和跨章状态。", ["章节摘要", "术语", "引用", "字段状态"], ["可复用上下文状态"], "它不是判断节点，而是状态载体和上下文工具。"),
    card("AuditEngine", "AuditEngine", "SDK 工具", "否，供 Agent 调用", "SDK 工具层", "母项目中的审核执行工具。", "运行检查点并结构化输出问题。", ["审核规则", "方案文本", "结构化字段"], ["检查项结果", "问题清单", "建议"], "Compliance Agent 可以调用它，但它本身不是 Agent。"),
]


def apply_card_overrides(cards, overrides):
    updated = []
    for item in cards:
        merged = dict(item)
        merged.update(overrides.get(item["id"], {}))
        updated.append(merged)
    return updated


KNOWLEDGE_CARD_OVERRIDES = {
    "Raw": {
        "summary": "南网提供的未处理施工方案原文、扫描件、附件、盖章版和配套资料，是证据层输入而不是直接生成层输入。",
        "purpose": "解决“原始施工方案可读但不可直接稳定复用”的问题。Raw 往往同时包含扫描噪声、版式差异、重复版本和附件引用，如果不保留这层原始来源，后续抽出的参数、可复用段落和审核结论就无法回溯到具体文件、页码或附件。",
        "notes": "Raw 更适合承担证据底座和补充抽取来源，不应直接成为运行期唯一写作语料。真正给 Agent 高效使用的主输入，应是经过结构化处理的 Processed 数据。 ",
    },
    "Processed": {
        "summary": "Formal_Version_Data_Processed 中的结构化章节树，已经把五类线路工程方案整理为 text/table/image 内容块。",
        "purpose": "解决“原文太散、运行期无法直接做模板化和检索”的问题。Processed 已经把基础、架线、跨越、立塔、消缺五种子类型统一成章节树，适合做字段挖掘、章节级检索、段落复用和表格参数化，是知识库构建的主输入层。",
        "notes": "结合当前计划，建库重点是文本块和表格块，图片先保留引用关系。Processed 不是最终模板本身，而是构建字段槽、段落库和规则库的稳定中间层。",
    },
    "TaskBook": {
        "summary": "任务计划书与标准规范提供系统目标、边界和验收口径，决定什么内容可以固定、可选、填空或人工补充。",
        "purpose": "解决“系统应该生成到什么程度、审核按什么标准判定”的问题。它把项目目标从模糊的‘AI写方案’收敛为受控的工程文档编制与审核：固定模板内容、预置可选段落、关键参数填写项、人工补充内容四类资产必须明确分层。",
        "notes": "这一层不是普通背景材料，而是整个 Agent 系统的治理边界。没有它，开放式写作很容易越界到‘编造段落’或‘无法审计’。",
    },
    "RawParser": {
        "summary": "把 Raw 文档、附件和扫描件解析成可继续处理的文本、表格和来源片段。",
        "purpose": "解决“原始文档格式不统一，后续节点没法直接处理”的问题。不同来源可能是 Word、PDF、扫描页或附件截图，RawParser 负责把它们转成统一可读取的片段，同时尽量保留原始文件名、章节线索和附件关联，避免后面做知识抽取时丢失证据来源。",
        "notes": "它只负责把资料转成可处理形态，不负责判断哪些内容值得入库。解析质量会直接影响后续抽取与追溯质量。",
    },
    "Normalizer": {
        "summary": "把 Raw 解析结果和 Processed JSON 统一成同一套章节节点与内容块模型。",
        "purpose": "解决“不同数据源结构不一致，导致后续节点每次都要写特判”的问题。无论来源是原始文档解析结果还是已处理章节树，Normalizer 都将其统一为章节路径、块类型、表格结构和元数据一致的中间模型，这样后续切片、标签、字段挖掘和规则提取都可以复用同一套逻辑。",
        "notes": "这一步越规则化，后续 Agent 越稳定。它的价值在于把复杂性前移，而不是把复杂性留给生成或审核阶段。",
    },
    "Chunker": {
        "summary": "按章节、段落、表格和子主题切片，并处理重复段落与重复版本。",
        "purpose": "解决“整章文本太大、重复内容太多、检索命中不精确”的问题。线路工程方案里很多段落在不同项目、不同子类型之间高度重复，Chunker 负责把大段内容切成可检索、可复用、可追踪的小粒度单元，同时通过 hash 或相似度去重，避免知识库把同一句话存几十次。",
        "notes": "切得太粗会影响检索精度，切得太细会丢失上下文。这个节点的目标不是单纯分块，而是为后续‘选段落’和‘找证据’提供合适粒度。",
    },
    "Taxonomy": {
        "summary": "为切片内容打上子类型、工况、章节功能和风险场景标签。",
        "purpose": "解决“同样是线路工程，但不同子类型和工况检索范围完全不同”的问题。基础、架线、跨越、立塔、消缺的可复用段落和审核规则并不通用，Taxonomy 负责把知识片段标成可过滤、可路由、可审核的标签集合，让后续生成不会拿跨越工程的段落去写基础工程的章节。",
        "notes": "标签体系决定了系统能否从‘线路工程总类’继续细分到真正可执行的写作和审核范围，是后续 Chapter Router 和 KnowledgeStore 过滤能力的基础。",
    },
    "SlotMiner": {
        "summary": "从模板挖空、表格空项和上下文语义中提炼统一字段槽。",
        "purpose": "解决“原文中的 XXXX 只是视觉占位，不是系统可复用字段”的问题。SlotMiner 要把不同方案里出现的项目名称、起止桩号、工期、基础数量、塔型参数、跨越对象等占位，统一成稳定字段 id、字段别名和校验规则，支撑统一表单而不是为每份原文单独做一套问卷。",
        "notes": "它的价值在于语义归一，而不是机械替换占位符。否则同一个含义会在不同模板里产生多份重复字段。",
    },
    "PassageCurator": {
        "summary": "从真实方案中整理固定模板段、可选段和允许受控补写的素材段。",
        "purpose": "解决“开放式写作不能脱离真实施工方案原文随意生成”的问题。任务计划书并不是鼓励模型从零写全文，而是希望把可复用的真实表述沉淀下来，区分哪些段落必须原样填空、哪些可以按条件选择、哪些只允许在受控前提下补写扩展。",
        "notes": "这个节点决定了系统能否既保持真实行业口吻，又不过度依赖单一模板。它是从单模板 Demo 走向多原文知识驱动写作的关键桥梁。",
    },
    "RuleExtractor": {
        "summary": "从任务计划书、制度规范和历史方案中抽取风险触发条件、检查点和整改建议。",
        "purpose": "解决“审核不能只靠打分或主观点评”的问题。RuleExtractor 要把‘何时必须补充安全措施、何时构成高风险、哪些章节必须包含哪些要素’转成结构化规则，让系统既能在生成期补全措施，也能在审核期输出有依据的缺陷与建议。",
        "notes": "它抽取的不是泛泛而谈的‘注意安全’，而是与线路工程子类型、工况参数、章节要求绑定的可执行规则。",
    },
    "EvidenceLinker": {
        "summary": "为字段、段落和规则建立回到原文件、原章节、原表格的证据链。",
        "purpose": "解决“生成结果、审核结论和知识片段无法追溯来源”的问题。没有证据链，就无法回答‘这段话来自哪份正式方案’‘这个审核意见依据哪条规范或哪张表’。EvidenceLinker 负责把每一类知识资产都挂回源文件与版本。",
        "notes": "这一步直接支撑后期的人审、复核和责任边界。对基建场景来说，可追溯比多写一段华丽文字更重要。",
    },
    "SlotStore": {
        "summary": "统一字段槽库，保存字段 id、别名、单位、默认值与校验规则。",
        "purpose": "解决“表单字段散落在模板和代码里，无法跨模板复用”的问题。它让同一工程类型下不同原文模板仍可共享一套字段语义，也为后续多原文、多模板、多章节接入提供稳定字段底座。",
        "notes": "这不是前端表单本身，而是表单背后的语义字段知识库。它决定了系统能否做到表单统一、模板多样。",
    },
    "PassageStore": {
        "summary": "保存真实方案中整理出的可复用段落、适用条件和改写边界。",
        "purpose": "解决“系统做开放式写作时没有可靠素材库”的问题。PassageStore 不是把所有历史方案全文塞进去，而是把已经确认可复用、可检索、可追溯的段落资产化，供 select_and_fill 和 controlled_compose 使用。",
        "notes": "它是系统从模板填空走向知识驱动写作的核心资产库，但前提是每一段都带适用条件和证据来源。",
    },
    "RuleStore": {
        "summary": "保存结构化审核规则、风险触发条件、检查点和整改建议。",
        "purpose": "解决“审核逻辑只能写死在 prompt 里，无法复用和解释”的问题。RuleStore 把审核依据从单次 prompt 中抽离出来，让审核结果可追溯、可复用、可迭代，并能针对不同子类型和工况动态加载不同检查集合。",
        "notes": "它不只是分数配置表，而是问题结构、风险条件和建议模板的统一管理处。",
    },
    "EvidenceStore": {
        "summary": "集中管理文件来源、章节路径、表格编号、附件引用和版本信息。",
        "purpose": "解决“知识项入库后与原始资料脱钩”的问题。字段、段落、规则如果没有统一的证据索引，就无法在输出审核报告或人工复核时快速定位到源材料。EvidenceStore 让知识库保持可追溯性，而不是只剩最终文本。",
        "notes": "它和 PassageStore、RuleStore、SlotStore配套存在，目的是让所有知识资产都能回到来源，而不是孤立存储。",
    },
    "KnowledgeStore": {
        "summary": "Scrivai SDK 中统一的知识检索入口，屏蔽底层多类知识资产的存储差异。",
        "purpose": "解决“运行时 Agent 不应该分别操作字段库、段落库、规则库和证据库”的问题。KnowledgeStore 负责统一检索接口，让上层节点按子类型、章节、风险场景和查询语义取回所需资产，而不是自己管理底层库结构。",
        "notes": "在架构里它是工具，不是 Agent。Agent 做决策，KnowledgeStore 提供受控知识。",
    },
    "SDKTools": {
        "summary": "Scrivai SDK 已有工具能力集合，包括生成、上下文管理、审核和模型调用。",
        "purpose": "解决“新系统不必重造底层轮子”的问题。我们设计的 Agent 层应调用既有 SDK 能力完成模板填充、上下文维护、知识检索和审核执行，而不是把所有逻辑重新写一遍。",
        "notes": "它代表工具编排层，不代表工作流本身。真正的 Agent 价值在于如何调用和组织这些工具。",
    },
    "Governance": {
        "summary": "负责知识版本、人工确认、变更留痕和可审计治理。",
        "purpose": "解决“知识库一旦持续更新，就必须知道谁改了什么、依据何在、当前是否可上线”的问题。尤其在后续多小组持续补充 Raw/Processed 数据时，Governance 决定哪些知识资产已审核、哪些仍是草稿、哪些版本可被运行期调用。",
        "notes": "这层通常不直接参与生成，但它决定系统能否在企业环境中长期可维护、可追责、可回滚。",
    },
}


AGENT_CARD_OVERRIDES = {
    "Start": {
        "summary": "用户发起一次线路工程施工方案任务，输入项目资料、子类型线索和补充要求。",
        "purpose": "解决“系统从哪里开始、接受哪些输入”的问题。开始节点明确这不是纯聊天，而是一次受控的工程文档任务入口，后续所有决策都从这里取得项目背景、资料附件和用户约束。",
        "notes": "它本身不推理，也不做生成；价值在于把任务显式化，便于后续节点接管。",
    },
    "Intake": {
        "summary": "把自然语言诉求、上传资料和结构化输入合并成统一任务说明。",
        "purpose": "解决“用户输入来源杂、格式乱、口径不一致”的问题。实际项目里，用户可能同时给工程名称、附件、补充要求和口头说明；Intake Agent 负责先把这些输入归一成可计算的任务包，避免后面每个节点都自己猜用户想表达什么。",
        "notes": "它只做任务理解和约束整理，不直接写章节，也不决定最终生成策略。",
    },
    "Classifier": {
        "summary": "识别线路工程属于基础、架线、跨越、立塔、消缺中的哪一类，并提取关键工况标签。",
        "purpose": "解决“同属线路工程，但知识范围、模板章节和审核规则并不通用”的问题。分类结果会决定表单字段、可检索段落范围、风险规则集合，避免系统把跨越工程的经验段落错误写进基础工程方案里。",
        "notes": "分类结果必须允许人工覆盖，因为项目资料可能不完整，且一个项目也可能出现复合工况。",
    },
    "FormPlanner": {
        "summary": "基于子类型、章节要求和字段槽库生成统一表单 schema。",
        "purpose": "解决“多原文、多模板场景下前端表单到底怎么问”的问题。Form Planner 不再围绕某一份模板的 XXXX 顺序问问题，而是围绕统一语义字段组织表单，让不同模板共享同一套字段底座，并按章节和工况决定哪些字段必须问、哪些字段可选、哪些表格可编辑。",
        "notes": "它是统一表单体验的关键节点，也是从单模板 Demo 走向多原文知识驱动写作的第一道关口。",
    },
    "Completeness": {
        "summary": "检查当前输入是否已经足以支持安全生成和后续审核。",
        "purpose": "解决“缺关键参数时系统仍硬写正文，导致方案看似完整但实际不可用”的问题。它会判断项目名称、范围、工期、关键数量、跨越对象、风险参数等是否缺失，并阻止系统在缺核心信息时进入生成阶段。",
        "notes": "这一步优先依据规则和字段要求，不应退化成笼统的‘感觉信息差不多了’。",
    },
    "Clarify": {
        "summary": "只追问真正影响生成或审核的缺失字段，而不是泛泛重复提问。",
        "purpose": "解决“补问过多、过泛、影响用户填写效率”的问题。Clarification Agent 会把缺口收敛成最小必要问题集，例如缺的是跨越对象还是工期、缺的是塔型参数还是基础数量，从而让用户补充的每一项都能直接降低后续生成和审核风险。",
        "notes": "它是补问节点，不是闲聊节点。问题越精确，后续生成越稳定。",
    },
    "GenPlanner": {
        "summary": "为每一章确定采用填空、选段、受控补写还是规则推导的生成策略。",
        "purpose": "解决“不同章节不能用一套写法一把梭”的问题。依据任务计划书提出的四类资产边界，它会把章节区分为固定模板填空、检索选段拼装、受控开放式补写、规则驱动生成，并明确像第三章这类高确定性章节应走 fill_only，而不是让模型自由改写。",
        "notes": "这个节点决定系统是不是‘受控编制’，也是避免整个方案被一个大 prompt 写成同一种口气的关键。",
    },
    "Router": {
        "summary": "把 Generation Planner 的策略落实到具体章节，逐章路由到对应执行方式。",
        "purpose": "解决“即使规划好了策略，也需要真正按章分发执行”的问题。Chapter Router 会针对当前章标题、章节功能、锁定规则和知识可用性，决定该章进入 fill_only、select_and_fill、controlled_compose 还是 derive_by_rules，避免全局策略只停留在纸面上。",
        "notes": "它是章节级执行分发器，不重新做上游规划判断。",
    },
    "FillOnly": {
        "summary": "对高确定性章节做纯模板填空，不允许运行时自由改写。",
        "purpose": "解决“某些章节本来就应该稳定、正式、可控，没必要让模型发挥”的问题。例如封面、审批页、固定说明段、以及像第三章这样已高度模板化的施工技术措施，都更适合通过字段填充和表格写入完成，而不是让模型改写措辞。",
        "notes": "这是确定性最强的生成路径，优先保证格式稳定、字段准确和版本可控。",
    },
    "SelectFill": {
        "summary": "从可复用段落库中检索候选段，按条件选择后再结合参数落到当前章节。",
        "purpose": "解决“章节不是纯固定模板，但也不该从零写”的问题。它会从真实历史方案中选择适用于当前子类型、工况和章节目标的段落，再把项目参数嵌入其中，从而在保持真实行业口吻的同时减少模型自由发挥。",
        "notes": "它强调‘选真实段落并填参数’，不是让模型凭空扩写。",
    },
    "Compose": {
        "summary": "在受控边界内做开放式补写，补足固定模板和段落库未覆盖的内容。",
        "purpose": "解决“有些章节存在一定开放写作空间，但不能彻底脱离知识和风格约束”的问题。controlled_compose 会把已检索到的段落、模板风格、项目参数和禁改要求一起喂给模型，让模型只在必要范围内补写，而不是重写整章。",
        "notes": "它是最接近开放式写作的节点，因此必须同时受知识库、模板风格和证据边界约束。",
    },
    "DeriveRules": {
        "summary": "根据参数和规则库推导必须出现的风险措施、检查点和约束说明。",
        "purpose": "解决“有些内容不是历史段落直接复用，而是由工程参数触发”的问题。比如跨越对象、电压等级、作业环境、基础深度等条件会触发不同的安全措施和审核要点，这些内容应由规则推导，而不是单纯靠模型回忆。",
        "notes": "它把规则资产变成生成资产，是生成与审核共用的一条桥梁。",
    },
    "Assembler": {
        "summary": "把不同策略产出的章节片段重新拼装成一份结构完整、编号正确、风格统一的方案正文。",
        "purpose": "解决“各章分别生成后，整份文档容易出现编号混乱、表格位置错乱、口吻断裂”的问题。Assembler 负责统一目录层级、章节顺序、表格位置和基础格式，让多策略生成的结果最终看起来像一份完整方案，而不是几段拼贴文本。",
        "notes": "它不应重新创作内容，重点是结构装配和结果归并。",
    },
    "Context": {
        "summary": "维护项目级上下文，包括章节摘要、术语、引用和已确认事实。",
        "purpose": "解决“后写章节看不到前面已经确定的术语、数量和口径”的问题。Context Agent 会把前文已确定的项目名称、数量、时间、术语和引用关系沉淀下来，避免后续章节重新命名、重复解释或出现相互矛盾的表述。",
        "notes": "它是跨章一致性的基础，不直接判断对错，但决定后续节点是否拿得到共享上下文。",
    },
    "Consistency": {
        "summary": "检查跨章节、跨表格、跨段落的事实一致性和表述一致性。",
        "purpose": "解决“每章单看都合理，但整份方案前后自相矛盾”的问题。它重点关注项目名、日期、工期、数量、起止范围、术语口径、章节引用是否一致，防止因多节点生成导致同一事实在不同位置写出不同版本。",
        "notes": "它关心的是全局一致，不等同于合规审核；合规还要看规则是否满足。",
    },
    "Compliance": {
        "summary": "调用审核规则和证据链，对已生成方案做结构化合规检查。",
        "purpose": "解决“方案生成出来以后，系统如何给出可解释、可复核的审核意见”的问题。Compliance Agent 不只输出一个分数，而是基于规则库、证据引用和章节内容形成问题清单：缺什么、为什么缺、依据是什么、建议怎么补。",
        "notes": "它是精准审核的核心节点，输出应便于后续 Revision Planner 消化，而不是模糊评价。",
    },
    "Pass": {
        "summary": "基于一致性与合规检查结果，决定方案进入交付还是进入修订闭环。",
        "purpose": "解决“系统何时应该停止生成并交付，何时必须继续修订”的问题。这个节点把上游审核结果收敛为明确分流，避免存在实质性缺陷的方案直接流出，也避免轻微问题导致无限重写。",
        "notes": "它应该结合规则严重度和人工确认口径，而不是完全依赖模型主观判断。",
    },
    "RevisionPlanner": {
        "summary": "把审核发现拆成可执行、可定位、可排序的修订任务清单。",
        "purpose": "解决“审核问题出来了，但 Revision Agent 不知道该先改哪、改多大、能不能改”的问题。Revision Planner 会把缺陷映射到具体章节、具体问题类型和允许采用的修订策略，并标出哪些章节是禁改或仅能局部修改。",
        "notes": "它的目标是把修订从‘重写全文’变成‘定向修复缺陷’。",
    },
    "Revision": {
        "summary": "按修订任务定向修改命中的章节或段落，并保留未命中部分稳定。",
        "purpose": "解决“修一次小问题却把整篇文档全部改乱”的问题。Revision Agent 只对被指派的问题位置做修正，尽量保持已通过审核章节、fill_only 章节和已确认事实不被重新改写，从而形成稳定闭环。",
        "notes": "它必须是局部修订，不应退化成另一轮从头生成。",
    },
    "Output": {
        "summary": "输出最终方案正文及配套审核、变更和追溯结果。",
        "purpose": "解决“系统最终到底交付什么”的问题。除了施工方案正文本身，真实企业场景还需要保留审核意见、修订记录、版本信息和证据链，以便后续会签、复核、归档和责任追踪。",
        "notes": "交付物不应只是一份 Markdown 文本，而应是可追溯的文档结果集合。",
    },
    "LLMClient": {
        "summary": "Scrivai SDK 中的模型调用客户端，统一封装模型访问方式。",
        "purpose": "解决“各 Agent 如果各自直连模型，会导致 provider 差异、调用方式和超时处理全部散落”的问题。LLMClient 把模型调用收敛成统一接口，供 Clarify、Compose、Revision 等需要模型能力的节点使用。",
        "notes": "它提供模型能力，但不负责工作流编排，也不决定哪个节点该不该调用模型。",
    },
    "KnowledgeStore": {
        "summary": "运行期统一检索字段槽、段落候选、审核规则和证据引用的 SDK 工具入口。",
        "purpose": "解决“Agent 层需要知识，但不应该知道底层知识库如何组织”的问题。通过统一检索接口，Agent 可以按子类型、章节和工况拉取所需知识资产，避免每个节点自行拼数据库查询逻辑。",
        "notes": "在 Agent 流程图里它是支撑工具，而不是一个会自主决策的 Agent。",
    },
    "GenerationEngine": {
        "summary": "Scrivai SDK 中的模板渲染与章节生成工具。",
        "purpose": "解决“高确定性章节需要稳定生成，而不是每次都让模型自由发挥”的问题。GenerationEngine 负责把模板、变量和结构化上下文稳定渲染成章节文本，是 fill_only 和部分 select_and_fill 路径的底层执行器。",
        "notes": "它强调确定性和格式稳定，适合承接明确模板，不适合承担复杂策略决策。",
    },
    "GenerationContext": {
        "summary": "用于存放章节摘要、术语、引用关系和跨章状态的上下文工具。",
        "purpose": "解决“多章节流程中状态容易丢失或重复计算”的问题。GenerationContext 把前文抽取出的术语、摘要、引用和中间状态收拢起来，为 Context Agent 和后续章节提供稳定上下文载体。",
        "notes": "它是状态容器和工具，不是判断节点；没有它，多章生成容易失忆。",
    },
    "AuditEngine": {
        "summary": "Scrivai SDK 中执行结构化检查点审核的底层工具。",
        "purpose": "解决“审核意见不能只停留在 prompt 层文字输出”的问题。AuditEngine 负责按检查点运行审核，把结果结构化成问题、证据和建议，供 Compliance Agent 汇总与后续 Revision Planner 使用。",
        "notes": "它提供审核执行能力，但是否审核、审核哪些点、如何闭环，仍由上层 Agent 决定。",
    },
}


KNOWLEDGE_ROLE_REFINEMENTS = {
    "Raw": {
        "purpose": "这一层是知识构建链路的最左端，直接承接南网交付的原始方案、扫描件和附件。它不直接送去运行期写作，而是先交给 RawParser 做解析，同时为后面的 EvidenceLinker 留下最原始的来源锚点；这样 Slot、Passage、Rule 三类知识资产在入库后都还能回到具体文件和版本。",
    },
    "Processed": {
        "purpose": "它和 Raw 一起进入 Normalize，但角色不同：Raw 提供原始证据，Processed 提供已经整理好的章节树和块结构。后面的 Chunker、Taxonomy、SlotMiner、PassageCurator 会主要依赖这层的稳定结构做字段挖掘、章节级切片和段落沉淀，因此它相当于知识库构建的主语料底座。",
    },
    "TaskBook": {
        "purpose": "这一层给整个知识构建链提供边界条件，不是普通参考文档。它的内容先流向 RuleExtractor，帮助系统识别哪些检查点、风险条件和编制边界必须结构化保存；同时它也为后面运行期的 Generation Planner 和 Compliance Agent 提供判断标准，确保生成与审核都围绕同一套项目目标。",
    },
    "RawParser": {
        "purpose": "它直接承接 Raw，把原始文件中的文字、表格、附件线索转成可继续处理的解析结果，然后交给 Normalizer。没有这一步，后面的章节归一、字段提取和证据链建立都只能依赖人工处理好的数据，系统就无法吸收新到的原始资料。",
    },
    "Normalizer": {
        "purpose": "它是 RawParser 和 Processed 的汇合点：一边接收原始资料解析结果，一边接收已处理章节树，把两者统一成相同的章节节点、块类型和元数据结构。这样后面的 Chunker、Taxonomy、SlotMiner 和 RuleExtractor 就能围绕同一套数据模型工作，而不必为不同来源分别写逻辑。",
    },
    "Chunker": {
        "purpose": "它接在 Normalizer 后面，把统一后的章节内容切成适合检索和复用的粒度，并顺手处理重复段落与重复版本。切完的结果继续交给 Taxonomy 打标签，因此它决定了后面段落库、规则库和字段库拿到的是整章大块文本，还是足够细且可复用的知识单元。",
    },
    "Taxonomy": {
        "purpose": "它承接 Chunker 的切片结果，为每个片段补上子类型、工况、章节功能和风险场景标签，然后把带标签的知识分发给 SlotMiner、PassageCurator、RuleExtractor 和 EvidenceLinker。后面运行期的 KnowledgeStore 之所以能按‘基础/跨越/立塔’或‘风险工况’精准检索，基础就在这里打牢。",
    },
    "SlotMiner": {
        "purpose": "它从 Taxonomy 标注后的章节片段里识别可统一的参数槽，把看似零散的 XXXX、空表格项和上下文参数归并成稳定字段，然后写入 SlotStore。运行期的 Form Planner、fill_only 和部分审核规则都要依赖这些字段槽，所以它承担的是‘把原文占位变成系统字段’的角色。",
    },
    "PassageCurator": {
        "purpose": "它同样接在 Taxonomy 后面，但关注的是可复用表述而不是字段。它会把真实方案中的固定模板段、条件性可选段和允许受控补写的素材段整理出来，送进 PassageStore，供运行期的 select_and_fill 和 controlled_compose 调用，因此它决定了开放式写作是否始终站在真实方案表述之上。",
    },
    "RuleExtractor": {
        "purpose": "它一端接收 TaskBook 和规范，另一端接收带标签的真实方案片段，把两边的信息压缩成结构化风险条件、必备措施和检查点，再写入 RuleStore。后面的 derive_by_rules 和 Compliance Agent 都要以这里抽出来的规则为依据，所以它处在‘知识沉淀’与‘生成/审核执行’之间的枢纽位置。",
    },
    "EvidenceLinker": {
        "purpose": "它跟 SlotMiner、PassageCurator、RuleExtractor 平行工作，但不负责生产正文资产，而是负责给这些资产统一挂回源文件、章节路径和表格编号，再送入 EvidenceStore。这样运行期无论是生成某段正文还是输出某条审核意见，都能继续把结果追溯回来源。",
    },
    "SlotStore": {
        "purpose": "它承接 SlotMiner 的输出，把统一字段存成可以被检索和校验的字段库。运行期 Form Planner 会从这里生成表单 schema，fill_only 和部分审核规则也会读取这里的字段定义，因此它是表单层和模板层共享的一套参数底座。",
    },
    "PassageStore": {
        "purpose": "它承接 PassageCurator 整理出的可复用段落，把这些段落按适用条件、证据来源和禁改边界存起来。运行期 Router 一旦把某章送到 select_and_fill 或 controlled_compose，这里就是主要的候选素材来源，因此它是从单模板写作走向多原文写作的内容资产库。",
    },
    "RuleStore": {
        "purpose": "它把 RuleExtractor 产出的风险条件、检查点和整改建议沉淀成可调用规则。运行期 derive_by_rules 需要从这里推导应写入的措施，Compliance Agent 也需要从这里调用审核依据，因此它同时服务于生成和审核两条链路。",
    },
    "EvidenceStore": {
        "purpose": "它承接 EvidenceLinker 产出的来源索引，把字段、段落、规则和原始资料之间的映射稳定保存下来。这样后面 KnowledgeStore、Governance、人工复核和审计留痕都能围绕同一套证据索引工作，而不是各自重新找来源。",
    },
    "KnowledgeStore": {
        "purpose": "它站在四类知识资产之上，把 SlotStore、PassageStore、RuleStore、EvidenceStore 统一封装成单一检索入口。运行期的 Planner、Router、SelectFill、DeriveRules、Compliance 不需要知道底层各库存在哪，只需要通过它按子类型、章节和工况拿回对应知识。",
    },
    "SDKTools": {
        "purpose": "它接在 KnowledgeStore 之后，代表 Scrivai 母项目已有的工具能力被 Agent 系统复用的入口。换句话说，知识层在这里不再只是静态存储，而是被包装成 GenerationEngine、GenerationContext、AuditEngine、LLMClient 等运行期真正会调用的能力。",
    },
    "Governance": {
        "purpose": "它不在运行期热路径中央，但位于知识层出库前的治理口。KnowledgeStore 和各类资产库持续更新后，需要这一层记录版本、人工确认状态和上线边界，保证后面被 Agent 调用的是可追溯、可回滚、可审计的知识，而不是未经确认的草稿。",
    },
}


AGENT_ROLE_REFINEMENTS = {
    "Start": {
        "purpose": "它是整条运行链路的入口，把用户给出的工程类型、资料附件、补充要求和已有结构化参数打包成一次任务。这个任务包随后交给 Intake Agent 做归一化，因此 Start 更像是把‘聊天请求’切换成‘工程编制任务’的起点。",
    },
    "Intake": {
        "purpose": "它承接 Start 送来的混合输入，把自然语言诉求、附件说明和基础参数整理成统一任务摘要，再把结果交给 Classifier 和 Form Planner。这样下游节点拿到的不是零散材料，而是一份可以继续分类、补问和规划的任务上下文。",
    },
    "Classifier": {
        "purpose": "它接在 Intake 后面，利用任务摘要和资料线索先判断当前方案更接近基础、架线、跨越、立塔还是消缺，并补上工况标签。这个分类结果会直接影响下游 Form Planner 生成哪些字段、Generation Planner 检索哪些章节知识、Compliance 加载哪一组审核规则。",
    },
    "FormPlanner": {
        "purpose": "它承接 Classifier 给出的子类型和工况标签，再结合 SlotStore 中统一字段定义，把前端应该展示的字段、分组、必填规则和可编辑表格组织成 schema。随后 Completeness 会拿这份 schema 检查信息缺口，因此它处在‘知识字段’与‘用户填写体验’之间的转换位置。",
    },
    "Completeness": {
        "purpose": "它接收 Form Planner 组织好的表单结果和必填规则，判断当前资料是否足以进入生成。若缺的是关键字段，它把缺口清单交给 Clarification Agent；若信息已经完整，则把任务直接送去 Generation Planner，起到生成前总闸门的作用。",
    },
    "Clarify": {
        "purpose": "它承接 Completeness 给出的缺失项，不重新定义表单，而是把缺口压缩成最小必要补问，再把补回来的信息送回 Form Planner 和 Completeness 复核。这样整个链路形成一个小闭环：只补真正缺的内容，补完后立即回到生成前检查。",
    },
    "GenPlanner": {
        "purpose": "它位于生成链的总控位置，接收完整表单、子类型标签和知识检索摘要，把每一章应该走的路径规划出来。这个规划随后交给 Router 逐章落地，因此它承担的是‘整份方案怎么分工生成’的职责，而不是直接写某一章正文。",
    },
    "Router": {
        "purpose": "它承接 GenPlanner 的章节级策略，把每一章送到 fill_only、select_and_fill、controlled_compose 或 derive_by_rules 之一。也就是说，GenPlanner 决定策略，Router 决定每一章到底去哪条执行通道，并把对应的输入上下文路由给具体执行节点。",
    },
    "FillOnly": {
        "purpose": "它从 Router 接收那些确定性最高、禁改边界最清晰的章节，直接结合表单字段和模板片段交给 GenerationEngine 生成，再把结果返回给 Assembler。它在整体链路中的作用，是把最稳定的章节从 LLM 自由改写链路中剥离出来，保证核心模板内容不漂移。",
    },
    "SelectFill": {
        "purpose": "它承接 Router 分来的半确定性章节，从 KnowledgeStore 检索到适合当前子类型和工况的真实段落候选，再把项目参数嵌入这些候选段并交给 Assembler。它位于纯模板和开放补写之间，负责把‘真实可复用段落’真正落到当前方案中。",
    },
    "Compose": {
        "purpose": "它处理 Router 分来的受控开放写作章节，上游会给它模板风格、检索段落、项目参数和禁改要求，它再调用 LLMClient 补写出一版仍受边界约束的正文并交给 Assembler。它的作用不是替代前两条路径，而是在模板和候选段不足时补上必要的叙述空间。",
    },
    "DeriveRules": {
        "purpose": "它承接 Router 分来的规则驱动章节或段落，读取 KnowledgeStore 中的规则条件，再根据当前项目参数推导出必须出现的措施、限制和检查点，之后把这些结果交给 Assembler。它的存在让某些内容来源于‘参数触发规则’，而不是来源于历史措辞回忆。",
    },
    "Assembler": {
        "purpose": "它接收四条生成支路返回的章节结果，把它们按目录结构、编号顺序、表格位置和基本格式重新装配成完整文档，然后把成稿送入 Context Agent。也就是说，它是多策略生成结果进入统一方案正文的汇合点。",
    },
    "Context": {
        "purpose": "它承接 Assembler 给出的整体成稿，把其中已经确认的术语、摘要、引用关系和关键事实写入 GenerationContext，再把这份跨章节上下文交给 Consistency Agent。这样后续一致性检查和修订不会只看单章，而能看到整份方案的状态。",
    },
    "Consistency": {
        "purpose": "它接在 Context 后面，利用上下文状态检查整份方案前后是否一致，再把一致性结论送给 Compliance Agent。它在流程中的作用，是先把跨章节事实和术语统一性校正清楚，再进入基于规则的正式审核，避免 Compliance 一边查规则一边还要承担全局对账。",
    },
    "Compliance": {
        "purpose": "它承接 Consistency 之后的成稿与上下文，调用 AuditEngine 和 KnowledgeStore 中的规则/证据进行结构化审核，再把问题清单送给 Pass。这个节点让系统输出的不只是‘看起来不错’，而是可以继续流向修订闭环的明确审核结果。",
    },
    "Pass": {
        "purpose": "它接收 Compliance 的审核结果，决定当前文档是直接进入 Output 还是回到 RevisionPlanner。换句话说，它把审核链路和修订链路连接起来，是从‘检查出结果’转入‘是否继续流转’的分流点。",
    },
    "RevisionPlanner": {
        "purpose": "它承接 Pass 判定为未通过的方案，把 Compliance 输出的问题清单拆成具体修订任务，再把这些任务派给 Revision Agent。这样下游 Revision 改的是清晰范围和明确问题，而不是重新面对一整份含糊的审核报告。",
    },
    "Revision": {
        "purpose": "它根据 RevisionPlanner 给出的任务，只修改命中的章节或段落，改完后把新版本重新送回 Consistency 复查。也就是说，它不是另起一轮生成，而是审核闭环中的定向修复执行者。",
    },
    "Output": {
        "purpose": "它承接 Pass 放行后的最终方案，把正文、审核结果、变更记录和证据链整理成可交付输出。它位于整条运行链的最右端，把前面生成、审核、修订形成的所有结果固化为可以下载、归档和继续流转的交付物。",
    },
    "LLMClient": {
        "purpose": "它是运行期的模型调用接口，当前图里主要支撑 controlled_compose，必要时也可扩展给 Clarify、Revision 等节点使用。上游 Agent 只负责判断何时需要模型能力，真正的模型请求、超时和 provider 适配由它统一承接。",
    },
    "KnowledgeStore": {
        "purpose": "它在运行期为 SelectFill、DeriveRules 等节点提供知识检索入口，把字段槽、候选段、审核规则和证据索引统一返回给调用方。对上游节点来说，它承担的是‘按当前章节和工况拿知识’的角色，而不是再暴露底层多库结构。",
    },
    "GenerationEngine": {
        "purpose": "它位于 FillOnly 这条确定性链路下方，负责把模板、字段和结构化上下文稳定渲染成章节文本。部分 SelectFill 也可以借它把选中的真实段落和参数拼成结果，因此它是运行期生成链中的模板执行器。",
    },
    "GenerationContext": {
        "purpose": "它为 Context Agent 提供稳定的跨章状态载体，把摘要、术语、引用和已确认事实保存下来，再供 Consistency、Revision 等后续节点继续读取。它不单独做判断，但在整条链路里承担‘把局部结果沉淀成全局状态’的基础作用。",
    },
    "AuditEngine": {
        "purpose": "它在 Compliance 节点下方执行具体审核检查点，把文档内容与规则条件比对后产出结构化问题、证据和建议。上游 Compliance 决定查什么、何时查；它负责把审核真正跑出来并生成可被 Pass 和 RevisionPlanner 消化的结果。",
    },
}


KNOWLEDGE_CARDS = apply_card_overrides(KNOWLEDGE_CARDS, KNOWLEDGE_CARD_OVERRIDES)
AGENT_CARDS = apply_card_overrides(AGENT_CARDS, AGENT_CARD_OVERRIDES)
KNOWLEDGE_CARDS = apply_card_overrides(KNOWLEDGE_CARDS, KNOWLEDGE_ROLE_REFINEMENTS)
AGENT_CARDS = apply_card_overrides(AGENT_CARDS, AGENT_ROLE_REFINEMENTS)

KNOWLEDGE_CARDS.extend(
    [
        card(
            "TemplateCurator",
            "Template Curator",
            "Agentic 模板整理节点",
            "是",
            "知识识别",
            "把固定模板骨架、禁改章节和章节结构规则从段落资产里单独抽出来。",
            "它与 Passage Curator 并列，但职责不同：Passage Curator 整理可复用段落，Template Curator 固定章节骨架和改写边界。Generation Planner 只有同时拿到模板资产和段落资产，才能稳定区分 fill_only 与受控补写。",
            ["带标签的章节结构", "固定模板文本", "章节规则"],
            ["章节骨架", "禁改标记", "章节结构规则", "模板版本"],
            "如果不单独建这一层，固定模板与可选段落会混在一起，规划器很难稳定划清策略边界。",
            graph_role="agent node",
            phase_scope="终态知识层",
            upstream=["Taxonomy"],
            downstream=["TemplateStore"],
            future_link="这是对齐完整 planning 新增的关键节点，用来显式承接“模板固定内容”这类资产。",
        ),
        card(
            "TemplateStore",
            "Template Store",
            "专题知识资产",
            "否",
            "专题知识资产",
            "集中保存固定模板骨架、禁改规则和章节结构约束。",
            "它承接 Template Curator 的输出，给运行期的 Generation Planner 和 fill_only 提供明确模板边界。只有把模板资产和段落资产分开，系统才能稳定表达“这一章只能填空”和“这一章可以受控补写”的差异。",
            ["章节骨架", "禁改标记", "章节结构规则"],
            ["模板版本", "章节约束", "rewrite_allowed 标记"],
            "模板资产不是段落拼盘；它承担的是结构稳定与改写边界控制。",
            graph_role="knowledge asset",
            phase_scope="终态知识层",
            upstream=["TemplateCurator"],
            downstream=["KnowledgeStore"],
            future_link="这是本轮知识图新增的显式资产层，用来对齐完整 planning 中的模板固定内容。",
        ),
    ]
)

KNOWLEDGE_CARD_METADATA = {
    "Raw": {
        "graph_role": "knowledge asset",
        "phase_scope": "终态知识层",
        "upstream": [],
        "downstream": ["RawParser"],
        "future_link": "终态下，外部提交施工方案的审核链会重新读取这一层，而不是只依赖 Processed。",
    },
    "Processed": {
        "graph_role": "knowledge asset",
        "phase_scope": "终态知识层",
        "summary": "Formal_Version_Data_Processed 是统一章节树输入，已经拆成 text/table/image 内容块。",
        "purpose": "它和 Raw 一起进入知识构建，但承担不同角色：Raw 负责证据底座，Processed 负责主建库输入。后面的 SlotMiner、PassageCurator、TemplateCurator 和 RuleExtractor 都主要围绕这一层提取结构化资产，因此运行期模板、段落、参数槽和规则资产都间接来自这里。",
        "notes": "这里的子类型不是互斥分类；同一文档可以挂多个 subtype 标签，不能把目录名当成唯一类型。",
        "upstream": [],
        "downstream": ["Normalizer"],
        "future_link": "这是终态知识层的主语料底座，服务编制、审核以及后续动态管控的知识复用。",
    },
    "TaskBook": {
        "graph_role": "knowledge asset",
        "phase_scope": "终态知识层",
        "purpose": "它不是普通背景材料，而是整个系统的边界定义。它向 RuleExtractor 明确哪些内容必须参数化、哪些措施必须检查、哪些章节允许人工补充，并给运行期的 Generation Planner 和 Compliance 提供同一套判断口径。",
        "notes": "如果没有这一层，系统会退化成只有 prompt 风格的写作器，而不是受控的工程文档系统。",
        "upstream": [],
        "downstream": ["RuleExtractor"],
        "future_link": "终态里，任务书的约束会继续影响动态管控和现场协同的检查点生成，只是本轮不把这些节点画进主图。",
    },
    "RawParser": {
        "graph_role": "agent node",
        "phase_scope": "终态知识层",
        "upstream": ["Raw"],
        "downstream": ["Normalizer"],
        "future_link": "终态下，外部方案审核、证据追溯和附件对照都依赖这一层保留下来的原始提取结果。",
    },
    "Normalizer": {
        "graph_role": "pipeline node",
        "phase_scope": "终态知识层",
        "upstream": ["RawParser", "Processed"],
        "downstream": ["Chunker"],
        "future_link": "统一模型是后续知识持续扩充的基础，否则每接一批新数据都要重写抽取链。",
    },
    "Chunker": {
        "graph_role": "pipeline node",
        "phase_scope": "终态知识层",
        "upstream": ["Normalizer"],
        "downstream": ["Taxonomy"],
        "notes": "去重时不能丢掉多标签归属；同一文档出现在多个子类型目录中时，应保留所有 subtype 关联。",
        "future_link": "这一层决定知识库能否同时支持模板骨架、段落候选、规则片段和证据索引的细粒度复用。",
    },
    "Taxonomy": {
        "name": "Subtype + Scene Tagger",
        "graph_role": "agent node",
        "phase_scope": "终态知识层",
        "summary": "为切片内容打上多标签子类型、工况、章节角色和风险场景标签。",
        "purpose": "它接在 Chunker 之后，把片段从“通用文本块”转成运行期可路由的知识单元。SlotMiner、PassageCurator、TemplateCurator、RuleExtractor 和 EvidenceLinker 都依赖这些标签；而 Generation Planner、Chapter Router 和 Compliance 能否精准检索，也取决于这一步是否把基础、架线、跨越、立塔、消缺和工况维度标对。",
        "notes": "这里必须显式支持 multi-label subtype，不能退回一文档一类型的单标签假设。",
        "upstream": ["Chunker"],
        "downstream": ["SlotMiner", "PassageCurator", "TemplateCurator", "RuleExtractor", "EvidenceLinker"],
        "future_link": "终态下，动态管控阶段的检查表和异常识别也会复用这里的工况和风险标签体系。",
    },
    "SlotMiner": {
        "graph_role": "agent node",
        "phase_scope": "终态知识层",
        "upstream": ["Taxonomy"],
        "downstream": ["SlotStore"],
        "future_link": "终态下，现场协同和结构化审核摘要表也会复用这些字段槽。",
    },
    "PassageCurator": {
        "graph_role": "agent node",
        "phase_scope": "终态知识层",
        "summary": "把真实方案中的可复用段落整理成候选素材库。",
        "purpose": "它承接 Taxonomy 的多标签片段，识别哪些段落适合作为预置可选段、哪些段落只允许在特定工况下复用，再写入 PassageStore。运行期的 select_and_fill 和 controlled_compose 之所以能保持行业口吻，不是因为模型自己会写，而是因为这里先把真实表述资产化了。",
        "notes": "它服务开放式写作，但不等于鼓励自由生成；重点是把真实段落变成受控素材。",
        "upstream": ["Taxonomy"],
        "downstream": ["PassageStore"],
        "future_link": "终态里，这一层将直接影响不同模板变体、不同子类型和不同工况下的写作风格与可选表达范围。",
    },
    "RuleExtractor": {
        "graph_role": "agent node",
        "phase_scope": "终态知识层",
        "purpose": "它一端接收 TaskBook 和规范，另一端接收带标签的真实方案片段，把二者压成可执行的风险触发条件、必备措施和审核检查点，再写入 RuleStore。这样运行期的 derive_by_rules 和 Compliance 不用各自重新理解规范。",
        "notes": "抽取的不是泛泛的安全提醒，而是与子类型、工况和参数绑定的可执行规则。",
        "upstream": ["TaskBook", "Taxonomy"],
        "downstream": ["RuleStore"],
        "future_link": "终态下，现场监督检查表和异常提示也会复用这里的检查点资产，只是本轮不把 تلك阶段画进主图。",
    },
    "EvidenceLinker": {
        "graph_role": "pipeline node",
        "phase_scope": "终态知识层",
        "upstream": ["Taxonomy"],
        "downstream": ["EvidenceStore"],
        "future_link": "终态里，所有审核结论和后续现场差异提示都需要能回到这一层给出的证据索引。",
    },
    "SlotStore": {
        "graph_role": "knowledge asset",
        "phase_scope": "终态知识层",
        "upstream": ["SlotMiner"],
        "downstream": ["KnowledgeStore"],
        "future_link": "终态下，这里的字段槽还会继续服务现场数据映射与差异比对。",
    },
    "PassageStore": {
        "graph_role": "knowledge asset",
        "phase_scope": "终态知识层",
        "upstream": ["PassageCurator"],
        "downstream": ["KnowledgeStore"],
        "future_link": "终态下，不同模板变体和不同子类型会共享这套段落资产，但以不同条件过滤和不同风格边界使用。",
    },
    "RuleStore": {
        "graph_role": "knowledge asset",
        "phase_scope": "终态知识层",
        "purpose": "它承接 RuleExtractor 的结果，为运行期的 derive_by_rules 和 Compliance 提供同一套规则资产。这样生成链和审核链共享同一规则底座，不会一边写措施一边又按另一套口径审。",
        "upstream": ["RuleExtractor"],
        "downstream": ["KnowledgeStore"],
        "future_link": "终态下，这里的检查点还能继续下游复用为现场核查表和异常提示依据。",
    },
    "EvidenceStore": {
        "graph_role": "knowledge asset",
        "phase_scope": "终态知识层",
        "upstream": ["EvidenceLinker"],
        "downstream": ["KnowledgeStore"],
        "future_link": "终态里，所有结构化审核报告和后续现场协同输出都要依赖这里保留下来的追溯关系。",
    },
    "KnowledgeStore": {
        "graph_role": "SDK tool",
        "phase_scope": "终态基础能力",
        "summary": "作为统一检索入口，把参数槽、模板、段落、规则和证据资产屏蔽在单一运行期接口后面。",
        "purpose": "它站在各类知识资产之上，给运行期的 Generation Planner、Chapter Router、select_and_fill、derive_by_rules 和 Compliance 提供统一检索入口。上层节点不需要知道底层是字段库、模板库、段落库还是规则库，只需要按子类型、工况、章节和查询目标取回受控资产。",
        "notes": "它是 SDK 工具，不是 Agent；规划与判断仍由上层节点负责。",
        "upstream": ["SlotStore", "PassageStore", "TemplateStore", "RuleStore", "EvidenceStore"],
        "downstream": ["Governance"],
        "future_link": "终态下，它仍是知识层唯一对外运行入口，动态管控和现场协同阶段也会复用这条入口。",
    },
    "Governance": {
        "graph_role": "governance node",
        "phase_scope": "终态基础能力",
        "summary": "记录知识版本、人工确认状态和上线边界。",
        "purpose": "它位于知识层出库之后，负责控制哪些资产已审核、哪些仍是草稿、哪些版本可供运行期调用。这样系统才能在多人持续补充 Raw/Processed 数据时保持可审计、可回滚、可追责。",
        "notes": "它通常不参与运行期热路径，但决定知识层能否长期可维护。",
        "upstream": ["KnowledgeStore"],
        "downstream": [],
        "future_link": "终态里，治理层会同时约束编制、审核和后续现场协同阶段可使用的知识版本。",
    },
}

AGENT_CARD_METADATA = {
    "Start": {
        "name": "Start Request",
        "graph_role": "entry node",
        "phase_scope": "当前主图",
        "purpose": "它把用户发起的工程编制任务从普通聊天请求切换成工程文档任务，统一携带工程类型、项目资料、人工补充要求和已知参数。随后 Intake Agent 才能接管并做正式的需求归一化。",
        "upstream": [],
        "downstream": ["Intake"],
        "future_link": "终态下，发布后回流的修订任务或现场反馈也会重新汇聚到统一任务入口，但本轮不画这些支路。",
    },
    "Intake": {
        "graph_role": "agent node",
        "phase_scope": "当前主图",
        "upstream": ["Start"],
        "downstream": ["Classifier"],
        "future_link": "终态下，外部方案审核或现场异常回流时，也会先经过这一层做任务归一化，只是目标不一定是生成正文。",
    },
    "Classifier": {
        "name": "Subtype + Scene Classifier",
        "graph_role": "agent node",
        "phase_scope": "当前主图 / 终态基础能力",
        "summary": "识别多标签子类型与关键工况，不再是假定一文档只对应一个单标签类型。",
        "purpose": "它接在 Intake 后面，把标准化任务摘要映射到基础、架线、跨越、立塔、消缺等 subtype 标签，并继续提取工况和风险场景标签。Form Planner 会据此决定该问哪些字段，Generation Planner 会据此限定模板/段落/规则检索范围，Compliance 也会据此加载更准确的审核口径。",
        "notes": "分类结果必须允许人工覆盖；工程资料不完整时，系统不能假装单标签分类绝对正确。",
        "upstream": ["Intake"],
        "downstream": ["FormPlanner"],
        "future_link": "终态下，这套 subtype + scene 标签还会继续服务检查表生成和现场差异识别，只是这些节点不进本轮主图。",
    },
    "FormPlanner": {
        "graph_role": "agent node",
        "phase_scope": "当前主图",
        "purpose": "它承接 Classifier 的 subtype 和工况标签，再结合 KnowledgeStore 中的字段槽与模板约束，生成真正面向前端的字段分组、必填项、可选项和可编辑表格。Completeness 会以这份 schema 为准做缺口判断，因此它处在知识字段与用户填写体验之间的转换层。",
        "upstream": ["Classifier", "Clarify"],
        "downstream": ["Completeness"],
        "future_link": "终态下，外部文档解析出的结构化信息也会尽量落回这套字段 schema，便于统一审核。",
    },
    "Completeness": {
        "graph_role": "conditional gate",
        "phase_scope": "当前主图",
        "upstream": ["FormPlanner"],
        "downstream": ["Clarify", "GenPlanner"],
    },
    "Clarify": {
        "graph_role": "agent node",
        "phase_scope": "当前主图",
        "upstream": ["Completeness"],
        "downstream": ["FormPlanner"],
        "future_link": "终态下，Revision 或现场差异回流时也可能复用这种最小补问模式，但本轮不扩展到那些流程。",
    },
    "GenPlanner": {
        "graph_role": "agent node",
        "phase_scope": "当前主图 / 终态基础能力",
        "summary": "为每一章决定采用哪种生成模式，并明确知识依赖和改写边界。",
        "purpose": "它位于生成层总控位置，承接完整表单、subtype/scene 标签和 KnowledgeStore 返回的模板、段落、规则、证据摘要。随后它把每章应该走 fill_only、select_and_fill、controlled_compose 还是 derive_by_rules 的决策交给 Router 落地，因此它负责的是全局章节策略，而不是直接生成某章正文。",
        "notes": "它是规划节点，不是写作节点；其价值在于明确章级边界，而不是把整篇交给一个大 prompt。",
        "upstream": ["Completeness", "KnowledgeStore"],
        "downstream": ["Router"],
        "future_link": "终态下，它还会为发布后的修订、摘要表生成和检查点下游复用提供章节级策略基础。",
    },
    "Router": {
        "graph_role": "router node",
        "phase_scope": "当前主图",
        "purpose": "它承接规划器给出的章级策略，不再重新做上游判断，而是把每一章发往 fill_only、select_and_fill、controlled_compose 或 derive_by_rules。这样规划和执行分层清晰，LangGraph 视角下也能区分“决策节点”和“执行节点”。",
        "upstream": ["GenPlanner"],
        "downstream": ["FillOnly", "SelectFill", "Compose", "DeriveRules"],
    },
    "FillOnly": {
        "graph_role": "strategy executor",
        "phase_scope": "当前主图",
        "summary": "对高稳定、禁改边界明确的章节做纯模板填空。",
        "purpose": "它承接 Router 分来的强模板章节，结合 GenerationEngine 用模板、字段和表格数据直接生成结果，再交给 Assembler。这里的关键不是写得花，而是稳，因此像第三章这类只填空不改写的章节要明确走这条链。",
        "notes": "这是策略执行节点，不是 Agent；不接受运行期自由改写。",
        "upstream": ["Router", "GenerationEngine"],
        "downstream": ["Assembler"],
        "future_link": "终态下，更多审批页、固定附表和禁改章节仍会继续走这条确定性链路。",
    },
    "SelectFill": {
        "graph_role": "strategy executor",
        "phase_scope": "当前主图",
        "summary": "从可复用段落库中选出最合适的真实表达，再做参数注入。",
        "purpose": "它承接 Router 分来的半确定性章节，从 KnowledgeStore 中检索匹配当前 subtype、scene 和章节目标的段落候选，再把项目参数嵌入这些候选段交给 Assembler。它位于纯模板与受控开放写作之间，重点是用真实段落做选择，而不是自由改写。",
        "notes": "候选段落必须来自知识库并带证据链；它不是自由写作节点。",
        "upstream": ["Router", "KnowledgeStore"],
        "downstream": ["Assembler"],
        "future_link": "终态下，不同模板变体、不同子类型和不同工况会大量复用这条链路，因为它最能体现“真实段落复用”。",
    },
    "Compose": {
        "graph_role": "strategy executor",
        "phase_scope": "当前主图",
        "notes": "这是最接近开放式写作的节点，因此必须受模板、段落、参数和证据共同约束。",
        "upstream": ["Router", "LLMClient"],
        "downstream": ["Assembler"],
        "future_link": "终态下，人工补充要求和风格变体会主要在这条链路上体现，但仍不能突破模板和证据边界。",
    },
    "DeriveRules": {
        "graph_role": "strategy executor",
        "phase_scope": "当前主图",
        "summary": "根据参数和规则资产派生必须出现的风险措施、检查点和说明。",
        "purpose": "它承接 Router 分来的规则驱动章节或段落，从 KnowledgeStore 读取 RuleStore 里的触发条件和检查点，再结合当前项目参数生成必须写出的措施说明，之后交给 Assembler。与 select_and_fill 不同，它的核心不是选段落，而是按规则推出必写内容。",
        "notes": "这条链的内容来源于规则触发，不是历史措辞回忆或自由写作。",
        "upstream": ["Router", "KnowledgeStore"],
        "downstream": ["Assembler"],
        "future_link": "终态下，Compliance 和现场检查表会继续复用同一规则资产，因此这条链是生成与审核之间的重要桥梁。",
    },
    "Assembler": {
        "graph_role": "strategy executor / deterministic assembler",
        "phase_scope": "当前主图",
        "upstream": ["FillOnly", "SelectFill", "Compose", "DeriveRules"],
        "downstream": ["Context"],
    },
    "Context": {
        "graph_role": "agent node",
        "phase_scope": "当前主图",
        "upstream": ["Assembler", "GenerationContext"],
        "downstream": ["Consistency"],
    },
    "Consistency": {
        "graph_role": "agent node",
        "phase_scope": "当前主图",
        "upstream": ["Context"],
        "downstream": ["Compliance"],
    },
    "Compliance": {
        "graph_role": "agent node",
        "phase_scope": "当前主图 / 终态基础能力",
        "summary": "调用规则、证据和审核引擎对整份方案做结构化合规检查。",
        "purpose": "它承接 Consistency 之后的草稿和上下文，结合 KnowledgeStore 提供的规则/证据以及 AuditEngine 的检查执行能力，输出明确的问题清单、证据和整改建议，再交给 Pass。它存在的意义不是给一个总分，而是把精准审核落成可复核、可修订的结构化结果。",
        "notes": "输出应便于 RevisionPlanner 消化，不能只停留在模糊评价。",
        "upstream": ["Consistency", "KnowledgeStore", "AuditEngine"],
        "downstream": ["Pass"],
        "future_link": "终态下，这里的检查点和结论还能下游复用为现场核查表与动态管控提示，但这些节点本轮不进入主图。",
    },
    "Pass": {
        "graph_role": "conditional gate",
        "phase_scope": "当前主图",
        "upstream": ["Compliance"],
        "downstream": ["RevisionPlanner", "Output"],
    },
    "RevisionPlanner": {
        "graph_role": "agent node",
        "phase_scope": "当前主图",
        "upstream": ["Pass"],
        "downstream": ["Revision"],
    },
    "Revision": {
        "graph_role": "agent node",
        "phase_scope": "当前主图",
        "upstream": ["RevisionPlanner"],
        "downstream": ["Consistency"],
    },
    "Output": {
        "graph_role": "output node",
        "phase_scope": "当前主图 / 终态下游复用",
        "summary": "把通过审核的方案正文、审核结果和追溯信息整理成可交付包。",
        "purpose": "它承接 Pass 放行后的定稿，把正文、审核报告、变更记录和证据链整理成可下载、可归档、可继续流转的交付结果。对当前主图来说这里是终点；对完整规划来说，这里也是发布、现场协同和动态管控的上游起点。",
        "notes": "当前主图止于这里，不展开发布后现场协同链路。",
        "upstream": ["Pass"],
        "downstream": [],
        "future_link": "终态下游：发布、现场协同、检查表生成、动态管控和异常回流都从这里接续展开，但本轮主图不把这些节点画出来。",
    },
    "LLMClient": {
        "graph_role": "SDK tool",
        "phase_scope": "终态基础能力",
        "upstream": [],
        "downstream": ["Compose"],
    },
    "KnowledgeStore": {
        "graph_role": "SDK tool",
        "phase_scope": "当前主图 / 终态基础能力",
        "summary": "运行期统一检索模板、段落、规则和证据。",
        "purpose": "它在当前主图里显式支撑 Generation Planner、select_and_fill、derive_by_rules 和 Compliance。这样读图的人可以直接看出：规划、生成和审核都不是各自维护一套知识，而是共享同一个运行期知识入口。",
        "notes": "它是 SDK 工具，不是 LangGraph 里的 Agent 节点；它提供知识，不做决策。",
        "upstream": [],
        "downstream": ["GenPlanner", "SelectFill", "DeriveRules", "Compliance"],
        "future_link": "终态下，发布后的检查表生成和现场协同也会继续复用同一个运行期知识入口。",
    },
    "GenerationEngine": {
        "graph_role": "SDK tool",
        "phase_scope": "终态基础能力",
        "upstream": [],
        "downstream": ["FillOnly"],
    },
    "GenerationContext": {
        "graph_role": "SDK tool",
        "phase_scope": "终态基础能力",
        "upstream": [],
        "downstream": ["Context"],
    },
    "AuditEngine": {
        "graph_role": "SDK tool",
        "phase_scope": "终态基础能力",
        "upstream": [],
        "downstream": ["Compliance"],
    },
}

KNOWLEDGE_CARDS = merge_card_metadata(KNOWLEDGE_CARDS, KNOWLEDGE_CARD_METADATA)
AGENT_CARDS = merge_card_metadata(AGENT_CARDS, AGENT_CARD_METADATA)
KNOWLEDGE_CARDS = filter_cards(KNOWLEDGE_CARDS, {"SDKTools"})

KNOWLEDGE_CARDS = merge_card_metadata(
    KNOWLEDGE_CARDS,
    {
        "KnowledgeStore": {
            "summary": "知识层的统一出库与检索接口，承接参数槽、模板、段落、规则和证据资产。",
            "purpose": "在知识构建图里，它不是普通流程下游 Agent，而是把 SlotStore、PassageStore、TemplateStore、RuleStore 和 EvidenceStore 封装成运行期可调用入口。图中连到 Governance 的关系表示版本、审核状态和上线边界的治理约束，不表示 KnowledgeStore 主动调用治理节点。",
            "notes": "读图时要把它理解成 SDK 工具入口：它被运行期 Planner、Router、策略执行器和 Compliance 检索使用；具体决策仍由 Agent 节点负责。",
            "future_link": "在 Agent 主链和后续动态管控阶段，KnowledgeStore 会继续作为统一知识入口被读取，但治理关系仍由 Governance 单独约束。",
        }
    },
)

AGENT_CARDS = merge_card_metadata(
    AGENT_CARDS,
    {
        "LLMClient": {
            "summary": "模型调用工具，当前主要被 controlled_compose 调用。",
            "purpose": "图中的虚线表示 Compose 在需要受控补写时调用 LLMClient。它不是 Compose 的流程上游，也不会主动驱动工作流；它只负责把 prompt、上下文和模型配置发送给模型并返回结果。",
            "notes": "是否调用模型、传入哪些约束、调用失败时如何回退，都由上层 Agent / 策略节点决定，不由 LLMClient 决定。",
        },
        "KnowledgeStore": {
            "summary": "运行期统一知识检索工具，被规划、生成策略和审核节点读取。",
            "purpose": "图中的虚线表示 Generation Planner、select_and_fill、derive_by_rules 和 Compliance 会按需检索 KnowledgeStore。它不是这些节点的流程上游，而是工具依赖：提供模板、段落、规则、参数槽和证据，不决定章节策略或审核结论。",
            "notes": "卡片中的“发挥作用的节点”表示调用方 / 读取方；真正的流程顺序仍看实线主链。",
        },
        "GenerationEngine": {
            "summary": "确定性模板渲染工具，被 fill_only 和部分 select_and_fill 路径调用。",
            "purpose": "图中的虚线表示 FillOnly 和 SelectFill 会调用 GenerationEngine 做模板渲染或段落填参。它不选择章节策略，也不判断哪些段落适用，只负责把已经确定的模板、字段和片段稳定渲染成正文。",
            "notes": "它是执行器，不是 Agent；适合高确定性章节和已选段落的稳定落版。",
            "downstream": ["FillOnly", "SelectFill"],
        },
        "GenerationContext": {
            "summary": "跨章状态工具，被 Context Agent 读写。",
            "purpose": "图中的虚线表示 Context Agent 会借助 GenerationContext 保存章节摘要、术语、引用关系和已确认事实。它不是 Context 的流程前置节点，而是 Context Agent 的状态载体。",
            "notes": "它提供状态存储和读取能力；一致性判断仍由 Context / Consistency 等上层节点完成。",
        },
        "AuditEngine": {
            "summary": "结构化审核执行工具，被 Compliance Agent 调用。",
            "purpose": "图中的虚线表示 Compliance Agent 会调用 AuditEngine 执行检查点。它不决定是否通过审核，也不负责修订；它把规则比对结果产出为结构化问题、证据和建议，供 Pass 和 RevisionPlanner 使用。",
            "notes": "它是审核执行器，不是审核决策 Agent。",
        },
    },
)


KNOWLEDGE_SCOPE_NOTE = (
    "知识页按终态知识层表达：重点说明 Raw / Processed 如何沉淀为参数槽、可复用段落、模板资产、规则资产和证据资产，"
    "并通过 KnowledgeStore 服务后续编制与审核。"
)

AGENT_SCOPE_NOTE = (
    "Agent 页当前只覆盖“编制 + 审核”主链；动态管控 / 现场协同不进入主图，"
    "但会在节点卡片与报告中标明与终态能力的衔接关系。"
)

KNOWLEDGE_LEGEND_ITEMS = [
    ("input", "输入资产"),
    ("agentic", "结构归一化 / 知识识别节点"),
    ("store", "专题知识资产"),
    ("sdk", "运行期入口 / 治理"),
]

AGENT_LEGEND_ITEMS = [
    ("input", "入口"),
    ("agentic", "Agent node"),
    ("strategy", "Strategy executor"),
    ("decision", "Conditional gate"),
    ("sdk", "SDK tool"),
    ("output", "Output"),
]

REPORT_TEMPLATE = """# 线路工程施工方案 Agent 架构图说明

本文档由 `scripts/render_agent_architecture.py` 生成，用于团队内部对齐当前 Agent 规划，不代表已进入实现阶段。

本地查看交互图时，优先打开：

- `knowledge_construction_interactive.html`
- `agent_runtime_interactive.html`

脚本会优先调用 Mermaid CLI 生成本地 SVG，并把 SVG 直接嵌入 HTML，避免浏览器端 Mermaid 渲染失败后只显示源码。

## 当前范围

- 知识页更接近终态知识层，已经显式补出 `Template Curator / Template Store`，并把多标签子类型与工况识别纳入主链。
- Agent 页当前只覆盖“编制 + 审核”主链，不把动态管控 / 现场协同画进主图；相关终态衔接通过卡片与本说明文档表达。

## 目标判断

结合任务计划书、Formal Version 数据和 SDK 工具层，系统目标不应被理解为“完全开放式自由写作”。更准确的目标是：围绕线路工程施工方案，把历史方案与规范沉淀为以下五类知识资产，再由 Agent 在受控边界内调用它们完成编制与审核：

- 模板固定内容
- 预置可选段落
- 关键参数槽
- 规则 / 风险检查点
- 证据索引

正式版数据中的五种子类型 `基础 / 架线 / 跨越 / 立塔 / 消缺` 应作为运行期和知识层的一等标签。`Formal_Version_Data_Processed` 更适合作为主建库输入，因为它已经整理成章节树 JSON，并区分 `text / table / image`；`Formal_Version_Data_Raw` 更适合作为证据底座、补充抽取源和外部审核输入源。

## 知识构建层

```mermaid
{knowledge_mermaid}
```

## Agent 主链

```mermaid
{agent_mermaid}
```
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def fix_svg_ids(svg: str, prefix: str) -> str:
    return svg.replace("my-svg", prefix)


def render_mermaid_svg(input_path: Path, output_path: Path, config_path: Path) -> bool:
    mmdc = shutil.which("mmdc")
    if mmdc:
        command = [mmdc, "-c", str(config_path), "-i", str(input_path), "-o", str(output_path), "-b", "transparent"]
    else:
        npx = shutil.which("npx")
        if not npx:
            return False
        command = [
            npx,
            "-y",
            "@mermaid-js/mermaid-cli",
            "-c",
            str(config_path),
            "-i",
            str(input_path),
            "-o",
            str(output_path),
            "-b",
            "transparent",
        ]
    try:
        subprocess.run(command, check=True, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Mermaid SVG render failed for {input_path.name}: {exc}")
        return output_path.exists()
    return output_path.exists()


def build_legend_html(items):
    return "".join(
        f'<span class="legend-item"><span class="legend-chip {css_class}"></span><span>{label}</span></span>'
        for css_class, label in items
    )


def build_html(
    title,
    subtitle,
    svg,
    mermaid_source,
    cards,
    default_node_id,
    other_page,
    other_label,
    initial_scale,
    scope_note,
    legend_items,
):
    cards_json = json.dumps(cards, ensure_ascii=False, indent=2)
    legend_html = build_legend_html(legend_items)
    graph_view = f'<div class="graph-canvas" id="graph-canvas">{svg}</div>' if svg else f'<pre class="graph-source">{mermaid_source}</pre>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg:#f7f3ea; --paper:#fffdf7; --ink:#1f2d2a; --muted:#63736d;
      --line:#deceaa; --accent:#587f6f; --agent:#d9ead3; --strategy:#eadcf8;
      --decision:#ddf4ff; --sdk:#efe6d2; --output:#ddefd5;
      --store:#ddebf7; --input:#fce4d6;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; background:radial-gradient(circle at top left,#fff7df 0,var(--bg) 42%,#f3efe5 100%);
      color:var(--ink); font-family:"Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",sans-serif;
    }}
    main {{ max-width:1680px; margin:0 auto; padding:30px 26px 42px; }}
    header {{ display:flex; justify-content:space-between; gap:22px; align-items:flex-start; margin-bottom:18px; }}
    h1 {{ margin:0 0 8px; font-size:30px; letter-spacing:.02em; }}
    p {{ margin:0; color:var(--muted); line-height:1.75; }}
    a {{ color:var(--accent); font-weight:700; text-decoration:none; }}
    .page-link {{ flex:0 0 auto; border:1px solid var(--line); border-radius:999px; padding:9px 14px; background:#fffaf0; }}
    .layout {{ display:grid; grid-template-columns:minmax(0,1fr) 420px; gap:18px; align-items:start; }}
    .graph-panel,.detail-panel {{ background:color-mix(in srgb,var(--paper) 94%,white); border:1px solid var(--line); border-radius:22px; box-shadow:0 18px 50px rgb(58 47 26 / 10%); }}
    .graph-panel {{ padding:16px; min-width:0; }}
    .toolbar {{ display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap; }}
    .tool-button {{ border:1px solid var(--line); border-radius:12px; background:#fff8e8; color:var(--ink); padding:8px 11px; cursor:pointer; font-weight:700; }}
    .zoom-readout {{ color:var(--accent); font-weight:800; min-width:52px; text-align:right; margin-left:auto; }}
    .scope-note {{ margin:0 0 12px; padding:12px 14px; border:1px solid #e7d8b6; border-radius:16px; background:#fff7ea; color:#365148; font-weight:700; line-height:1.7; }}
    .legend {{ display:flex; flex-wrap:wrap; gap:10px 14px; margin:0 0 14px; padding:10px 12px; border:1px solid #eadbb8; border-radius:16px; background:#fffaf0; }}
    .legend-item {{ display:inline-flex; align-items:center; gap:8px; color:var(--muted); font-size:13px; }}
    .legend-chip {{ width:12px; height:12px; border-radius:999px; border:1px solid rgb(0 0 0 / 16%); display:inline-block; }}
    .legend-chip.agentic {{ background:var(--agent); }} .legend-chip.strategy {{ background:var(--strategy); }}
    .legend-chip.decision {{ background:var(--decision); }} .legend-chip.sdk {{ background:var(--sdk); }}
    .legend-chip.output {{ background:var(--output); }}
    .legend-chip.input {{ background:var(--input); }} .legend-chip.store {{ background:var(--store); }}
    .graph-window {{ position:relative; height:76vh; min-height:620px; overflow:hidden; border:1px solid #e7d8b6; border-radius:18px; background:linear-gradient(180deg,#fffdf6,#f8f1df); cursor:grab; touch-action:none; }}
    .graph-window.is-dragging {{ cursor:grabbing; }}
    .graph-canvas {{ position:absolute; left:0; top:0; transform-origin:0 0; will-change:transform; min-width:320px; min-height:320px; }}
    .graph-canvas svg {{ display:block; width:1200px; height:auto; max-width:none!important; background:transparent!important; font-family:"Microsoft YaHei","SimHei","Noto Sans CJK SC",sans-serif!important; }}
    .graph-canvas svg text,.graph-canvas svg tspan,.graph-canvas svg foreignObject div,.graph-canvas svg foreignObject span {{
      font-family:"Microsoft YaHei","SimHei","Noto Sans CJK SC",sans-serif!important; line-height:1.18!important;
    }}
    .graph-canvas svg .node {{ cursor:pointer; }}
    .graph-canvas svg .node:hover rect,.graph-canvas svg .node:hover polygon,.graph-canvas svg .node:hover path {{
      stroke:#8c6d2d!important; stroke-width:2.4px!important;
    }}
    .graph-canvas svg .node.adjacent-node rect,.graph-canvas svg .node.adjacent-node polygon,.graph-canvas svg .node.adjacent-node path {{
      filter:none;
    }}
    .graph-canvas svg [data-edge="true"].adjacent-edge {{
      stroke-width:4px!important; opacity:1!important;
    }}
    .graph-canvas svg [data-edge="true"].adjacent-sdk-edge {{
      stroke-width:4px!important; opacity:1!important;
    }}
    .graph-canvas svg .node.selected-node rect,.graph-canvas svg .node.selected-node polygon,.graph-canvas svg .node.selected-node path {{
      stroke:#c44f35!important; stroke-width:3px!important; filter:drop-shadow(0 0 5px rgb(196 79 53 / 30%));
    }}
    .graph-canvas svg .node-highlight-ring {{ pointer-events:none; fill:none!important; vector-effect:non-scaling-stroke; }}
    .graph-source {{ padding:18px; overflow:auto; white-space:pre; background:#fff7e8; border-radius:16px; border:1px dashed var(--line); }}
    .detail-panel {{ position:sticky; top:18px; padding:20px; min-height:620px; max-height:86vh; overflow-y:auto; overflow-x:hidden; scrollbar-gutter:stable; }}
    .detail-panel h2 {{ margin:0 0 10px; font-size:23px; }}
    .badge-row {{ display:flex; flex-wrap:wrap; gap:7px; margin-bottom:16px; }}
    .badge {{ display:inline-flex; align-items:center; border-radius:999px; padding:4px 9px; font-size:12px; border:1px solid rgb(0 0 0 / 10%); background:#f3efe5; color:var(--ink); }}
    .badge.agentic {{ background:var(--agent); }} .badge.strategy {{ background:var(--strategy); }}
    .badge.decision {{ background:var(--decision); }} .badge.sdk {{ background:var(--sdk); }}
    .badge.output {{ background:var(--output); }}
    .badge.input {{ background:var(--input); }} .badge.store {{ background:var(--store); }}
    .detail-panel h3 {{ margin:18px 0 8px; color:var(--accent); font-size:15px; }}
    .detail-panel ul {{ margin:0; padding-left:20px; line-height:1.75; }}
    .detail-panel p {{ color:var(--ink); }}
    .node-ref-list {{ list-style:none; padding-left:0!important; display:flex; flex-wrap:wrap; gap:8px; line-height:1.2!important; }}
    .node-ref-list li {{ margin:0; padding:0; }}
    .node-ref {{ border:1px solid rgb(0 0 0 / 14%); border-radius:999px; color:var(--ink); cursor:pointer; font:inherit; font-size:13px; font-weight:700; padding:6px 10px; box-shadow:0 6px 14px rgb(58 47 26 / 8%); }}
    .node-ref:hover {{ outline:2px solid #ff8a00; outline-offset:2px; }}
    .node-ref.agentic {{ background:var(--agent); }} .node-ref.strategy {{ background:var(--strategy); }}
    .node-ref.decision {{ background:var(--decision); }} .node-ref.sdk {{ background:var(--sdk); }}
    .node-ref.output {{ background:var(--output); }}
    .node-ref.input {{ background:var(--input); }} .node-ref.store {{ background:var(--store); }}
    .empty-note {{ color:var(--muted)!important; font-style:italic; }}
    .hint {{ color:var(--accent); font-weight:700; margin:0 0 12px; }}
    @media (max-width:1100px) {{
      .layout {{ grid-template-columns:1fr; }} .detail-panel {{ position:static; min-height:auto; }}
      .toolbar {{ display:flex; }}
      header {{ display:block; }} .page-link {{ display:inline-flex; margin-top:12px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>{title}</h1><p>{subtitle}</p></div>
      <a class="page-link" href="{other_page}">{other_label}</a>
    </header>
    <div class="layout">
      <section class="graph-panel">
        <div class="toolbar">
          <button class="tool-button" id="zoom-out">-</button>
          <button class="tool-button" id="zoom-in">+</button>
          <button class="tool-button" id="reset-view">重置</button>
          <span class="zoom-readout" id="zoom-readout"></span>
        </div>
        <div class="scope-note">{scope_note}</div>
        <div class="legend" aria-label="图例">{legend_html}</div>
        <p class="hint">点击节点更新右侧卡片；滚轮或键盘 +/- 缩放；按住图框拖拽只移动观察位置，不改变缩放比例。</p>
        <div class="graph-window" id="graph-window">{graph_view}</div>
      </section>
      <aside class="detail-panel" id="node-detail"></aside>
    </div>
  </main>
  <script>
    const nodeCards = {cards_json};
    const nodeMap = new Map(nodeCards.map((item) => [item.id, item]));
    const defaultNodeId = "{default_node_id}";
    let scale = {initial_scale};
    const minScale = 0.25, maxScale = 1.45;
    const graphWindow = document.getElementById("graph-window");
    const graphCanvas = document.getElementById("graph-canvas");
    const zoomReadout = document.getElementById("zoom-readout");
    const detail = document.getElementById("node-detail");
    let pan = {{ x: null, y: null }};
    let dragState = null;
    let suppressNodeClick = false;
    let graphLookup = new Map();
    const html = (value) => String(value).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
    const badgeClass = (card) => {{
      const role = String(card.graph_role || card.type || "").toLowerCase();
      if (role.includes("sdk")) return "sdk";
      if (role.includes("strategy")) return "strategy";
      if (role.includes("conditional")) return "decision";
      if (role.includes("knowledge")) return "store";
      if (role.includes("input")) return "input";
      if (role.includes("output")) return "output";
      if (String(card.type || "").includes("决策")) return "decision";
      return "agentic";
    }};
    function listItems(items) {{
      if (!items || !items.length) return '<p class="empty-note">无</p>';
      return "<ul>" + items.map((item) => "<li>" + html(item) + "</li>").join("") + "</ul>";
    }}
    function nodeRefLabel(nodeId) {{
      const ref = nodeMap.get(nodeId);
      return ref ? ref.name : String(nodeId);
    }}
    function nodeRefClass(nodeId) {{
      const ref = nodeMap.get(nodeId);
      return ref ? badgeClass(ref) : "agentic";
    }}
    function edgeColorForNode(nodeId) {{
      const palette = {{
        input:"#B76E4C",
        agentic:"#6A8F63",
        strategy:"#8B67A6",
        decision:"#2F80A8",
        sdk:"#9A825A",
        output:"#6A8F63",
        store:"#5B8DB0"
      }};
      return palette[nodeRefClass(nodeId)] || "#6A8F63";
    }}
    function glowForColor(color) {{
      const normalized = String(color || "").trim();
      const rgba = {{
        "#B76E4C":"rgba(183,110,76,.78)",
        "#6A8F63":"rgba(106,143,99,.78)",
        "#8B67A6":"rgba(139,103,166,.78)",
        "#2F80A8":"rgba(47,128,168,.82)",
        "#9A825A":"rgba(154,130,90,.82)",
        "#5B8DB0":"rgba(91,141,176,.82)"
      }};
      return rgba[normalized] || "rgba(106,143,99,.78)";
    }}
    function isSdkTool(nodeId) {{
      const ref = nodeMap.get(nodeId);
      if (!ref) return false;
      const role = String(ref.graph_role || "").toLowerCase();
      const type = String(ref.type || "").toLowerCase();
      return role.includes("sdk") || type.includes("sdk");
    }}
    function isGovernanceNode(nodeId) {{
      const ref = nodeMap.get(nodeId);
      if (!ref) return false;
      const role = String(ref.graph_role || "").toLowerCase();
      const type = String(ref.type || "");
      return role.includes("governance") || type.includes("治理");
    }}
    function nodeRefItems(items) {{
      if (!items || !items.length) return '<p class="empty-note">无</p>';
      return '<ul class="node-ref-list">' + items.map((item) =>
        '<li><button type="button" class="node-ref ' + nodeRefClass(item) + '" data-node-ref="' + html(item) + '">' + html(nodeRefLabel(item)) + '</button></li>'
      ).join("") + "</ul>";
    }}
    function optionalNodeRefSection(title, items) {{
      return items && items.length ? section(title, nodeRefItems(items)) : "";
    }}
    function graphNeighborIds(nodeId, direction) {{
      const entry = graphLookup.get(nodeId);
      if (!entry) return [];
      const links = direction === "upstream" ? entry.incoming : entry.outgoing;
      return links.map((link) => link.nodeId);
    }}
    function mergeNodeRefs(primary, secondary) {{
      const merged = [];
      [...(primary || []), ...(secondary || [])].forEach((nodeId) => {{
        if (nodeId && !merged.includes(nodeId)) merged.push(nodeId);
      }});
      return merged;
    }}
    function textBlock(value) {{
      if (!value) return '<p class="empty-note">无</p>';
      return "<p>" + html(value) + "</p>";
    }}
    function section(title, content) {{
      return "<h3>" + html(title) + "</h3>" + content;
    }}
    function renderDetail(card) {{
      const upstreamRefs = mergeNodeRefs(graphNeighborIds(card.id, "upstream"), card.upstream);
      const sdkDependencyRefs = upstreamRefs.filter((nodeId) => isSdkTool(nodeId));
      const ordinaryUpstreamRefs = upstreamRefs.filter((nodeId) => !isSdkTool(nodeId));
      const downstreamRefs = mergeNodeRefs(graphNeighborIds(card.id, "downstream"), card.downstream);
      const toolInputRefs = upstreamRefs.filter((nodeId) => !isSdkTool(nodeId));
      const toolGovernanceRefs = downstreamRefs.filter((nodeId) => isGovernanceNode(nodeId));
      const toolConsumerRefs = downstreamRefs.filter((nodeId) => !isGovernanceNode(nodeId));
      const relationSections = isSdkTool(card.id)
        ? optionalNodeRefSection("工具输入来源", toolInputRefs)
          + optionalNodeRefSection("发挥作用的节点", toolConsumerRefs)
          + optionalNodeRefSection("治理 / 版本控制关系", toolGovernanceRefs)
        : isGovernanceNode(card.id)
          ? optionalNodeRefSection("治理对象 / 受控入口", upstreamRefs)
            + section("下游", nodeRefItems(downstreamRefs))
        : section("上游", nodeRefItems(ordinaryUpstreamRefs))
          + optionalNodeRefSection("SDK Tool 依赖", sdkDependencyRefs)
          + section("下游", nodeRefItems(downstreamRefs));
      detail.innerHTML = "<h2>" + html(card.name) + "</h2>"
        + '<div class="badge-row"><span class="badge ' + badgeClass(card) + '">' + html(card.type) + '</span>'
        + '<span class="badge">Agentic：' + html(card.agentic) + '</span>'
        + '<span class="badge">层级：' + html(card.layer) + '</span></div>'
        + "<p>" + html(card.summary) + "</p>"
        + section("节点类型", textBlock(card.graph_role))
        + section("所属阶段", textBlock(card.phase_scope))
        + section("在整体流程中的作用", textBlock(card.purpose))
        + relationSections
        + section("输入", listItems(card.inputs))
        + section("输出", listItems(card.outputs))
        + section("技术边界", textBlock(card.notes))
        + section("与终态完整规划的关系", textBlock(card.future_link));
    }}
    function getSvgSize(svg) {{
      const viewBox = (svg.getAttribute("viewBox") || "").trim().split(/[\\s,]+/).map(Number);
      if (viewBox.length === 4 && viewBox.every((value) => Number.isFinite(value))) {{
        return {{ width: viewBox[2], height: viewBox[3] }};
      }}
      const bounds = svg.getBoundingClientRect();
      return {{ width: Math.max(bounds.width / scale, 1200), height: Math.max(bounds.height / scale, 720) }};
    }}
    function clampPan(size, x, y) {{
      const scaledWidth = size.width * scale;
      const scaledHeight = size.height * scale;
      let nextX = x;
      let nextY = y;
      if (scaledWidth <= graphWindow.clientWidth) {{
        nextX = (graphWindow.clientWidth - scaledWidth) / 2;
      }} else {{
        nextX = Math.min(0, Math.max(graphWindow.clientWidth - scaledWidth, nextX));
      }}
      if (scaledHeight <= graphWindow.clientHeight) {{
        nextY = Math.max(18, (graphWindow.clientHeight - scaledHeight) / 2);
      }} else {{
        nextY = Math.min(0, Math.max(graphWindow.clientHeight - scaledHeight, nextY));
      }}
      return {{ x: nextX, y: nextY }};
    }}
    function ensurePan(size) {{
      if (pan.x !== null && pan.y !== null) return;
      pan = clampPan(size, 0, 18);
    }}
    function applyTransform() {{
      if (!graphCanvas) return;
      const svg = graphCanvas.querySelector("svg");
      if (!svg) return;
      const size = getSvgSize(svg);
      const graphWidth = size.width;
      const graphHeight = size.height;
      svg.style.width = graphWidth + "px";
      svg.style.height = graphHeight + "px";
      graphCanvas.style.width = graphWidth + "px";
      graphCanvas.style.height = graphHeight + "px";
      ensurePan(size);
      pan = clampPan(size, pan.x, pan.y);
      graphCanvas.style.transform = "translate(" + pan.x + "px," + pan.y + "px) scale(" + scale + ")";
      zoomReadout.textContent = Math.round(scale * 100) + "%";
    }}
    function setScale(nextScale, event) {{
      const svg = graphCanvas ? graphCanvas.querySelector("svg") : null;
      if (!svg) return;
      const size = getSvgSize(svg);
      ensurePan(size);
      const oldScale = scale;
      const rect = graphWindow.getBoundingClientRect();
      const originX = event ? event.clientX - rect.left : rect.width / 2;
      const originY = event ? event.clientY - rect.top : rect.height / 2;
      const graphX = (originX - pan.x) / oldScale;
      const graphY = (originY - pan.y) / oldScale;
      scale = Math.min(maxScale, Math.max(minScale, nextScale));
      pan = clampPan(size, originX - graphX * scale, originY - graphY * scale);
      applyTransform();
    }}
    function parseNodeId(rawId) {{
      const match = String(rawId || "").match(/flowchart-([A-Za-z0-9]+)-/);
      return match ? match[1] : null;
    }}
    function parseEdgeMeta(edge) {{
      const raw = edge.getAttribute("data-id") || edge.id || "";
      const match = raw.match(/L_([A-Za-z0-9]+)_([A-Za-z0-9]+)_\\d+$/);
      return match ? {{ from: match[1], to: match[2] }} : null;
    }}
    function ensureLookupEntry(nodeId) {{
      if (!graphLookup.has(nodeId)) {{
        graphLookup.set(nodeId, {{ element:null, incoming:[], outgoing:[] }});
      }}
      return graphLookup.get(nodeId);
    }}
    function buildGraphLookup() {{
      graphLookup = new Map();
      const svg = graphCanvas ? graphCanvas.querySelector("svg") : null;
      if (!svg) return;
      svg.querySelectorAll(".node").forEach((node) => {{
        const nodeId = parseNodeId(node.id);
        if (!nodeId) return;
        const entry = ensureLookupEntry(nodeId);
        entry.element = node;
      }});
      svg.querySelectorAll('[data-edge="true"]').forEach((edge) => {{
        const meta = parseEdgeMeta(edge);
        if (!meta) return;
        ensureLookupEntry(meta.from).outgoing.push({{ nodeId:meta.to, edge }});
        ensureLookupEntry(meta.to).incoming.push({{ nodeId:meta.from, edge }});
      }});
    }}
    function clearHighlights() {{
      document.querySelectorAll(".graph-canvas svg .node-highlight-ring").forEach((ring) => ring.remove());
      document.querySelectorAll(".graph-canvas svg .node").forEach((node) => node.classList.remove("selected-node", "adjacent-node"));
      document.querySelectorAll('.graph-canvas svg [data-edge="true"]').forEach((edge) => {{
        edge.classList.remove("adjacent-edge", "adjacent-sdk-edge");
        edge.style.removeProperty("stroke");
        edge.style.removeProperty("stroke-width");
        edge.style.removeProperty("opacity");
        edge.style.removeProperty("filter");
      }});
    }}
    function addHighlightRing(node, kind, strokeOverride) {{
      if (!node) return;
      try {{
        const box = node.getBBox();
        const padding = kind === "selected" ? 16 : 11;
        const strokeColor = kind === "selected" ? "#D92D20" : (strokeOverride || "#6A8F63");
        const strokeWidth = kind === "selected" ? "7px" : "5px";
        const glowColor = kind === "selected" ? "rgba(217,45,32,.9)" : glowForColor(strokeColor);
        const ring = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        ring.setAttribute("class", "node-highlight-ring " + kind);
        ring.setAttribute("x", box.x - padding);
        ring.setAttribute("y", box.y - padding);
        ring.setAttribute("width", box.width + padding * 2);
        ring.setAttribute("height", box.height + padding * 2);
        ring.setAttribute("rx", kind === "selected" ? "14" : "12");
        ring.setAttribute("ry", kind === "selected" ? "14" : "12");
        ring.style.setProperty("fill", "none", "important");
        ring.style.setProperty("stroke", strokeColor, "important");
        ring.style.setProperty("stroke-width", strokeWidth, "important");
        ring.style.setProperty("filter", "drop-shadow(0 0 12px " + glowColor + ")", "important");
        ring.style.setProperty("vector-effect", "non-scaling-stroke", "important");
        node.appendChild(ring);
      }} catch (error) {{}}
    }}
    function edgeColorForLink(selectedNodeId, link) {{
      const sdkColor = "#9A825A";
      const isSdkEdge = isSdkTool(selectedNodeId) || isSdkTool(link.nodeId) || (link.edge && link.edge.classList.contains("edge-pattern-dotted"));
      return isSdkEdge ? sdkColor : edgeColorForNode(link.nodeId);
    }}
    function highlightEdge(link, color) {{
      if (!link.edge) return;
      const isSdkEdge = isSdkTool(link.nodeId) || (link.edge && link.edge.classList.contains("edge-pattern-dotted"));
      link.edge.classList.add(isSdkEdge ? "adjacent-sdk-edge" : "adjacent-edge");
      link.edge.style.setProperty("stroke", color, "important");
      link.edge.style.setProperty("stroke-width", "4px", "important");
      link.edge.style.setProperty("opacity", "1", "important");
      link.edge.style.setProperty("filter", "drop-shadow(0 0 7px " + glowForColor(color) + ")", "important");
    }}
    function highlightNeighborhood(nodeId) {{
      const entry = graphLookup.get(nodeId);
      if (!entry) return;
      entry.incoming.forEach((link) => {{
        const neighborColor = edgeColorForNode(link.nodeId);
        highlightEdge(link, edgeColorForLink(nodeId, link));
        const neighbor = graphLookup.get(link.nodeId);
        if (neighbor && neighbor.element) {{
          neighbor.element.classList.add("adjacent-node");
          addHighlightRing(neighbor.element, "adjacent", neighborColor);
        }}
      }});
      entry.outgoing.forEach((link) => {{
        const neighborColor = edgeColorForNode(link.nodeId);
        highlightEdge(link, edgeColorForLink(nodeId, link));
        const neighbor = graphLookup.get(link.nodeId);
        if (neighbor && neighbor.element) {{
          neighbor.element.classList.add("adjacent-node");
          addHighlightRing(neighbor.element, "adjacent", neighborColor);
        }}
      }});
    }}
    function selectNode(nodeId) {{
      const card = nodeMap.get(nodeId);
      if (!card) return;
      clearHighlights();
      const selected = (graphLookup.get(nodeId) || {{}}).element
        || document.querySelector('.graph-canvas svg [id*="flowchart-' + nodeId + '-"]');
      if (selected) {{
        selected.classList.add("selected-node");
        addHighlightRing(selected, "selected");
      }}
      highlightNeighborhood(nodeId);
      renderDetail(card);
    }}
    function attachNodeHandlers() {{
      buildGraphLookup();
      graphLookup.forEach((entry, nodeId) => {{
        if (!entry.element || !nodeMap.has(nodeId)) return;
        entry.element.addEventListener("click", (event) => {{
          event.preventDefault();
          event.stopPropagation();
          if (suppressNodeClick) return;
          selectNode(nodeId);
        }});
      }});
    }}
    detail.addEventListener("click", (event) => {{
      const trigger = event.target.closest("[data-node-ref]");
      if (!trigger) return;
      event.preventDefault();
      const nodeId = trigger.getAttribute("data-node-ref");
      if (nodeId) selectNode(nodeId);
    }});
    graphWindow.addEventListener("wheel", (event) => {{
      event.preventDefault();
      setScale(scale * (event.deltaY < 0 ? 1.08 : 0.92), event);
    }}, {{ passive:false }});
    graphWindow.addEventListener("pointerdown", (event) => {{
      if (event.button !== 0 || !graphCanvas) return;
      const svg = graphCanvas.querySelector("svg");
      if (!svg) return;
      ensurePan(getSvgSize(svg));
      dragState = {{
        startX:event.clientX,
        startY:event.clientY,
        panX:pan.x,
        panY:pan.y,
        moved:false,
        captured:false,
        pointerId:event.pointerId
      }};
    }});
    graphWindow.addEventListener("pointermove", (event) => {{
      if (!dragState) return;
      const dx = event.clientX - dragState.startX;
      const dy = event.clientY - dragState.startY;
      if (!dragState.moved && Math.abs(dx) + Math.abs(dy) <= 4) return;
      if (!dragState.moved) {{
        dragState.moved = true;
        dragState.captured = true;
        graphWindow.setPointerCapture(dragState.pointerId);
        graphWindow.classList.add("is-dragging");
      }}
      const svg = graphCanvas.querySelector("svg");
      pan = clampPan(getSvgSize(svg), dragState.panX + dx, dragState.panY + dy);
      applyTransform();
    }});
    function endDrag(event) {{
      if (!dragState) return;
      suppressNodeClick = dragState.moved;
      const wasCaptured = dragState.captured;
      dragState = null;
      if (wasCaptured) {{
        graphWindow.classList.remove("is-dragging");
        try {{ graphWindow.releasePointerCapture(event.pointerId); }} catch (error) {{}}
      }}
      if (suppressNodeClick) setTimeout(() => {{ suppressNodeClick = false; }}, 0);
    }}
    graphWindow.addEventListener("pointerup", endDrag);
    graphWindow.addEventListener("pointercancel", endDrag);
    document.getElementById("zoom-in").addEventListener("click", () => setScale(scale * 1.12));
    document.getElementById("zoom-out").addEventListener("click", () => setScale(scale / 1.12));
    document.getElementById("reset-view").addEventListener("click", () => {{ scale = {initial_scale}; pan = {{ x:null, y:null }}; applyTransform(); }});
    window.addEventListener("keydown", (event) => {{
      if (event.target && ["INPUT","TEXTAREA","SELECT"].includes(event.target.tagName)) return;
      if (event.key === "+" || event.key === "=") {{ event.preventDefault(); setScale(scale * 1.12); }}
      if (event.key === "-" || event.key === "_") {{ event.preventDefault(); setScale(scale / 1.12); }}
    }});
    window.addEventListener("resize", applyTransform);
    attachNodeHandlers();
    selectNode(defaultNodeId);
    applyTransform();
  </script>
</body>
</html>
"""


def build_index_html():
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>线路工程施工方案 Agent 架构入口</title><style>body{margin:0;font-family:"Microsoft YaHei",sans-serif;background:#f7f3ea;color:#1f2d2a}main{max-width:980px;margin:0 auto;padding:56px 28px}h1{font-size:34px;margin:0 0 16px}p{color:#63736d;line-height:1.8}.note{padding:14px 16px;border:1px solid #deceaa;border-radius:18px;background:#fff7ea;color:#365148;font-weight:700}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:26px}a{display:block;padding:24px;border:1px solid #deceaa;border-radius:22px;background:#fffdf7;color:#1f2d2a;text-decoration:none;box-shadow:0 18px 50px rgb(58 47 26 / 10%)}strong{display:block;font-size:22px;margin-bottom:8px}span{color:#63736d;line-height:1.7}@media(max-width:760px){.cards{grid-template-columns:1fr}}</style></head><body><main><h1>线路工程施工方案 Agent 架构图</h1><p>两张图仍拆成独立页面，并保持右侧固定卡片、滚轮缩放和拖拽平移交互。</p><p class="note">知识页更接近终态知识层；Agent 页当前只覆盖“编制 + 审核”主链，动态管控 / 现场协同暂不进入主图。</p><div class="cards"><a href="knowledge_construction_interactive.html"><strong>知识构建层</strong><span>Raw / Processed / 任务书如何沉淀为参数槽、可复用段落、模板资产、规则资产、证据资产，并通过 KnowledgeStore 进入运行期。</span></a><a href="agent_runtime_interactive.html"><strong>Agent 主链</strong><span>需求理解、多标签子类型与工况识别、表单规划、章节策略路由、受控生成、审核修订闭环和 SDK 工具调用关系。</span></a></div></main></body></html>"""


def parse_args():
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Generate interactive Mermaid/SVG architecture pages.")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "docs" / "agent_architecture")
    return parser.parse_args()


def main():
    output_dir = parse_args().output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge_mmd = output_dir / "knowledge_construction_layer.mmd"
    agent_mmd = output_dir / "agent_runtime_architecture.mmd"
    config_path = output_dir / "mermaid_config.json"
    knowledge_svg_path = output_dir / "knowledge_construction_layer.svg"
    agent_svg_path = output_dir / "agent_runtime_architecture.svg"
    write_text(knowledge_mmd, KNOWLEDGE_MERMAID)
    write_text(agent_mmd, AGENT_MERMAID)
    write_text(config_path, json.dumps(MERMAID_CONFIG, ensure_ascii=False, indent=2))
    knowledge_svg = None
    agent_svg = None
    if render_mermaid_svg(knowledge_mmd, knowledge_svg_path, config_path):
        knowledge_svg = fix_svg_ids(knowledge_svg_path.read_text(encoding="utf-8"), "knowledge-svg")
        write_text(knowledge_svg_path, knowledge_svg)
    if render_mermaid_svg(agent_mmd, agent_svg_path, config_path):
        agent_svg = fix_svg_ids(agent_svg_path.read_text(encoding="utf-8"), "agent-svg")
        write_text(agent_svg_path, agent_svg)
    write_text(output_dir / "knowledge_construction_interactive.html", build_html(
        "知识库层构建",
        "从 Raw 原文和 Processed 章节树中沉淀参数槽、可复用段落、审核规则与证据链。",
        knowledge_svg,
        KNOWLEDGE_MERMAID,
        KNOWLEDGE_CARDS,
        "Processed",
        "agent_runtime_interactive.html",
        "切换到 Agent 层流程图",
        0.43,
        KNOWLEDGE_SCOPE_NOTE,
        KNOWLEDGE_LEGEND_ITEMS,
    ))
    write_text(output_dir / "agent_runtime_interactive.html", build_html(
        "Agent 层流程图",
        "主流程固定可控，分类、表单规划、章节策略、审核修订等局部节点具备 Agentic 决策。",
        agent_svg,
        AGENT_MERMAID,
        AGENT_CARDS,
        "GenPlanner",
        "knowledge_construction_interactive.html",
        "切换到知识库层构建",
        0.50,
        AGENT_SCOPE_NOTE,
        AGENT_LEGEND_ITEMS,
    ))
    write_text(output_dir / "agent_architecture_preview.html", build_index_html())
    write_text(output_dir / "agent_architecture_report.md", REPORT_TEMPLATE.format(
        knowledge_mermaid=KNOWLEDGE_MERMAID.strip(),
        agent_mermaid=AGENT_MERMAID.strip(),
    ))
    print(f"Generated interactive architecture pages in: {output_dir}")


if __name__ == "__main__":
    main()
