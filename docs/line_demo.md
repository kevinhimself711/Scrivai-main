# 线路工程施工方案 Demo

## 运行方式

1. 安装基础依赖：
   - `pip install -e .`
2. 安装 demo 依赖：
   - `pip install -e .[demo]`
3. 启动页面：
   - `streamlit run streamlit_app.py`

当前仓库已按阿里云百炼 OpenAI 兼容接口预配置：

- `MODEL_NAME=qwen3-max`
- `BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `API_KEY` / `LLM_API_KEY` 从项目根目录 `.env` 读取

## 当前启用范围

当前章节清单位于 `demo/config/chapters.yaml`，默认启用：

- 封面
- 审批页
- 目录
- 第1章 编制说明
- 第2章 工程概况
- 第3章 施工技术措施
- 第4章 施工组织措施
- 第5章 安全管理措施

## 后续新增章节的更新步骤

1. 将新的章节树 JSON 放入 `data/`。
2. 使用源数据工具查看章节树和占位词：
   - `python -m demo.tools --data-file data/2.json --chapter-id chapter_1`
3. 在 `demo/config/chapters.yaml` 中新增章节配置。
4. 在 `demo/templates/` 中新增对应章节模板。
5. 如需新增表单项，在 `demo/config/fields.yaml` 中补充字段 schema。
6. 将新章节设为 `enabled: true`，目录会自动扩展。

## 核心文件

- `demo/config/fields.yaml`：表单 schema
- `demo/config/chapters.yaml`：章节清单与 source mapping
- `demo/templates/*.j2`：章节模板 fragments
- `demo/generator.py`：统一生成接口
- `demo/source_data.py`：源数据解析和草稿预览
- `demo/tools/inspect_source.py`：模板更新辅助工具
