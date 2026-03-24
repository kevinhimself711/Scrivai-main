# Scrivai

面向电力工程长文档生成的 Python 项目，当前主交付物是一个可演示、可持续扩展的“线路工程施工方案生成 Demo”。

当前仓库包含两层能力：

- `demo/`
  面向甲方演示的本地 Streamlit 应用。流程固定为“选择工程类型 -> 填写表单 -> 选填客制化要求 -> 生成 Markdown 施工方案”。
- `core/`
  通用 SDK 层，提供 LLM、知识库、上下文、生成、审核等基础模块，供后续继续封装更完整的平台能力。

## 当前 Demo 能力

当前 Demo 已接入并启用以下章节：

- 封面
- 审批页
- 目录
- 第 1 章 编制说明
- 第 2 章 工程概况
- 第 3 章 施工技术措施
- 第 4 章 施工组织措施
- 第 5 章 安全管理措施
- 第 6 章 质量管理措施
- 第 7 章 应急处置措施
- 第 8 章 环境保护与水土保持措施

当前页面只提供一个工程类型：

- `线路工程`

生成结果当前以 Markdown 为主，图片块默认忽略，不影响方案正文演示。

## Demo 使用方式

### 1. 安装依赖

```bash
pip install -e .
pip install -e .[demo]
```

如需运行测试：

```bash
pip install -e .[dev]
```

### 2. 配置环境变量

在项目根目录准备 `.env` 文件，至少包含：

```env
MODEL_NAME=qwen3-max
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_api_key
LLM_API_KEY=your_api_key

# 兼容 Clash / TUN 场景，默认不继承系统代理
LLM_USE_SYSTEM_PROXY=false
NO_PROXY=dashscope.aliyuncs.com

# OpenAI 兼容接口直连模式的读取超时，默认 180 秒
LLM_REQUEST_TIMEOUT=180

# 可选：客制化改写的专用参数
REWRITE_MODEL=qwen3-max
REWRITE_MAX_TOKENS=2600
REWRITE_CHAPTER_LIMIT=4
REWRITE_CONCURRENCY=3
```

说明：

- 当前默认对接阿里云百炼 OpenAI 兼容接口。
- `BASE_URL` 使用 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- 如果本机启用了 Clash 且开启了 TUN，建议在代理规则中把 `dashscope.aliyuncs.com` 或 `aliyuncs.com` 设为 `DIRECT`。

### 3. 启动 Demo

```bash
streamlit run streamlit_app.py
```

### 4. 标准演示流程

1. 打开页面，选择工程类型 `线路工程`
2. 检查并填写关键数据表单
3. 如有需要，填写“客制化要求”
4. 点击“生成施工方案”
5. 预览结果并下载 Markdown

## 两种生成模式

### 不填写客制化要求

- 不调用 LLM
- 只做模板填充
- 生成速度快
- 适合校验模板、字段、表格与章节结构

### 填写客制化要求

- 调用 LLM 做受控改写
- 不改变现有章节顺序、标题结构、表格和工程数据
- 系统会根据章节标签和客制化关键词，自动选择最相关的章节进行改写
- 若需求只是偏“整体文风、正式程度、总述口径”这类泛化要求，则默认优先改写第 1、2 章
- 若模型输出结构异常、章节缺失或明显截断，则自动回退原章节

## 当前客制化改写策略

客制化改写不再固定只改第 1、2 章，而是“按主题路由 + 受控回退”：

1. 先从 `demo/config/chapters.yaml` 读取每章的 `rewrite_topics`
2. 根据用户输入的客制化要求做关键词匹配和打分
3. 在上限范围内选择最相关的章节并行改写
4. 对每个改写结果做结构校验
5. 不合格的结果回退为模板原文

当前默认可覆盖的改写主题包括但不限于：

- 雨季施工
- 环保水保
- 山区运输
- 边坡稳定
- 夜间施工
- 质量控制
- 缺陷处理
- 应急处置
- 风险监测
- 文明施工

相关实现位于：

- `demo/generator.py`
- `demo/config/chapters.yaml`

## 配置驱动的模板体系

为了便于后续继续追加章节，Demo 采用“三层配置驱动”：

### 1. 章节清单

文件：

- `demo/config/chapters.yaml`

职责：

- 定义当前启用哪些章节
- 定义输出顺序和是否进入目录
- 定义每章对应的模板文件
- 定义章节和源数据 JSON 的映射关系
- 定义每章是否参与客制化改写，以及其改写主题标签

### 2. 表单字段 schema

文件：

- `demo/config/fields.yaml`

职责：

