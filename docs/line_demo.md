# 线路工程施工方案 Demo

## 目标

这个 Demo 不是通用文档平台，而是一个围绕“线路工程施工方案生成”做的可演示 MVP。

页面流程固定为：

1. 选择工程类型 `线路工程`
2. 选择模板 `A / B / C`
3. 填写关键数据表单
4. 可选填写客制化要求
5. 生成并下载 Markdown 施工方案

## 当前启用范围

当前默认启用：

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

## 三套模板

### 模板 A

- 风格：规范严谨
- 适用：正式报审、标准审批
- 特点：口径稳妥、结构严谨、参数表达完整

### 模板 B

- 风格：均衡通用
- 适用：内部流转、专业会审、一般评审
- 特点：专业但不生硬，阅读更顺

### 模板 C

- 风格：执行展开
- 适用：施工交底、现场执行、班组落实
- 特点：强调工序动作、检查点和转序条件

## 客制化改写规则

### 不填写客制化要求

- 不调用 LLM
- 只做模板填充
- 生成速度快

### 填写客制化要求

- 只对相关章节做受控改写
- 保留原有章节结构、标题层级、表格和工程参数
- 根据章节 `rewrite_topics` 自动选择相关章节
- 对模型输出做结构校验，不合格时自动回退

### 第 3 章特殊规则

第 3 章“施工技术措施”在 A/B/C 三套模板中都只做模板填空，不参与 LLM 改写。

原因：

- 甲方要求第 3 章尽量作为稳定模板使用
- 这一章对施工工序、参数和作业逻辑要求最严格
- 用模板填空更利于稳定输出和后续审阅

## 运行方式

安装依赖：

```bash
pip install -e .
pip install -e .[demo]
```

启动页面：

```bash
streamlit run streamlit_app.py
```

建议在根目录 `.env` 中配置：

```env
MODEL_NAME=qwen3-max
REWRITE_MODEL=qwen3-max
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=your_api_key
LLM_API_KEY=your_api_key
LLM_USE_SYSTEM_PROXY=false
NO_PROXY=dashscope.aliyuncs.com
```

## 配置文件

### 模板变体

- `demo/config/template_variants.yaml`

定义：

- 变体 id
- 展示名称
- 风格标题
- 适用场景
- 风格摘要
- 改写时的风格保持提示

### 章节清单

- `demo/config/chapters.yaml`

定义：

- 章节启用状态
- 输出顺序
- 目录项
- 每章在 A/B/C 下对应的模板文件
- 数据源路径
- 是否允许改写
- 改写主题关键词

### 表单字段

- `demo/config/fields.yaml`

定义：

- 字段 id
- 字段标签
- 字段类型
- 默认值
- 是否必填
- 可编辑表格

## 后续更新章节

新增章节时按这个顺序做：

1. 把新 JSON 放入 `data/`
2. 用 `demo/tools/inspect_source.py` 查看章节树和节点路径
3. 在 `demo/templates/` 下新增该章节模板
4. 在 `demo/config/chapters.yaml` 中注册该章节
5. 如有新字段，再改 `demo/config/fields.yaml`
6. 跑测试并手工生成一次

示例：

```bash
python -m demo.tools.inspect_source --data-file data/8.json
```

## 后续更新模板

新增模板 D/E 时，不需要重写前端，只需要：

1. 在 `demo/config/template_variants.yaml` 里注册新模板
2. 为每个已启用章节补模板文件
3. 在 `demo/config/chapters.yaml` 里补模板映射
4. 跑 `validate_template_context()` 和单测

## 相关文件

- `demo/app.py`
  Streamlit 页面
- `demo/generator.py`
  文档生成、模板选择、改写路由
- `demo/source_data.py`
  源数据解析
- `demo/tools/inspect_source.py`
  新章节接入辅助工具
