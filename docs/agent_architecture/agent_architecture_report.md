# 线路工程施工方案 Agent 架构图说明

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
flowchart LR
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
```

## Agent 主链

```mermaid
flowchart TD
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
```
