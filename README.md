# Scrivai

线路工程施工方案生成 Demo，以及一套可复用的长文档生成 SDK 骨架。

当前仓库已经落地了一个可演示的 MVP：

- 工程类型固定为 `线路工程`
- 页面流程为 `选择工程类型 -> 填写关键数据表单 -> 选填客制化要求 -> 生成 Markdown 施工方案`
- 当前已接入封面、审批页、目录、第 1 章、第 2 章、第 3 章、第 4 章、第 5 章
- 后续新增章节时，不需要重写页面，只需要补数据、章节配置和模板

## 1. 项目定位

这个项目现在有两层能力：

1. `core/`
   一套偏 SDK 的通用文档生成骨架，包含 LLM 调用、知识库、上下文、审核等模块。
2. `demo/`
   一个围绕“线路工程机械挖孔基础施工方案”做的具体 Demo，当前是实际对外演示的主入口。

如果你的目标是快速跑出演示效果，请优先看 `demo/` 和 Streamlit 页面。

## 2. 当前 Demo 能做什么

### 2.1 基础能力

- 读取 `data/` 中整理过的真实施工方案 JSON 数据
- 按章节模板生成施工方案 Markdown
- 表单中的同一字段会在全文多个位置复用
- 支持可编辑表格字段，例如基础技术参数表、人员配置表
- 忽略图片，不影响当前 Demo 生成

### 2.2 客制化要求

- 如果不填写客制化要求，系统走纯模板填充，生成速度快
- 如果填写客制化要求，系统会调用 LLM 做受控改写
- 当前客制化改写默认只改写第 1、2 章
  - 这是当前 Demo 的性能与稳定性折中
  - 第 3、4、5 章仍由模板直接输出
  - 这样可以显著降低超时风险，同时保证主体结构稳定

### 2.3 当前已启用章节

- 封面
- 审批页
- 目录
- 第 1 章 编制说明
- 第 2 章 工程概况
- 第 3 章 施工技术措施
- 第 4 章 施工组织措施
- 第 5 章 安全管理措施

章节开关和顺序定义在 [demo/config/chapters.yaml](/d:/Engineering%20Projects/Scrivai-main/demo/config/chapters.yaml)。

## 3. 目录结构

```text
Scrivai-main/
├─ core/                     # 通用 SDK 核心模块
├─ demo/                     # 线路工程 Demo 主体
│  ├─ app.py                 # Streamlit 页面
│  ├─ generator.py           # Demo 统一生成服务
│  ├─ source_data.py         # JSON 源数据解析
│  ├─ config/
│  │  ├─ chapters.yaml       # 章节清单与启用顺序
│  │  └─ fields.yaml         # 表单 schema
│  ├─ templates/             # 每章一个 Jinja 模板
│  └─ tools/
│     └─ inspect_source.py   # 新章节接入辅助工具
├─ data/                     # 真实施工方案切片 JSON
├─ docs/                     # 说明文档
├─ tests/                    # 单测与集成测试
├─ streamlit_app.py          # Streamlit 顶层入口
├─ pyproject.toml
└─ README.md
```

## 4. 快速启动

### 4.1 环境要求

- Python 3.11+
- Windows / macOS / Linux 均可
- 建议使用虚拟环境

### 4.2 安装依赖

```bash
pip install -e .
pip install -e .[demo]
```

如果你需要跑测试：

```bash
pip install -e .[dev]
```

### 4.3 配置环境变量

项目根目录放一个 `.env` 文件，至少包含：

```env
MODEL_NAME=qwen3-max
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_api_key
LLM_API_KEY=your_api_key

# 默认不读取系统代理，避免和本地代理/TUN 冲突
LLM_USE_SYSTEM_PROXY=false
NO_PROXY=dashscope.aliyuncs.com

# OpenAI 兼容接口读取超时，默认 180 秒
LLM_REQUEST_TIMEOUT=180
```

说明：

- Demo 当前默认使用阿里云百炼的 OpenAI 兼容接口
- `BASE_URL` 当前使用 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- 如果本机使用 Clash/TUN，建议在代理规则里把 `dashscope.aliyuncs.com` 设为 `DIRECT`

### 4.4 启动 Demo

```bash
streamlit run streamlit_app.py
```

启动后可直接在浏览器中使用。

