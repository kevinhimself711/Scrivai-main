# Scrivai

面向电力工程长文档生成的 Python 项目。当前主交付物是一个可演示、可持续扩展的“线路工程施工方案生成 Demo”。

这个仓库分两层：

- `demo/`
  面向甲方演示的本地 Streamlit 应用。当前流程固定为“选择工程类型 -> 选择模板 A/B/C -> 填写表单 -> 可选填写客制化要求 -> 生成 Markdown 施工方案”。
- `core/`
  通用 SDK 层，提供 LLM、生成、上下文、审核等基础能力。Demo 只复用了 LLM 相关能力，没有依赖知识库和审核主链。

## 当前 Demo 能力

当前 Demo 只有一个工程类型：

- `线路工程`

当前已接入并默认启用的文档部分：

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

当前输出格式：

- Markdown

当前图片处理策略：

- 默认忽略 `data/` 中的图片块
- 不影响正文和表格生成
- 仍保留源数据解析能力，方便以后恢复图片

## 模板 A / B / C

在同一个“线路工程”下，当前提供三套模板变体。三套模板共用同一份表单、同一组字段、同一套表格，但正文风格不同。

### 模板 A

- 风格：规范严谨
- 适用：正式报审、对外提交、标准化审批
- 特点：偏正式、稳妥、报审口径，强调规范依据、管理要求和参数完整性

### 模板 B

- 风格：均衡通用
- 适用：常规内部流转、专业会审、一般评审
- 特点：保持专业准确，但措辞更均衡、阅读更顺

### 模板 C

- 风格：执行展开
- 适用：施工交底、现场执行说明、班组落实
- 特点：更强调现场组织、工序动作、检查点和转序条件

### 模板共性规则

- 三套模板都覆盖当前 1-8 章
- 三套模板共用同一份 `fields.yaml`
- 三套模板共用同一批可编辑 Markdown 表格
- 三套模板章节编号、目录结构、表格位置保持一致
- 第 3 章在 A/B/C 中都只做模板填空，不参与 LLM 改写

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
pip install -e .[demo]
```

如需跑测试：

```bash
pip install -e .[dev]
```

### 2. 配置 `.env`

在仓库根目录创建 `.env`，至少包含：

```env
MODEL_NAME=qwen3-max
REWRITE_MODEL=qwen3-max
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_api_key
LLM_API_KEY=your_api_key

# 可选
TEMPERATURE=0.2
MAX_TOKENS=4096
REWRITE_MAX_TOKENS=3072
REWRITE_CHAPTER_LIMIT=4
REWRITE_CONCURRENCY=3

