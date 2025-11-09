# StudyCompanion

# StudyCompanion

**将课程课件转化为可控风格的结构化学习资料**

StudyCompanion 是一个智能学习助手,能够自动将 PPT 或 PDF 课件转换为多种形式的高质量学习材料。通过 AI 驱动的内容解析与生成能力,系统覆盖从上传、解析、大纲构建到笔记生成、模板输出、导出和问答的完整学习闭环。

---

## 核心特性

### 🎯 多风格笔记生成

通过 **详略程度** × **难易程度** 两个维度的组合,生成 9 种不同风格的结构化笔记:

- **详略程度**: `brief`(简略) | `medium`(中等) | `detailed`(详细)
- **难易程度**: `simple`(通俗易懂) | `explanatory`(标准讲解) | `academic`(学术深入)

每种风格都有独立的策略控制,包括长度比例、术语密度、公式使用、句式复杂度等,确保输出符合不同学习场景需求。

### 📚 多模板学习资料

- **知识卡片**: 按章节提取核心概念、关键公式和算法要点,适合快速复习
- **模拟试题**: 自动生成选择题、填空题和简答题,附参考答案与解析
- **思维导图**: 将大纲转化为可视化的层级结构,支持导出为图片

### 🔍 智能问答助手

基于 RAG (检索增强生成) 技术,对当前会话的学习内容进行即时问答,并提供溯源引用,帮助理解复杂概念。

### 📄 多格式导出

支持将生成的笔记、卡片、试题导出为:
- **Markdown**: 纯文本格式,易于编辑和版本控制
- **PDF**: 专业排版,包含目录和页眉
- **PNG**: 思维导图图片格式

---

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+ (如需运行前端)
- Google Gemini API Key 或 OpenAI API Key

### 安装与配置

1. **克隆项目并安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

2. **配置 API 密钥**

   创建 `.env` 文件并设置你的 API 密钥:

   ```bash
   # 使用 Google Gemini
   GOOGLE_API_KEY=your_google_api_key_here
   
   # 或使用 OpenAI
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **启动后端服务**

   ```bash
   uvicorn main:app --reload --port 8000
   ```

   服务将在 `http://localhost:8000` 启动。

4. **启动前端界面 (可选)**

   ```bash
   cd ui
   npm install
   npm run dev
   ```

   前端将在 `http://localhost:5173` 启动,并自动代理 API 请求到后端。

### 验证安装

访问 `http://localhost:8000/docs` 查看 API 文档,确认服务正常运行。

---

## 使用指南

### 基本工作流程

StudyCompanion 的使用遵循以下步骤:

```
上传课件 → 解析内容 → 构建大纲 → 生成笔记 → 创建模板 → 导出资料
```

### 1. 上传课件

使用前端界面或 API 上传 `.pptx` 或 `.pdf` 文件:

```bash
curl -X POST "http://localhost:8000/api/v1/files" \
  -F "file=@lecture.pdf" \
  -F "title=机器学习导论"
```

**响应示例**:
```json
{
  "file_id": "file_abc123",
  "session_id": "session_xyz789"
}
```

每次上传会创建一个新的会话 (session),后续所有操作都基于这个会话 ID。

### 2. 解析课件内容

**a) 提取文本和结构**

```bash
curl -X POST "http://localhost:8000/api/v1/parse" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "file_id": "file_abc123",
    "file_type": "pdf"
  }'
```

**b) 构建页面布局 (保留图片、公式等)**

```bash
curl -X POST "http://localhost:8000/api/v1/layout/build" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "file_id": "file_abc123"
  }'
```

### 3. 生成章节大纲

系统会自动识别课件的层级结构:

```bash
curl -X POST "http://localhost:8000/api/v1/outline/build" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789"
  }'
```

**响应示例**:
```json
{
  "id": "outline_001",
  "root": {
    "title": "机器学习导论",
    "children": [
      {"title": "第一章 监督学习", "children": [...]},
      {"title": "第二章 无监督学习", "children": [...]}
    ]
  }
}
```

### 4. 生成笔记

选择合适的风格组合生成笔记。以下是常见场景的推荐配置:

| 场景 | 详略程度 | 难易程度 | 说明 |
|------|---------|---------|------|
| 快速复习 | `brief` | `simple` | 简洁要点,适合考前突击 |
| 日常学习 | `medium` | `explanatory` | 标准教科书风格 |
| 深度研究 | `detailed` | `academic` | 包含完整推导和理论背景 |

> 通过 `language` 选项可切换输出语言：`zh`（默认，中文）或 `en`（英文）。可在 `style.language` 中声明，也可在请求体顶层携带 `language` 字段。

**示例: 生成标准讲解风格的笔记**

