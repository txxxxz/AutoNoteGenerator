# StudyCompanion｜功能实现文档（Feature Implementation Doc）

> 目标：为工程团队与代码生成工具（如 Codex）提供**可直接落地**的功能实现细节（输入/输出契约、规则、流程、验收），以实现“从课件到多形态学习资料”的自动化生成与导出。核心能力与工作流对齐项目提案（前端 + Agent 服务层 + 数据/RAG；上传→识别→分块→生成→导出）。
>  产物模板与风格调节（详略×难易）作为一等公民能力纳入实现。
>  分块/检索遵循“层级化分块、页级锚点摘要、按节深度动态组装、分阶段提示”的增强式 RAG 思路。

------

## 0. 文档范围与不变项

- **范围**：功能层面的输入/输出、数据契约、流程状态机、验收标准、错误码与配置。
- **不变项**（来自提案）：
  - 输出形态：**结构化笔记（9 组合风格）/ 知识卡 / 模拟试题 / 思维导图**；支持导出。
  - 工作流：**Upload & Parse → Recognize & Organize → Chunk & Outline → Generate & Refine → Embed & Export**。
  - 存储：**向量索引（FAISS）+ 关系型元数据（SQLite/PG）+ 本地资源（图表/公式截图）**。

------

## 1. 系统能力清单（Capabilities）

1. **课件解析**：读取 PPT/PDF，抽取页级结构（标题/正文/图片/公式/表格）。
2. **页面式还原**：保留“文字+图片+公式”的页面布局；图片/公式附说明。
3. **分块与大纲**：章节优先的层级分块；节点生成“锚点摘要”。
4. **结构化笔记**：两条滑档——详略（简/中/详）×难易（简单/讲解/学术）＝ 9 种组合。
5. **模板产物**：知识卡片、模拟试题、思维导图/知识树。
6. **导出**：Markdown / PDF /（导图）图片等多格式。
7. **悬浮问答**：对当前课程产物进行问答/抽测，不打断主流程（悬浮球唤起）。

------

## 2. 端到端流程（E2E Flow）

**状态机**：`UPLOADED → PARSED → LAYOUT_BUILT → OUTLINE_READY → NOTES_READY → TEMPLATES_READY → EXPORTED`
 失败转移：任一阶段 `*_FAILED` → 支持“**从最近成功阶段重跑**”。

------

## 3. 模块实现规格（按功能分解）

> 统一约定：所有接口返回均含 `request_id`、`status`、`error`（可空）、`metrics`（可空）。
>  字段类型：`str | int | float | bool | array | object | uri | enum`。

### 3.1 课件解析（Slide Parser）

**目标**：将 PPT/PDF 转为页→区块的结构化表示，形成后续一切能力的“骨架”。（对应 “Upload & Parse”）

**输入**

- `file_id: str`（上传后返回）
- `file_type: enum["pptx","pdf"]`

**输出（核心契约）**

```json
{
  "doc_meta": { "title": "str", "pages": 42 },
  "slides": [
    {
      "page_no": 1,
      "blocks": [
        { "id":"b1","type":"title","order":0,"bbox":[x,y,w,h],"raw_text":"..." },
        { "id":"b2","type":"text","order":1,"bbox":[...],"raw_text":"..." },
        { "id":"b3","type":"image","order":2,"bbox":[...],"asset_uri":"uri" },
        { "id":"b4","type":"formula","order":3,"bbox":[...],"raw_text":"E=mc^2" },
        { "id":"b5","type":"table","order":4,"bbox":[...],"asset_uri":"uri" }
      ]
    }
  ]
}
```

**业务规则**

- 页序与块内 `order` 必须保持**阅读顺序**。
- 类型集合固定：`title|text|image|formula|table`。
- 表格/图片仅保存**资源引用**，不做语义化（由后续模块处理）。

**验收**