- 定义字段 id、标题、类型、默认值、是否必填
- 定义页面字段分组
- 定义可编辑 Markdown 表格字段
- 定义部分字段从 `data/` 中加载默认表格内容

### 3. 章节模板 fragments

目录：

- `demo/templates/`

职责：

- 每章一个 Jinja 模板
- 模板只负责本章节内容
- 最终整份方案由生成器按启用顺序拼装

## 关键目录结构

```text
Scrivai-main/
├─ core/                     # 通用 SDK 层
├─ demo/                     # 线路工程 Demo
│  ├─ app.py                 # Streamlit 页面
│  ├─ generator.py           # Demo 统一生成服务
│  ├─ source_data.py         # data/ JSON 解析
│  ├─ config/
│  │  ├─ chapters.yaml       # 章节清单、source mapping、rewrite tags
│  │  └─ fields.yaml         # 表单 schema
│  ├─ templates/             # 章节模板 fragments
│  └─ tools/
│     └─ inspect_source.py   # 新章节接入辅助工具
├─ data/                     # 真实施工方案切片数据
├─ docs/
├─ tests/
├─ streamlit_app.py
└─ pyproject.toml
```

## 后续如何追加新章节

新增第 9 章或后续章节时，不需要重写页面和主流程，按下面步骤做：

1. 把新的章节 JSON 放进 `data/`
2. 用辅助工具查看章节树、节点路径、占位词和表格结构
3. 在 `demo/templates/` 下新增章节模板
4. 在 `demo/config/chapters.yaml` 中注册该章节
5. 如有新增字段，在 `demo/config/fields.yaml` 中补充 schema
6. 将该章节设为 `enabled: true`
7. 运行测试并做一次手工生成校验

示例：

```bash
python -m demo.tools.inspect_source --data-file data/6.json
python -m demo.tools.inspect_source --data-file data/7.json
python -m demo.tools.inspect_source --data-file data/8.json
```

这样做的好处是：

- 不用修改 Streamlit 页面主逻辑
- 不用手写新的目录拼接逻辑
- 不会破坏既有章节
- 方便不同同学并行补章节模板

## 当前接入数据的处理原则

- 继续沿用 `data/` 中的章节树 JSON
- 运行时不把原始 JSON 直接裸转成最终文档，而是通过“源数据 + 显式映射 + 章节模板”落地
- 图片块默认忽略，但保留解析能力，后续如需恢复图片可继续扩展
- 表格块保留为 Markdown 表格
- 原文中的 `XXXX / XXXXX / XXX` 必须替换为明确字段或改写为规范化表述，不能直接进入最终演示稿
- 同一语义字段只维护一个来源，避免同一个项目名称、标段名、工期在多个地方分别写死

## 关键文件说明

### `demo/app.py`

- 根据 `fields.yaml` 动态渲染表单
- 收集表单和可编辑表格
- 收集 LLM 参数
- 调用统一生成服务
- 预览与下载 Markdown

### `demo/generator.py`

- 读取章节配置
- 规范化表单数据
- 渲染各章节模板
- 自动生成目录
- 根据客制化要求选择改写目标章节
- 并行调用 LLM
- 对改写结果做结构校验与回退

### `demo/source_data.py`

- 读取 `data/` 中的 JSON
- 支持 text、table、list、image 等节点类型解析
- 默认忽略图片输出
- 支持从源数据生成章节草稿，便于后续快速整理模板

### `demo/tools/inspect_source.py`

用于新章节接入时快速查看：

- 章节树结构
- 节点路径
- 占位词情况
- 图片和表格分布
- 草稿预览

## SDK 层说明

如果你要继续基于仓库里的通用能力开发，可以看 `core/`：

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

- 1-8 章模板填充
- 目录生成
- 数据源解析
- 可编辑表格同步
- 客制化改写路由
- 无效改写自动回退
- `core` 惰性导入兼容

## 当前限制

- 当前工程类型只有 `线路工程`
- 当前导出格式只有 Markdown
- 图片默认忽略
- LLM 客制化改写仍是“在模板基础上受控改写”，不是从零生成整份施工方案

## 推荐协作方式

如果后续有其他同学继续补章节，建议遵守这些规则：

- 优先改 `chapters.yaml`、`fields.yaml`、章节模板，不要先改页面代码
- 同一业务字段不要在多个模板里重复定义
- 新增表格优先走 `markdown_table` 字段
- 不要把某章正文硬编码进 Python 逻辑
- 每次追加章节后都跑一次单测和一次手工生成

详细 demo 说明可继续查看：

- `docs/line_demo.md`