```bash
curl -X POST "http://localhost:8000/api/v1/notes/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "outline_tree_id": "auto",
    "style": {
      "detail_level": "medium",
      "difficulty": "explanatory",
      "language": "zh"
    },
    "language": "zh"
  }'
```

**响应**:
```json
{
  "task_id": "task_note_001"
}
```

笔记生成是异步任务,使用 task_id 查询进度:

```bash
# 查询任务状态
curl "http://localhost:8000/api/v1/notes/tasks/task_note_001"

# 或使用 SSE 流式获取进度
curl "http://localhost:8000/api/v1/notes/tasks/task_note_001/stream"
```

### 5. 生成学习模板

**a) 知识卡片**

```bash
curl -X POST "http://localhost:8000/api/v1/cards/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "note_doc_id": "note_001"
  }'
```

**b) 模拟试题**

```bash
curl -X POST "http://localhost:8000/api/v1/mock/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "note_doc_id": "note_001",
    "options": {
      "mode": "full",
      "size": 20,
      "difficulty": "mid"
    }
  }'
```

**c) 思维导图**

```bash
curl -X POST "http://localhost:8000/api/v1/mindmap/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "outline_tree_id": "outline_001"
  }'
```

### 6. 导出资料

将生成的内容导出为所需格式:

```bash
curl -X POST "http://localhost:8000/api/v1/export" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "target_id": "note_001",
    "type": "notes",
    "format": "pdf"
  }'
```

**响应**:
```json
{
  "download_url": "/exports/session_xyz789/notes_note_001.pdf",
  "filename": "机器学习导论_笔记.pdf"
}
```

### 7. 智能问答

对当前会话的学习内容进行提问:

```bash
curl -X POST "http://localhost:8000/api/v1/qa/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xyz789",
    "scope": "notes",
    "question": "什么是梯度下降法?"
  }'
```

**响应示例**:
```json
{
  "answer": "梯度下降法是一种优化算法,通过迭代地沿着目标函数梯度的反方向更新参数...",
  "refs": [
    {"section": "第一章 监督学习", "page": 5, "snippet": "...梯度下降的数学原理..."}
  ]
}
```

---

## 管理会话

### 查看所有会话

```bash
curl "http://localhost:8000/api/v1/sessions"
```

### 查看会话详情

```bash
curl "http://localhost:8000/api/v1/sessions/session_xyz789"
```

会话详情包含该会话下所有生成的产物 ID,方便你检索和导出。

---

## 配置说明

### 环境变量

系统支持通过环境变量覆盖默认配置,使用 `SC__` 前缀:

```bash
# 调整最大文件大小为 150MB
export SC__LIMITS__MAX_FILE_MB=150

# 调整 RAG 检索块大小
export SC__RAG__CHUNK__MAX_TOKENS=600
```

### 配置文件

编辑 `config.yaml` 自定义系统行为:

```yaml
limits:
  max_pages: 200          # 单个文件最大页数
  max_file_mb: 100        # 上传文件大小限制 (MB)

notes:
  default_detail: medium   # 默认详略程度
  default_difficulty: explanatory  # 默认难易程度

export:
  pdf:
    header: true          # PDF 是否包含页眉
    toc: true             # PDF 是否生成目录
  md:
    math_block: true      # Markdown 是否使用数学块

rag:
  chunk:
    max_tokens: 500       # 向量检索的文本块大小
    overlap: 50           # 相邻块的重叠词数
```

### LLM 配置

**使用 Google Gemini (默认)**:
```bash
export GOOGLE_API_KEY=your_key
export GOOGLE_EMBEDDING_MODEL=models/text-embedding-004
```

**使用 OpenAI**:
```bash
export OPENAI_API_KEY=your_key
export OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

---

## 项目结构

```
app/
├── api/                    # FastAPI 路由定义
├── orchestrator/           # 会话管理与流程编排
├── modules/
│   ├── parser/            # PPT/PDF 解析
│   ├── layout_ocr/        # 页面布局还原
│   ├── chunk_outline/     # 大纲构建
│   ├── note/              # 笔记生成 (含 9 种风格策略)
│   ├── templates/         # 卡片/试题/思维导图生成
│   ├── exporter/          # 多格式导出
│   └── qa/                # RAG 问答
├── schemas/               # Pydantic 数据模型
├── storage/               # 数据库与向量存储
├── configs/               # 配置管理
└── utils/                 # 工具函数

ui/                        # React + TypeScript 前端
├── src/
│   ├── pages/            # 页面组件
│   ├── components/       # UI 组件
│   └── api/              # API 客户端