- 解析成功率 ≥ 99%（对可支持的文件）。
- 遇到异常页：其余页面可继续解析并产出（页级容错）。

------

### 3.2 页面式还原（Layout Reconstruction & OCR）

**目标**：按页面保持“文字+图片+公式”的布局；为图片/公式生成说明（caption）。

**输入**

- `slides[]`（来自解析）

**输出（核心契约）**

```json
{
  "layout_doc": {
    "pages": [
      {
        "page_no": 1,
        "elements": [
          { "ref":"b2", "kind":"text", "content":"..." },
          { "ref":"b3", "kind":"image", "image_uri":"uri", "caption":"..." },
          { "ref":"b4", "kind":"formula", "latex":"E=mc^2", "caption":"..." }
        ]
      }
    ]
  }
}
```

**业务规则**

- **同页顺序**遵循解析阶段 `order`。
- 图片/表格一律以**截图 URI** 引用；公式以 **LaTeX** 表示。
- 所有图片/公式**必须**生成“简短说明”（caption），用于后续讲解/卡片。

**验收**

- 图片、公式占位与顺序与原页一致（容差：允许字号/间距变化）。
- 图片/公式说明**非空**；不足将回退为空字符串并记录 warning。

------

### 3.3 分块与大纲（Chunk & Outline）

**目标**：产出“**章节优先**”的知识树，避免语义断裂；节点自带“锚点摘要”。

**输入**

- `layout_doc`

**输出（核心契约）**

```json
{
  "outline_tree": {
    "root": {
      "title": "Course Title",
      "children": [
        {
          "section_id":"s1",
          "title":"Chapter 1",
          "summary":"<= 60 words",
          "anchors":[{"page":1,"ref":"b2"}],
          "children":[
            { "section_id":"s1.1", "title":"Topic A", "summary":"...", "anchors":[...] }
          ]
        }
      ]
    }
  }
}
```

**业务规则**

- 深度 `root → chapter → topic → bullet`（最多 4 层，平衡可读性）。
- 每个节点**必须**有 `summary`（锚点摘要，30–60 词）。
- `anchors[]` 记录该节点溯源（页号 + 区块引用），为导出与问答提供精确映射。

**验收**

- 节点覆盖 ≥ 95% 的信息密集页；章节顺序与课件一致。
- 对无明显结构的文档，退化为“页→块”两层树并标注 `structure="flat"`。

------

### 3.4 结构化笔记（Structured Notes，9 组合）

**目标**：以**两条滑档**控制输出风格：详略（`brief|medium|detailed`）× 难易（`simple|explanatory|academic`）。

**输入**

- `outline_tree`
- `style.detail_level` ∈ {brief, medium, detailed}
- `style.difficulty` ∈ {simple, explanatory, academic}

**输出（核心契约）**

```json
{
  "note_doc": {
    "style": { "detail_level":"medium", "difficulty":"academic" },
    "toc": [{ "section_id":"s1", "title":"..." }],
    "sections": [
      {
        "section_id":"s1",
        "title":"Chapter 1",
        "body_md":"markdown text ...",
        "figures":[{ "image_uri":"uri", "caption":"..." }],
        "equations":[{ "latex":"...", "caption":"..." }],
        "refs": ["anchor:s1@page1#b2"]
      }
    ]
  }
}
```

#### 维度与取值

- **详略程度（detail_level）**：`brief`（简略）｜`medium`（中等）｜`detailed`（详细）
- **表达层级（expression_level）**：`popular`（通俗易懂/科普语气，类比、两句话内能懂）｜`standard`（中等/正常讲解）｜`insightful`（深刻/正常讲解+部分学术表达）

> 所有输出保持**相同的章节/小节骨架**；风格只影响篇幅、术语密度、举例/推导的深度与语气。

#### 详略维度映射（Detail Axis）

