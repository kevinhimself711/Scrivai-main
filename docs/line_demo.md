# 线路工程施工方案 Demo

## 运行方式

1. 安装基础依赖
   - `pip install -e .`
2. 安装 demo 依赖
   - `pip install -e .[demo]`
3. 启动页面
   - `streamlit run streamlit_app.py`

当前项目默认按阿里云百炼 OpenAI 兼容接口配置：

- `MODEL_NAME=qwen3-max`
- `BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `API_KEY` / `LLM_API_KEY` 从项目根目录 `.env` 读取

## 当前启用范围

当前章节清单位于 `demo/config/chapters.yaml`，默认已启用：

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

## 客制化改写说明

不填写客制化要求时：

- 不调用 LLM
- 只做模板填充
- 适合快速生成和校验结构

填写客制化要求时：

- 系统会根据章节的 `rewrite_topics` 和客制化文本自动选章
- 优先改写与需求最相关的章节，而不是固定只改第 1、2 章
- 若需求更偏整体文风或总述口径，则默认回落到第 1、2 章
- 改写结果会做结构校验，不合格则自动回退原章节

## 后续新增章节的更新步骤

1. 将新的章节树 JSON 放入 `data/`
2. 使用源数据工具查看章节树、节点路径和占位词
   - `python -m demo.tools.inspect_source --data-file data/6.json`
3. 在 `demo/config/chapters.yaml` 中新增章节配置
4. 在 `demo/templates/` 中新增对应章节模板
5. 如需新表单项，在 `demo/config/fields.yaml` 中补充字段 schema
6. 将新章节设为 `enabled: true`

## 核心文件

- `demo/config/fields.yaml`：表单 schema
- `demo/config/chapters.yaml`：章节清单、source mapping、rewrite topics
- `demo/templates/*.j2`：章节模板 fragments
- `demo/generator.py`：统一生成接口与客制化改写路由
- `demo/source_data.py`：源数据解析与草稿预览
- `demo/tools/inspect_source.py`：模板更新辅助工具