## 5. Demo 使用说明

### 5.1 标准使用流程

1. 打开页面
2. 选择工程类型
   当前只有 `线路工程`
3. 填写关键数据表单
4. 如有需要，填写“客制化要求”
5. 点击“生成施工方案”
6. 预览 Markdown 并下载

### 5.2 两种生成模式

#### 不填写客制化要求

- 不调用 LLM
- 只做模板填充
- 速度最快
- 适合检查模板、字段、表格是否正确

#### 填写客制化要求

- 会调用 LLM
- 当前只对第 1、2 章做受控改写
- 会保留原有章节结构、表格和工程数据
- 适合演示“在既有模板基础上融入甲方要求”

## 6. 配置驱动设计

这个 Demo 的核心不是“把整篇文档写死”，而是“三层配置驱动”。

### 6.1 章节清单

文件：
[demo/config/chapters.yaml](/d:/Engineering%20Projects/Scrivai-main/demo/config/chapters.yaml)

职责：

- 定义当前有哪些章节
- 定义章节顺序
- 定义是否启用
- 定义是否进入目录
- 定义章节模板文件
- 定义章节对应的源数据文件和源路径

### 6.2 表单 schema

文件：
[demo/config/fields.yaml](/d:/Engineering%20Projects/Scrivai-main/demo/config/fields.yaml)

职责：

- 定义字段 id
- 定义字段标题
- 定义字段类型
- 定义是否必填
- 定义默认值
- 定义字段分组

页面表单由这个 schema 动态生成，不需要在前端手写每个字段。

### 6.3 章节模板 fragments

目录：
[demo/templates](/d:/Engineering%20Projects/Scrivai-main/demo/templates)

职责：

- 每个章节单独一个模板
- 模板只负责当前章节
- 最终文档由生成器按启用章节顺序拼装

## 7. 关键代码说明

### 7.1 Demo 页面

文件：
[demo/app.py](/d:/Engineering%20Projects/Scrivai-main/demo/app.py)

职责：

- 读取 schema
- 渲染 Streamlit 表单
- 收集用户输入
- 调用生成器
- 展示预览和下载按钮

### 7.2 统一生成服务

文件：
[demo/generator.py](/d:/Engineering%20Projects/Scrivai-main/demo/generator.py)

这是当前 Demo 最重要的文件，负责：

- 读取章节配置
- 规范化表单数据
- 渲染各章节模板
- 自动生成目录
- 在有客制化要求时调用 LLM
- 对 LLM 输出做结构校验

当前客制化策略：

- 只改写第 1、2 章
- 两个章节并行调用 LLM
- 若 LLM 输出缺章、缺小节或明显截断，则回退原章节

### 7.3 源数据解析

文件：
[demo/source_data.py](/d:/Engineering%20Projects/Scrivai-main/demo/source_data.py)

职责：

- 读取 `data/` 中的 JSON
- 通过显式路径提取章节、表格、文本块
- 忽略图片块，但保留解析能力

### 7.4 新章节接入辅助工具

文件：
[demo/tools/inspect_source.py](/d:/Engineering%20Projects/Scrivai-main/demo/tools/inspect_source.py)

用途：

- 查看 JSON 章节树
- 查看路径
- 查看占位词
- 辅助整理新章节模板

示例：

```bash
python -m demo.tools.inspect_source --data-file data/3.json
```

## 8. 如何继续新增章节

这是协作同学最重要的部分。

新增第 6 章或后续章节时，不要去改页面主流程，按下面的步骤做：

1. 把新的章节 JSON 放进 `data/`
2. 用 `inspect_source.py` 看章节树和可复用内容
3. 在 `demo/templates/` 下新增章节模板
4. 在 `demo/config/chapters.yaml` 里注册新章节
5. 如果需要新增字段，在 `demo/config/fields.yaml` 里补充 schema
6. 将章节 `enabled: true`
7. 跑测试并手工验证

这样做的好处：

- 不需要改 Streamlit 页面主逻辑
- 不需要重写目录生成逻辑
- 不会破坏已有章节
- 适合多位同学并行协作

## 9. 数据与模板协作规则

为了避免后续多人接手时越改越乱，建议统一遵守这些规则：

- 一个语义字段只维护一个 id
  - 例如项目名称、起止站、标段名、工期不要在多个模板里各自写死
