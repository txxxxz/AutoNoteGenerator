# StudyCompanion

StudyCompanion 将 PPT / PDF 课件自动转换为结构化、可控风格的学习资料，覆盖“上传 → 解析 → 大纲 → 笔记 → 模板产物 → 导出 → 问答”的完整闭环。全新架构实现于 FastAPI 服务中，并与增强式 RAG 流程、向量检索、模板化导出能力对齐。

## ✨ 核心能力

- **结构化笔记生成（9 种风格）**：详略档(`brief|medium|detailed`) × 难易档(`simple|explanatory|academic`)组合输出 Markdown 笔记，保留章节骨架与引用。
- **知识卡片**：按章节生成概念卡（定义、考点、例题），便于考前突击。
- **模拟试题**：自动抽取章节要点生成选择 / 填空 / 简答题，并附解析与得分点。
- **思维导图 / 知识树**：将大纲转化为分层图结构，可导出 PNG。
- **页面式内容还原**：保留标题、文本、图片、公式元素及 caption，支持回溯锚点。
- **浮动问答助手**：对当前会话的笔记/卡片/试题即时检索问答，返回溯源引用。
- **多格式导出**：Markdown / PDF（内含目录）、PNG（导图）。

## 🏗️ 架构速览

```text
app/
  api/               # FastAPI 入口与路由
  orchestrator/      # 课程会话编排器
  modules/
    parser/          # PPT/PDF 解析
    layout_ocr/      # 页面式还原与 caption
    chunk_outline/   # 层级化大纲
    note/            # 笔记生成 + 风格策略 + RAG
    templates/       # 卡片 / 模拟题 / 导图
    exporter/        # Markdown / PDF / PNG 导出
    qa/              # 浮动式问答
  schemas/           # Pydantic 契约
  storage/           # SQLite、向量库、资产管理
  configs/           # 配置加载（config.yaml）
```

> 数据持久化：SQLite（元数据 + 产物） + FAISS（向量索引） + 本地资产目录（图片、导出文件）。

## 🚀 快速开始

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **准备环境变量（可选）**
   在 `.env.txt` 中配置 LLM / 向量模型参数（默认使用 Google Gemini；亦支持 OpenAI 兼容接口）。

3. **启动 API 服务**
   ```bash
   uvicorn main:app --reload --port 8000 --log-level debug
   ```

4. **启动前端工作台（可选）**
   ```bash
   cd ui
   npm install
   npm run dev
   ```
   默认开发端口为 `5173`，已在 `vite.config.ts` 中通过代理指向后端 `http://localhost:8000` 的 `/api` 路径。

5. **调用流程示例**
   ```bash
   # 1. 上传文件并创建会话
   curl -X POST http://localhost:8000/api/v1/files \
        -H "Content-Type: application/json" \
        -d '{"name":"lecture.pdf","content_base64":"<BASE64>"}'

   # 2. 解析 + 生成大纲
   curl -X POST http://localhost:8000/api/v1/parse -d '{"session_id":"...","file_id":"...","file_type":"pdf"}'
   curl -X POST http://localhost:8000/api/v1/layout/build -d '{"session_id":"...","file_id":"..."}'
   curl -X POST http://localhost:8000/api/v1/outline/build -d '{"session_id":"..."}'

   # 3. 生成笔记、卡片、模拟题、导图
   curl -X POST http://localhost:8000/api/v1/notes/generate \
        -d '{"session_id":"...","outline_tree_id":"auto","style":{"detail_level":"medium","difficulty":"explanatory"}}'
   curl -X POST http://localhost:8000/api/v1/cards/generate -d '{"session_id":"...","note_doc_id":"note_..."}'
   curl -X POST http://localhost:8000/api/v1/mock/generate -d '{"session_id":"...","note_doc_id":"note_...","options":{"mode":"full","size":20,"difficulty":"mid"}}'
   curl -X POST http://localhost:8000/api/v1/mindmap/generate -d '{"session_id":"...","outline_tree_id":"outline_..."}'

   # 4. 导出所需资料
   curl -X POST http://localhost:8000/api/v1/export \
        -d '{"session_id":"...","target_id":"note_...","type":"notes","format":"pdf"}'

   # 5. 浮动问答
   curl -X POST http://localhost:8000/api/v1/qa/ask \
        -d '{"session_id":"...","scope":"notes","question":"线性回归的适用条件是什么？"}'
   ```