| 指标                     | `brief` 简略     | `medium` 中等        | `detailed` 详细                 |
| ------------------------ | ---------------- | -------------------- | ------------------------------- |
| **篇幅系数**（相对基线） | 0.6–0.8×         | 0.9–1.1×             | 1.4–1.7×                        |
| **举例数/小节**          | 0                | 1                    | 2–3                             |
| **是否强制小结**         | 可省略           | 必须（1–2 句）       | 必须（2–4 句，含要点清单）      |
| **列表 vs 段落**         | 列表优先（≤4条） | 平衡                 | 段落优先（配列表）              |
| **图表/公式说明**        | 1 句目的         | 1–2 句目的+用法      | 2–4 句目的/背景/边界            |
| **可包含内容**           | 结论、关键定义   | 结论、定义、基本理由 | 结论、定义、推导要点、反例/边界 |

#### 表达层级映射（Expression Axis）

| 指标                        | `popular` 通俗易懂                                           | `standard` 中等                  | `insightful` 深刻                                       |
| --------------------------- | ------------------------------------------------------------ | -------------------------------- | ------------------------------------------------------- |
| **术语密度**（术语/100 词） | ≤2                                                           | 3–6                              | 6–10                                                    |
| **平均句长**（中文词）      | 8–14                                                         | 12–20                            | 16–24                                                   |
| **语气/修辞**               | 科普口吻、**必须**有类比（每小节 1 次）；两句内先给“人话结论” | 教学口吻、直接解释、少比喻       | 半学术口吻；适度术语与逻辑连接词（因此/从而/在…条件下） |
| **公式呈现**                | 尽量延后，先文字再给 1 个核心式                              | 正文内 1–2 个必要式，附 1 句目的 | 可含 2–3 个式子与**变量表**（符号=含义）                |
| **变量定义**                | 仅关键变量                                                   | 关键变量+必要符号                | **变量表**（符号、名称、单位/域）                       |
| **引用/约束**               | 不要求                                                       | 建议给出 1 个适用边界            | **必须**写出适用条件与限制 1–2 条                       |
| **禁忌**                    | 长句、术语堆砌、未落地的结论                                 | 过多比喻或口语化                 | 空话、过度铺陈、无约束的“普遍成立”                      |

#### 组合规则与冲突处理

- **总原则**：**骨架不变**（章节与层级），风格影响“密度与语气”。
- **冲突优先级**（从高到低）：**篇幅约束 > 结论可读性 > 公式/推导深度 > 修辞**。
  - 例：`brief + insightful` → 允许学术表达但**严格控长**；保留 1 个关键公式并配 1 句目的。
- **类比频率**：仅 `popular` 强制开启；`standard` 可选，`insightful` 默认关闭（除非能显著澄清概念）。
- **图表/公式说明**：无论组合如何，**首次出现处**必须给“1 句目的”。

#### 9 组合“风格预设矩阵”（可直接落实现）

| 组合                  | 典型用途                 | 关键开关                                               |
| --------------------- | ------------------------ | ------------------------------------------------------ |
| `brief+popular`       | 极速扫盲/考前 5 分钟回顾 | 长度 0.6–0.7×；每小节首两句“人话结论+类比”；无推导     |
| `brief+standard`      | 课后速览                 | 长度 0.7–0.8×；1 句小结；1 句公式目的                  |
| `brief+insightful`    | 领导/评审快速理解要点    | 长度 0.7–0.8×；学术连接词 + 1 个必要公式；1 条适用条件 |
| `medium+popular`      | 初学者导读               | 常见误区 1 条；每小节 1 个类比；1–2 句目的             |
| `medium+standard`     | 常规复习版（默认）       | 举例=1；小结=必有；术语中密度                          |
| `medium+insightful`   | 研究生课程笔记           | 变量表（精简版）；边界 1 条；必要推导 1–2 步           |
| `detailed+popular`    | 跨学科讲解               | 2–3 个案例；复杂概念拆分；限制类比不滥用               |
| `detailed+standard`   | 期末总复习完整版         | 2–3 举例；每节小结 2–4 句；图表说明充分                |
| `detailed+insightful` | 深度学习/备论文          | 变量表+边界 2 条；2–3 个核心式；必要反例或对比         |