# 兼容代理场景
LLM_USE_SYSTEM_PROXY=false
NO_PROXY=dashscope.aliyuncs.com
LLM_REQUEST_TIMEOUT=180
```

说明：

- 当前默认使用阿里云百炼的 OpenAI 兼容接口
- `BASE_URL` 固定为 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- 如果本机启用了 Clash 且开启了 TUN，建议将 `dashscope.aliyuncs.com` 或 `aliyuncs.com` 配为 `DIRECT`

### 3. 启动 Demo

```bash
streamlit run streamlit_app.py
```

## 页面使用方式

标准演示流程：

1. 打开页面，工程类型保持 `线路工程`
2. 选择模板 `A / B / C`
3. 检查并填写关键数据表单
4. 如需测试客制化融合，填写“客制化要求”
5. 点击“生成施工方案”
6. 预览并下载 Markdown

下载文件名会自动带模板标识，例如：

- `line_project_demo_template_a.md`
- `line_project_demo_template_b.md`
- `line_project_demo_template_c.md`

## 两种生成模式

### 不填写客制化要求

- 不调用 LLM
- 只做模板填充
- 生成速度快
- 适合校验模板、字段、表格和章节结构

### 填写客制化要求

- 调用 LLM 做受控改写
- 不改变现有章节顺序、标题结构、表格和工程数据
- 系统会按章节 `rewrite_topics` 与用户要求做关键词匹配，自动选择最相关章节
- 若需求更偏“整体文风、正式程度、总说明口径”，则默认优先改写第 1、2 章
- 若模型输出缺章、缺小节或明显截断，则自动回退原章节

### 客制化改写与模板风格的关系

填写客制化要求时，系统不会把所有模板改写成一个口气，而是：

- 先确定用户当前选择的是 A/B/C 哪一套模板
- 将对应模板的风格元数据传给改写 prompt
- 仅做“需求融合”，保留原模板的展开方式和语气
- 第 3 章始终不参与改写

## 配置驱动的模板体系

为了后续继续追加章节和模板，Demo 使用三层配置驱动。

### 1. 模板变体配置

文件：

- `demo/config/template_variants.yaml`

职责：

- 定义模板 `a / b / c`
- 定义展示名称、风格标题、适用场景、篇幅倾向
- 定义改写时的风格保持提示
- 定义默认模板

### 2. 章节清单

文件：

- `demo/config/chapters.yaml`

职责：

- 定义当前启用哪些章节
- 定义输出顺序和是否进入目录
- 为每章声明 `templates.a / templates.b / templates.c`
- 定义章节与 `data/` 中源 JSON 的映射关系
- 定义每章是否参与客制化改写
- 定义每章的 `rewrite_topics`

### 3. 表单字段 schema

文件：

- `demo/config/fields.yaml`

职责：

- 定义字段 id、标签、类型、默认值、是否必填
- 定义页面分组和显示顺序
- 定义哪些字段是可编辑 Markdown 表格
- 定义部分表格默认从 `data/` 读取

### 4. 章节模板 fragments

目录：

- `demo/templates/`

职责：

- 每章一份 Jinja 模板
- 当前变体模式下，每章都有 `A/B/C` 三个模板版本
- 模板只负责本章内容，不直接拼整本文档

## 关键目录结构

```text
Scrivai-main/
├─ core/                         # 通用 SDK
├─ demo/                         # 线路工程 Demo
│  ├─ app.py                     # Streamlit 页面
│  ├─ generator.py               # 统一生成服务
│  ├─ source_data.py             # data/ JSON 解析
│  ├─ config/
│  │  ├─ template_variants.yaml  # A/B/C 模板元数据
│  │  ├─ chapters.yaml           # 章节清单、source mapping、rewrite topics
│  │  └─ fields.yaml             # 表单 schema
│  ├─ templates/                 # 章节模板 fragments
│  └─ tools/
│     └─ inspect_source.py       # 新章节接入辅助工具
├─ data/                         # 真实施工方案切片数据
├─ docs/
├─ tests/
├─ streamlit_app.py
└─ pyproject.toml
```

## 后续如何追加新章节

新增第 9 章或后续章节时，不需要重写页面和主流程，按下面步骤做：

1. 把新的章节 JSON 放进 `data/`
2. 运行辅助工具查看章节树、节点路径、占位词和表格结构
3. 在 `demo/templates/` 下新增该章节的模板文件
4. 在 `demo/config/chapters.yaml` 中注册该章节
5. 如需新增表单字段，在 `demo/config/fields.yaml` 中补充 schema
6. 设置 `enabled: true`
7. 跑测试并手工生成一次做验证

示例：

```bash
python -m demo.tools.inspect_source --data-file data/6.json
python -m demo.tools.inspect_source --data-file data/7.json
python -m demo.tools.inspect_source --data-file data/8.json
```

## 后续如何追加模板变体

如果以后需要做模板 D 或模板 E，沿用当前机制即可：

1. 在 `demo/config/template_variants.yaml` 中新增变体元数据
2. 为每个已启用章节补对应模板文件
3. 在 `demo/config/chapters.yaml` 中为每章补该变体的模板路径
4. 跑 `validate_template_context()` 和单测

不需要改：

- Streamlit 页面主逻辑
- 目录生成逻辑
- 表单收集逻辑
- LLM 改写主流程

## 当前数据处理原则

- 继续沿用 `data/` 中的章节树 JSON
- 运行时不直接把原始 JSON 拼成最终文档，而是走“源数据 + 显式映射 + 章节模板”
- 表格块保留为 Markdown 表格
- 图片块默认忽略
- 原文中的 `XXXX / XXXXX / XXX` 必须替换成明确字段或规范化文本
- 同一语义字段只维护一个来源，避免重复定义

## 关键文件说明

### `demo/app.py`

- 渲染模板卡片
- 根据 `fields.yaml` 动态生成表单
- 收集表单、表格和 LLM 参数
- 调用统一生成服务
- 预览并下载 Markdown

### `demo/generator.py`

- 读取章节配置和模板变体配置
- 规范化表单数据
- 渲染各章节模板
- 自动生成目录
- 根据客制化要求选择改写目标章节
- 并行调用 LLM
- 对改写结果做结构校验和回退

### `demo/source_data.py`

- 读取 `data/` 中的 JSON
- 支持 text / table / list / image 等节点解析
- 默认忽略图片输出
- 支持从源数据生成章节草稿预览

### `demo/tools/inspect_source.py`

用于后续接入新章节时快速查看：

- 章节树结构
- 节点路径
- 占位词情况
- 图片和表格分布
- 草稿预览

## SDK 层说明

如果后续要继续基于仓库里的通用能力开发，可以看 `core/`：

- `core/project.py`
  SDK 统一入口
- `core/llm.py`
  LLM 调用封装，支持 `litellm` 和 OpenAI 兼容直连
- `core/knowledge/store.py`
  知识库能力
- `core/generation/engine.py`
  单章生成
- `core/generation/context.py`
  摘要、术语和引用提取
- `core/audit/engine.py`
  审核能力

为了避免 Demo 被无关依赖阻塞，`core` 已做惰性导入处理；即使未安装 `qmd`，Demo 也能独立运行模板填充和客制化改写流程。

## 测试

建议优先运行：

```bash
pytest tests/unit/test_demo_generation.py tests/unit/test_demo_source_data.py tests/unit/test_llm.py tests/unit/test_project.py tests/unit/test_core_lazy_import.py -q
```

这些测试覆盖：

- A/B/C 模板上下文完整性
- 1-8 章模板填充
- 目录生成
- 数据源解析
- 可编辑表格同步
- 模板变体差异性
- 第 3 章不改写
- 客制化改写路由与回退
- `core` 惰性导入兼容

## 当前限制

- 当前工程类型只有 `线路工程`
- 当前导出格式只有 Markdown
- 图片默认忽略
- LLM 客制化改写仍是“在模板基础上受控改写”，不是从零生成整份施工方案

## 推荐协作方式

如果后续有其他同学继续补章节或补模板，建议遵守这些规则：

- 优先改 `template_variants.yaml`、`chapters.yaml`、`fields.yaml` 和章节模板，不要先改页面代码
- 同一业务字段不要在多个模板里重复发明新的 id
- 新增表格优先走 `markdown_table` 字段
- 不要把某章正文硬编码进 Python
- 每次加章节或模板后，都跑一次单测和一次手工生成

更聚焦的 Demo 说明见：

- `docs/line_demo.md`
