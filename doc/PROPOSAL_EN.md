## Project Proposal: StudyCompanion — An Intelligent Learning Agent for University Students

### Team Information

**Members**:

| Name | Student ID |
|------|------------|
| Xu Liang | 3036658279 |
| Meng Xiangchen | 3036655057 |
| He Shijing | 3036655746 |
| Cao Jiarui | 3036655045 |
| Zhou Chendi | 3036658176 |
| Zhang Qingyang | 3036658152 |

------

### I. Background and Problem Definition

In university classrooms, students often face two types of difficulties:

1. **Understanding Lag**: Course content is knowledge-intensive with high domain barriers. Students may struggle to follow the instructor's pace in real-time due to lack of prior knowledge or fast-paced lectures.
2. **Inefficient Review**: When facing hundreds of pages of PowerPoint slides during final exams, it is difficult to clarify the knowledge structure, grasp key points, resulting in high review costs and poor systematization.

Although existing large language models can answer questions, they have three main limitations:

- Unable to generate structured, reusable learning materials;
- Uncontrollable output style, difficult to maintain consistent teaching logic;
- When context becomes too long, they tend to deviate from course content, affecting accuracy.

The goal of **StudyCompanion** is: after students upload course PowerPoint slides, the Agent can automatically generate structured, clearly-layered, language-controllable learning materials, helping students learn "as if having a teacher explaining alongside" during preview, lecture attendance, and review.

------

### II. System Design Overview

### System Modules and Overall Workflow

**1) Frontend (Web UI)**
- Technology: Streamlit + Custom CSS.
- Features: Provides entry points for PPT upload, template selection, difficulty and detail level adjustment, real-time progress display, and allows users to view and edit notes online. Users can switch between different templates (detailed explanation, brief summary, mind map, knowledge cards, etc.) on the page. Provides a chatbot for real-time Q&A based on notes. Supports exporting final results as Markdown or PDF files.

**2) Backend (Agent Service Layer)**
- Technology: LangGraph (workflow orchestration), LangChain (RAG and model interface).
- Framework: Streamlit (integrates frontend and backend logic, simplifies deployment process).
- Features: Responsible for PPT parsing, OCR recognition, chunking and retrieval, content generation and asset embedding.

**3) Database (RAG Storage Layer)**
- Function: Processes PPT content into a structured RAG knowledge base, serving as the AI learning assistant's "course memory", supporting subsequent deep learning and intelligent Q&A functions.
- Technical Components:
  - **FAISS**: Used to build vector indexes for efficient semantic retrieval;
  - **SQLite/PostgreSQL**: Stores course metadata, chapter structure, user configuration and other structured information;
  - **Local File System**: Saves PPT screenshots, charts, formulas and other multimedia resource files.

#### Overall Workflow

1. **Upload and Parsing**: After students upload PPT, the system automatically reads the file structure, extracts titles, paragraphs and page numbers, and identifies the position of text, charts and formulas on each page. After parsing is complete, the content is saved as a hierarchical structure with coordinates for subsequent use.
2. **Recognition and Organization**: The system identifies images, tables, formulas and text content, and organizes them into an editable format. For example, tables are restored to text form, while formulas are preserved as screenshots or LaTeX expressions. This way, the generated notes can completely retain the visual structure of the original course.
3. **Content Chunking and Outline Generation**: Content is chunked according to chapter hierarchy. The system first generates a course outline, then expands the explanation content section by section. To make the output more consistent with course logic, prompts undergo multiple rounds of optimization to clarify the model's role (e.g., "course instructor") and objectives (e.g., "explain strictly in PPT order"), and control the explanation style and level of detail.
4. **Note Generation and Optimization**: The system generates explanatory text in the order of "outline → expansion → integration". Each stage automatically checks whether the logic is coherent and consistent with the outline. If off-topic or missing content is detected, the system regenerates it. Context is automatically trimmed to keep the focus clear.
5. **Asset Embedding and Export**: After generation is complete, the system embeds images, tables and formula screenshots corresponding to each page back to appropriate positions. The final learning materials support multiple templates (detailed notes, brief summaries, mind maps, etc.), and students can preview directly on the frontend or export as PDF.

------

### III. Core Features and Innovations

#### 1. Templated Learning Output

Supports five types of output formats:

- **Detailed Explanation Notes**: Page-by-page explanation, preserving formula variables, definitions and derivations;
- **Brief Summary Notes**: Extracting key terms, concepts and conclusions;
- **Mind Map**: Visualizing course knowledge as a graph;
- **Mock Exam Questions**: Generating multiple-choice, calculation and short-answer questions;
- **Knowledge Cards**: For memorizing core concepts and definitions.

#### 2. Personalized Style Adjustment

Provides two-dimensional parameters for "detail level" and "explanation difficulty":

- Detail Level: Very Detailed / Medium / Brief;
- Difficulty Level: Advanced (academic) / Medium (with explanations) / Simple (popularized).
   Users can generate different versions of notes according to their own needs, similar to "adjusting teaching tone".

#### 3. RAG Enhancement Scheme

To address the problem of "context fragmentation caused by document chunking" in traditional RAG for PPT tasks, this project adopts multiple enhancement strategies:

- **Hierarchical Chunking**: Organizes text according to chapter structure to preserve semantic hierarchy in retrieval;
- **Anchor Summaries**: Generates summary anchors for each page during chunking for cross-chunk association;
- **Dynamic Context Assembly**: Dynamically adjusts retrieval scope according to outline hierarchy;
- **Staged Prompt Planning**: First generates structural skeleton, then fills in details, reducing the risk of going off-topic.

These methods, combined with Prompt engineering, make the generated content more semantically stable and logically coherent.

------

### IV. Implementation Plan

| Stage | Timeline | Main Tasks |
| ------- | -------- | --------------------------- |
| Stage 1 | Late October | System framework and web interface setup |
| Stage 2 | Early November | Build RAG pipeline and hierarchical chunking logic |
| Stage 3 | Mid November | Template library and style adjustment feature implementation |
| Stage 4 | Late November | Case course testing and demo preparation |

------

### V. Demo and Expected Outcomes

The demonstration case will use a **COMP** course, with the demo process including:

1. Upload one lecture's PPT;
2. Generate multiple versions of study notes and mind maps;
3. Demonstrate style switching and conversational refinement effects.

**Expected Outcomes:**

- An online interactive learning Agent prototype;
- High-quality learning materials with multiple templates and controllable styles;
- A Prompt and RAG optimization framework that can be extended to other courses.