#### Prompt 开关与占位

**请求参数（示例）**

```
{
  "style": {
    "detail_level": "medium",
    "expression_level": "insightful"
  }
}
```

**风格策略（可内置于模板引擎）**

```
{
  "detail_policies": {
    "brief":   { "length_mult": 0.7, "examples": 0, "summary": "optional", "figure_caption": "1sent" },
    "medium":  { "length_mult": 1.0, "examples": 1, "summary": "required", "figure_caption": "1-2sent" },
    "detailed":{ "length_mult": 1.6, "examples": 2, "summary": "required+", "figure_caption": "2-4sent" }
  },
  "expression_policies": {
    "popular":    { "jargon_per_100": 2, "avg_sent_len": [8,14],  "analogy": "required", "equations": "min" },
    "standard":   { "jargon_per_100": [3,6], "avg_sent_len": [12,20], "analogy": "optional", "equations": "normal" },
    "insightful": { "jargon_per_100": [6,10], "avg_sent_len": [16,24], "analogy": "off", "equations": "rich", "constraints": "required" }
  }
}
```

**模板占位符**

```
{detail_level} {expression_level}
{length_mult} {examples} {summary_requirement}
{analogy_directive}  // 必须/可选/关闭
{equation_policy}    // min/normal/rich
{constraints_policy} // none/optional/required
{variable_table}     // none/brief/full
```

####  验收与自动化校验（Testable Criteria）

- **篇幅**：成品字数 / 基线字数 ∈ `length_mult` 区间（容差 ±10%）。
- **举例数**：按小节统计“例如/比如/案例/Case”等触发词或“示例段落”标记，符合目标值（容差 ±1）。
- **术语密度**：基于术语表或大写/公式符号统计，满足目标区间。
- **平均句长**：中文分词后统计，落在目标区间。
- **小结/目的句**：每小节末尾**必须**存在“总结/小结/要点/因此/所以”等触发的 1–4 句；每个公式/图首次出现前后**必须**出现“目的/含义”句。
- **变量表/边界**（`insightful`）：至少 1 处“变量—含义”对；至少 1 条“适用条件/限制”。
- **类比**（`popular`）：每小节至少 1 处“像…就像…/可以把…看作…”等模式。

#### 默认配置（config 片段，可落库）

```
style:
  default:
    detail_level: medium
    expression_level: standard
  limits:
    length_tolerance: 0.10
    examples_tolerance: 1
  mapping:
    detail:
      brief:    { length_mult: 0.7, examples: 0, summary: optional, figure_caption: "1sent" }
      medium:   { length_mult: 1.0, examples: 1, summary: required, figure_caption: "1-2sent" }
      detailed: { length_mult: 1.6, examples: 3, summary: required_plus, figure_caption: "2-4sent" }
    expression:
      popular:    { jargon_per_100: 2,   avg_sent_len: [8,14],  analogy: required,  equations: min,     variable_table: none,  constraints: none }
      standard:   { jargon_per_100: [3,6], avg_sent_len: [12,20], analogy: optional, equations: normal, variable_table: brief, constraints: optional }
      insightful: { jargon_per_100: [6,10], avg_sent_len: [16,24], analogy: off,     equations: rich,   variable_table: full,  constraints: required }
```

------

### 3.5 模板产物（Template Suite）

#### 3.5.1 知识卡片（Knowledge Cards）

**输入**：`note_doc`
 **输出**

```json
{
  "cards": [
    {
      "concept":"Overfitting",
      "definition":"<=60 words",
      "exam_points":["...","..."],
      "example_q":{"stem":"...","answer":"...","key_points":["..."]},
      "anchors":["section:s2.1"]
    }
  ]
}
```