- 模板里不要保留 `XXXX / XXXXX / XXX`
  - 应替换为明确字段
- 图片先忽略，不要为了图片占位去破坏正文结构
- 新增可编辑表格时，优先使用 `markdown_table` 字段类型
- 不要直接在 `app.py` 里硬编码业务字段
- 不要在生成器里把某章正文写死到 Python 代码里

## 10. SDK 层说明

如果你要使用通用能力，可以看 `core/`。

### 10.1 主要模块

- [core/project.py](/d:/Engineering%20Projects/Scrivai-main/core/project.py)
  统一入口，负责装配
- [core/llm.py](/d:/Engineering%20Projects/Scrivai-main/core/llm.py)
  LLM 调用封装，支持 litellm 和 OpenAI 兼容直连
- [core/knowledge/store.py](/d:/Engineering%20Projects/Scrivai-main/core/knowledge/store.py)
  知识库接口
- [core/generation/engine.py](/d:/Engineering%20Projects/Scrivai-main/core/generation/engine.py)
  单章生成
- [core/generation/context.py](/d:/Engineering%20Projects/Scrivai-main/core/generation/context.py)
  摘要、术语、引用提取
- [core/audit/engine.py](/d:/Engineering%20Projects/Scrivai-main/core/audit/engine.py)
  审核能力

### 10.2 导入方式

当前更稳妥的导入方式是：

```python
from core import Project
from core import LLMClient, LLMConfig
```

说明：

- `core/__init__.py` 做了惰性导入
- 这样在未安装 `qmd` 时，也不至于让 Demo 整体导入失败

## 11. 测试

### 11.1 推荐先跑的测试

```bash
pytest tests/unit/test_demo_generation.py tests/unit/test_llm.py tests/unit/test_project.py tests/unit/test_core_lazy_import.py -q
```

这些测试覆盖了：

- 模板变量完整性
- 默认生成结果
- 表格编辑写回
- 客制化改写调用
- LLM 回退逻辑
- core 层惰性导入

### 11.2 当前关注的回归点

- 是否还有占位符残留
- 客制化要求是否会导致超时
- 第 2 章是否被 LLM 截断
- 表格修改是否反映到最终 Markdown
- 新增章节后目录是否自动扩展

## 12. 常见问题

### 12.1 不填客制化要求时很快，填写后变慢

正常。

- 不填客制化要求时，只做模板填充
- 填写后会调用 LLM 做改写

当前已经做了并行改写和章节回退保护，但仍然比纯模板模式慢。

### 12.2 百炼接口超时

先排查这几项：

- `.env` 中 `BASE_URL` 是否正确
- `API_KEY` 是否有效
- 本机代理是否影响了 `dashscope.aliyuncs.com`
- Clash/TUN 是否已为该域名配置 `DIRECT`
- 是否填写了过长或过于复杂的客制化要求

### 12.3 为什么现在只改第 1、2 章

因为这是当前 Demo 的稳定性折中。

- 第 1、2 章适合承接总述型客制化要求
- 全文改写成本太高，容易超时或破坏结构
- 后续如果需要，可以再升级为“按关键词路由到第 3、4、5 章”

## 13. 协作建议

如果是多人并行开发，建议这样分工：

- A 同学负责 `data/` 数据整理
- B 同学负责 `demo/templates/` 章节模板
- C 同学负责 `demo/config/fields.yaml` 表单 schema
- D 同学负责测试与联调

这样可以最大限度减少冲突。

## 14. 当前已知限制

- 当前工程类型只有 `线路工程`
- 当前输出格式只有 Markdown
- 图片暂未纳入生成结果
- 客制化要求默认只改写第 1、2 章
- `qmd` 仍是 SDK 层的可选依赖点，主要影响通用知识库能力，不影响当前 Demo 主流程

## 15. 启动命令速查

安装：

```bash
pip install -e .
pip install -e .[demo]
```

运行：

```bash
streamlit run streamlit_app.py
```

测试：

```bash
pytest tests/unit/test_demo_generation.py tests/unit/test_llm.py tests/unit/test_project.py tests/unit/test_core_lazy_import.py -q
```

源数据检查：

```bash
python -m demo.tools.inspect_source --data-file data/3.json
```