doc/                       # 项目文档
├── 需求说明.md
├── 系统架构设计文档.md
└── 功能实现文档.md
```

---

## 数据存储

系统使用多层存储策略:

| 存储类型 | 位置 | 用途 |
|---------|------|------|
| SQLite | `db/study_companion.db` | 会话元数据、产物索引 |
| FAISS | `.vectors/{session_id}.faiss` | 向量索引 (RAG 检索) |
| 文件系统 | `uploads/` | 上传的原始课件 |
| 文件系统 | `assets/{session_id}/` | 解析出的图片、表格 |
| 文件系统 | `exports/{session_id}/` | 导出的文档 |

---

## API 参考

完整的 API 文档可通过以下方式访问:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

主要端点:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/files` | POST | 上传课件并创建会话 |
| `/api/v1/parse` | POST | 解析课件内容 |
| `/api/v1/layout/build` | POST | 构建页面布局 |
| `/api/v1/outline/build` | POST | 生成章节大纲 |
| `/api/v1/notes/generate` | POST | 生成笔记 (异步任务) |
| `/api/v1/notes/tasks/{task_id}` | GET | 查询笔记生成任务状态 |
| `/api/v1/cards/generate` | POST | 生成知识卡片 |
| `/api/v1/mock/generate` | POST | 生成模拟试题 |
| `/api/v1/mindmap/generate` | POST | 生成思维导图 |
| `/api/v1/export` | POST | 导出产物 |
| `/api/v1/qa/ask` | POST | 智能问答 |
| `/api/v1/sessions` | GET | 列出所有会话 |
| `/api/v1/sessions/{session_id}` | GET | 获取会话详情 |

---

## 高级用法

### 风格策略自定义

9 种笔记风格由 `app/modules/note/style_policies.py` 定义。你可以:

1. 调整现有策略的参数 (如术语密度、句式长度)
2. 添加新的风格组合
3. 为特定学科定制专属风格

详见 [风格策略文档](doc/功能实现文档（Feature Implementation Doc）.md)。

### 批量处理

使用脚本批量上传和处理多个课件:

```python
import requests

files = ["lecture1.pdf", "lecture2.pdf", "lecture3.pdf"]
for file_path in files:
    with open(file_path, "rb") as f:
        response = requests.post(
            "http://localhost:8000/api/v1/files",
            files={"file": f},
            data={"title": file_path.stem}
        )
        session_id = response.json()["session_id"]
        # 继续后续处理...
```

### 前端集成

前端通过 `ui/src/api/client.ts` 与后端交互。核心功能包括:

- 文件拖拽上传
- 实时进度显示 (SSE 流)
- 章节树展示与导航
- 在线预览与编辑
- 浮动问答窗口

---

## 常见问题

**Q: 支持哪些文件格式?**  
A: 目前支持 `.pptx` 和 `.pdf` 格式的课件。

**Q: 生成笔记需要多长时间?**  
A: 通常 2-5 分钟,具体取决于课件页数和选择的风格。你可以通过任务 ID 实时查询进度。

**Q: 可以修改生成的笔记吗?**  
A: 可以。导出为 Markdown 后可在任何文本编辑器中修改,或在前端界面直接编辑部分内容。

**Q: 如何提高问答准确性?**  
A: 问答基于 RAG 检索,确保大纲和笔记生成完整。调整 `config.yaml` 中的 `chunk.max_tokens` 可以优化检索粒度。

**Q: 支持其他语言吗?**  
A: 系统主要针对中文和英文课件优化,其他语言可能效果不佳。

---

## 贡献与支持

欢迎提交 Issue 和 Pull Request!

如有问题或建议,请查阅 `doc/` 目录下的详细文档或联系项目维护者。

---

## 许可证

本项目遵循 MIT 许可证。详见 LICENSE 文件。

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
        -d '{"session_id":"...","outline_tree_id":"auto","style":{"detail_level":"medium","difficulty":"explanatory","language":"zh"},"language":"zh"}'
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
| `POST /api/v1/notes/generate` | 结构化笔记（9 风格） | `{ session_id, outline_tree_id, style, language? }` | `{ note_doc_id, note_doc }` |
| `POST /api/v1/cards/generate` | 知识卡片 | `{ session_id, note_doc_id }` | `{ cards_id, cards }` |
| `POST /api/v1/mock/generate` | 模拟试题 | `{ session_id, note_doc_id, options }` | `{ paper_id, paper }` |
| `POST /api/v1/mindmap/generate` | 思维导图 | `{ session_id, outline_tree_id }` | `{ graph_id, graph }` |
| `POST /api/v1/export` | 导出产物 | `{ session_id, target_id, type, format }` | `{ download_url, filename }` |
| `POST /api/v1/qa/ask` | 浮动问答 | `{ session_id, scope, question }` | `{ answer, refs[] }` |
| `DELETE /api/v1/sessions/{session_id}` | 删除会话 | `-` | `{ deleted, session_id, released_bytes }` |

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