**规则**：每卡 80–180 词；`exam_points` 1–3 条；可引用 `note_doc.sections[*]`。
 **验收**：术语一致；卡片集覆盖课程核心概念（≥ 85% 的章节）。

#### 3.5.2 模拟试题（Mock Exam）

**输入**：`note_doc`；选项 `{ mode:"chapter|full", size:int, difficulty:"low|mid|high" }`
 **输出**

```json
{
  "paper": {
    "meta": { "mode":"full", "size":30, "difficulty":"mid" },
    "items":[
      { "id":"q1","type":"mcq","stem":"...","options":["A","B","C","D"],"answer":"B","explain":"..." },
      { "id":"q2","type":"fill","stem":"...","answer":"...", "explain":"..." },
      { "id":"q3","type":"short","stem":"...","answer":"...", "key_points":["..."] }
    ]
  }
}
```

**规则**：

- `mcq:fill:short` 比例默认 `5:3:2`；章节平衡（`chapter` 模式仅取该章）。
- 每题**必须**有 `explain` 或 `key_points`。
   **验收**：答案唯一且与讲义一致性通过抽样校验（10%）。

#### 3.5.3 思维导图/知识树（Mind Map）

**输入**：`outline_tree`
 **输出**

```json
{
  "graph": {
    "nodes":[{"id":"s1","label":"Chapter 1","level":1}],
    "edges":[{"from":"s1","to":"s1.1","type":"hierarchy"}]
  }
}
```

**规则**：

- `level` = 深度；`type` 固定 `hierarchy`。
- 节点可折叠；节点点击应能定位至 `note_doc.sections[section_id]`。
   **验收**：节点/边数量与 `outline_tree` 一致；节点跳转正确。

------

### 3.6 导出（Exporter）

**输入**：`note_doc | cards | paper | graph`，`format: "md|pdf|png"`
 **输出**

```json
{ "download_url":"uri", "filename":"Course_Title_Notes_v1.pdf" }
```

**规则**

- Markdown：保留标题层级（`#..####`）、图片 `![]()`、公式 `$...$`/`$$...$$`。
- PDF：自动生成目录与页眉；锚点与页码对齐。
- PNG：限导图 `graph`。
   **验收**：导出失败率 < 1%；PDF 目录锚点可点击跳转。

------

### 3.7 悬浮问答（Floating Q&A）

**输入**：`question`, `scope:"notes|cards|mock"`, `session_id`
 **输出**

```json
{ "answer":"...", "refs":["section:s3.2","anchor:s1@page3#b8"] }
```

**规则**

- 仅在**当前课程会话**内检索与作答；返回 `refs` 以便定位材料来源。
   **验收**：随机抽样问答的引用命中率 ≥ 90%。

------

## 4. API 设计（摘要）

> 统一前缀：`/api/v1`；鉴权略。所有 `POST` 请求体为 JSON。

| 功能     | 方法 | 路径                | 请求要点                          | 响应要点               |
| -------- | ---- | ------------------- | --------------------------------- | ---------------------- |
| 上传文件 | POST | `/files`            | `{ name, content_base64 }`        | `{ file_id }`          |
| 解析     | POST | `/parse`            | `{ file_id, file_type }`          | `{ doc_meta, slides }` |
| 还原     | POST | `/layout/build`     | `{ file_id }`                     | `{ layout_doc }`       |
| 大纲     | POST | `/outline/build`    | `{ layout_doc }`                  | `{ outline_tree }`     |
| 笔记     | POST | `/notes/generate`   | `{ outline_tree_id, style }`      | `{ note_doc_id }`      |
| 卡片     | POST | `/cards/generate`   | `{ note_doc_id }`                 | `{ cards_id }`         |
| 模拟题   | POST | `/mock/generate`    | `{ note_doc_id, options }`        | `{ paper_id }`         |
| 导图     | POST | `/mindmap/generate` | `{ outline_tree_id }`             | `{ graph_id }`         |
| 导出     | POST | `/export`           | `{ target_id, type, format }`     | `{ download_url }`     |
| 问答     | POST | `/qa/ask`           | `{ session_id, question, scope }` | `{ answer, refs }`     |