## 🧩 主要 API 契约

| 路径 | 功能 | 请求体 | 响应体核心 |
| ---- | ---- | ------ | ---------- |
| `POST /api/v1/files` | 上传课件、创建会话 | `{ name, content_base64, title? }` | `{ file_id, session_id }` |
| `POST /api/v1/parse` | PPT/PDF 解析 | `{ session_id, file_id, file_type }` | `{ doc_meta, slides[] }` |
| `POST /api/v1/layout/build` | 页面式还原 | `{ session_id, file_id }` | `{ layout_doc }` |
| `POST /api/v1/outline/build` | 章节大纲 | `{ session_id }` | `{ outline_tree }` |
| `POST /api/v1/notes/generate` | 结构化笔记（9 风格） | `{ session_id, outline_tree_id, style }` | `{ note_doc_id, note_doc }` |
| `POST /api/v1/cards/generate` | 知识卡片 | `{ session_id, note_doc_id }` | `{ cards_id, cards }` |
| `POST /api/v1/mock/generate` | 模拟试题 | `{ session_id, note_doc_id, options }` | `{ paper_id, paper }` |
| `POST /api/v1/mindmap/generate` | 思维导图 | `{ session_id, outline_tree_id }` | `{ graph_id, graph }` |
| `POST /api/v1/export` | 导出产物 | `{ session_id, target_id, type, format }` | `{ download_url, filename }` |
| `POST /api/v1/qa/ask` | 浮动问答 | `{ session_id, scope, question }` | `{ answer, refs[] }` |

详尽字段定义参考 `doc/功能实现文档（Feature Implementation Doc）.md` 与 `app/schemas/common.py`。

## ⚙️ 配置

`config.yaml` 提供默认限制，可用环境变量覆盖（前缀 `SC__`）：

```yaml
limits:
  max_pages: 200
  max_file_mb: 100
notes:
  default_detail: medium
  default_difficulty: explanatory
export:
  pdf:
    header: true
    toc: true
rag:
  chunk:
    max_tokens: 500
    overlap: 50
```

示例：`SC__RAG__CHUNK__MAX_TOKENS=600` 会将块大小提升至 600 tokens。

## 📦 资产与持久化

- 上传文件：`uploads/`
- 解析资产（图片、表格截图）：`assets/{session_id}/`
- 向量索引：`.vectors/{session_id}.faiss`
- 导出文件：`exports/{session_id}/`
- SQLite 数据库：`study_companion.db`

## 🧠 LLM 与嵌入

- 支持 `GOOGLE_API_KEY`（默认使用 Gemini 1.5 Flash）或 `OPENAI_API_KEY`。
- 嵌入模型由 `GOOGLE_EMBEDDING_MODEL` 或 `OPENAI_EMBEDDING_MODEL` 指定。
- 温度、检索参数由 `config.yaml` 与 API 侧请求控制。

## ✅ 对齐需求文档的关键点

- 端到端状态：`UPLOADED → PARSED → LAYOUT_BUILT → OUTLINE_READY → NOTES_READY → TEMPLATES_READY → EXPORTED`。
- 两维风格控制与 9 组合规则写入 `app/modules/note/style_policies.py`。
- 所有模板产物（笔记、卡片、模拟题、导图）可导出并溯源锚点。
- 浮动问答限定在当前会话上下文，返回引用数组。

欢迎根据文档继续扩展前端或自动化测试。 🎓