------

## 5. 数据模型（摘要）

> 关系表 + 资源与向量索引（与提案的“FAISS + SQLite/PG + 本地资源”一致）。

**核心表**

- `course_session(id, title, created_at, user_id, file_id, status)`
- `slide(id, course_session_id, page_no, meta_json)`
- `block(id, slide_id, type, order, bbox_json, raw_text, asset_uri, latex)`
- `outline_node(id, course_session_id, parent_id, title, summary, anchors_json, level, order)`
- `note_doc(id, course_session_id, style_detail, style_difficulty, content_md, toc_json)`
- `cards(id, course_session_id, json)` / `mock_paper(id, course_session_id, json)` / `mindmap_graph(id, course_session_id, json)`

**索引（向量库）**

- `idx_course_session(course_session_id, chunk_id, text, embedding)`

------

## 6. 配置与参数（config.yaml 示例）

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
  md:
    math_block: true
rag:
  chunk:
    max_tokens: 500
    overlap: 50
```

------

## 7. 错误码（Error Codes）

| code                        | 场景                  | 提示                             |
| --------------------------- | --------------------- | -------------------------------- |
| `E_FILE_UNSUPPORTED`        | 不支持的文件类型/损坏 | 请上传 .pptx 或 .pdf             |
| `E_PARSE_PAGE_FAIL`         | 某页解析失败          | 第 N 页解析失败，已跳过          |
| `E_LAYOUT_RESOURCE_MISSING` | 资源引用失效          | 图片/表格资源缺失                |
| `E_OUTLINE_EMPTY`           | 未识别到结构          | 文档结构不清晰，已退化为页级结构 |
| `E_NOTES_STYLE_INVALID`     | 风格参数非法          | 详略/难易取值不合法              |
| `E_EXPORT_FAIL`             | 导出失败              | 请重试或更换格式                 |

------

## 8. 验收标准（Acceptance）

**主流程**

- 上传→笔记首版生成 ≤ 120s（30–80 页课程）。
- 切换 9 种风格组合，`toc` 不变、正文密度差异可量化（±20% 容差）。
- 导出 PDF 含目录锚点；导图 PNG 清晰可读。

**产物一致性**

- 知识卡覆盖核心概念（≥ 85% 章节）。
- 模拟试题答案唯一、能由笔记溯源（题干 `refs` 命中率 ≥ 90%）。
- 问答返回包含 `refs`（章节或锚点）。

------

## 9. 用例（示例）

**UC-01 生成结构化笔记（academic × detailed）**

- Given：用户上传《线性代数》PPT（50 页）
- When：选择风格 `detailed + academic` 并点击“生成”
- Then：返回 `note_doc`，包含章节层级、公式（LaTeX）与图示说明；切换为 `brief + simple` 后，`toc` 不变，仅正文密度与语气变化。

**UC-02 生成模拟试题（chapter 模式）**

- Given：用户选中“第 3 章”并设置 `size=20`
- When：点击“生成模拟题”
- Then：返回含 20 题的试卷（mcq:fill:short≈5:3:2），附标准答案与关键点。

------

## 10. 附录 A：提示词（Prompt）占位符规范（用于代码生成）

- 全局：`{course_title}`, `{section_title}`, `{anchors}`, `{detail_level}`, `{difficulty}`
- 分阶段：
  - Outline 阶段：`{section_summaries}`, `{key_terms}`
  - Expand 阶段：`{required_examples:n}`, `{equation_policy}`
  - Integrate 阶段：`{coherence_checks}`, `{cross_refs}`

