# 系统交互与用户体验文档（Interaction & UX Flow Doc）

> 目的：为前端实现与代码生成工具（如 Codex）提供**可直接落地**的交互规范、页面结构、组件契约与状态流转，确保最小歧义地复现产品体验。文档仅覆盖交互与UX，不涉及业务策略与后端实现。

------

## 0. 使用范围与设计原则

- **目标任务**：把课件转换为多形态学习资料（结构化笔记＝9种风格组合、知识卡、模拟试题、思维导图），支持页面式还原与悬浮问答。
- **交互原则**：
  1. **三步即达**：上传 → 设定 → 生成/导出；
  2. **可控可见**：风格滑档所见即所得；
  3. **不中断学习**：问答悬浮球不遮挡主内容；
  4. **强状态反馈**：进度、错误、局部重试、回滚清晰；
  5. **无障碍优先**：键盘可达、对比度达标、读屏友好。

------

## 1. 信息架构（IA）

```
/ (Dashboard)
  ├─ New Session（新建会话：上传）
  ├─ Session/{id}
  │   ├─ Workspace（工作台）
  │   │   ├─ Notes 视图（结构化笔记）
  │   │   ├─ Cards 视图（知识卡片）
  │   │   ├─ Mock 视图（模拟试题）
  │   │   └─ MindMap 视图（思维导图）
  │   └─ Export（导出对话框）
  └─ Settings（可选）
```

- **入口页**：最近会话列表 + “新建会话”按钮
- **工作台**：左侧 TOC/导航，中间内容画布，右侧**风格滑档面板**与**生成/导出**操作
- **悬浮问答**：右下角 FAB，点击拉起侧边抽屉（Drawer）

------

## 2. 关键用户旅程（User Journeys）

### 2.1 新建会话与生成首版笔记

1. **上传**：选择 `.pptx` 或 `.pdf` → 解析进度条（页数/剩余秒）
2. **设定**：在右侧“风格面板”选择
   - 详略：简略 / 中等 / 详细（单选滑档）
   - 表达：通俗易懂 / 中等 / 深刻（单选滑档）
   - 模板勾选：结构化笔记（默认必选）、知识卡、模拟试题、思维导图
3. **生成**：点击“生成” → 顶部进度条 + Skeleton 占位
4. **预览**：默认进入 Notes 视图，左侧 TOC 同步定位；图片/公式保留版式并带说明
5. **可选**：切换风格（即刻重生）、导出

**验收**：用户无需离开工作台即可完成一次“上传→设定→生成→预览”。

------

### 2.2 风格切换与再生成（9 组合）

- 用户在右侧同时切换两条滑档
- **约束**：章节结构与TOC不变，仅内容密度/语气/举例变化
- 顶部出现“最近生成记录”面包屑（可一键回退上一版）
- 支持**局部重生**：在章节标题右侧点“仅重生本节”

**验收**：切换 9 组合，TOC 锚点稳定；重生仅刷新受影响区域，不闪烁其他内容。

------

### 2.3 知识卡 / 模拟试题 / 思维导图生成

- **Cards**：按章节批量生成卡片；卡片支持翻面（概念↔例题）
- **Mock**：选择章节/整卷 + 题量 + 难度；生成后支持“隐藏答案/显示答案”；答题结果（可选存本地）
- **MindMap**：自动生成树；节点可折叠/展开；点击节点跳转到笔记对应锚点

**验收**：三类视图在同一工作台页签切换，无需页面跳转；导出入口统一。

------

### 2.4 悬浮问答（Explain / Quiz）

- 右下 FAB → 抽屉
- **Explain**：输入问题，回答区展示文本 + 来源锚点（可跳转）
- **Quiz**：系统按当前章节出 3–5 题小测，用户可作答、查看解析

**验收**：抽屉层级不遮挡顶部导航与主要操作按钮，ESC 关闭。

------

### 2.5 导出

- 点击“导出”→ Modal
- 可选择导出对象（Notes / Cards / Mock / MindMap）与格式（MD / PDF / PNG）
- 生成完成后提供文件名与下载按钮；失败给出重试与“仅导出已完成部分”选项

**验收**：导出后返回工作台，滚动位置与折叠状态保持。

------

## 3. 页面规格（Screen Specs）

### 3.1 Dashboard（仪表盘）

- **区域**
  - Header：产品名、创建新会话按钮
  - Recent：卡片列表（标题、页数、上次修改时间、状态）
- **交互**
  - 卡片点击进入工作台
  - 新建按钮进入上传页
- **空状态**
  - 插画 + “把你的PPT拖进来，马上生成第一版笔记”
- **反馈**
  - 最近失败会话显示“可从解析阶段重试”标签

### 3.2 Upload（上传/解析）

- **Dropzone**：拖拽/点击上传
- **校验**：类型、大小、页数
- **进度**：多段式进度条（上传→解析→版式还原）
- **错误**：页级失败以“跳过N页”提示，继续进入工作台

### 3.3 Workspace（工作台）

- **布局**：
  - 左：TOC（章节树，搜索框）
  - 中：Content（内容画布，支持段落/图片/公式块）
  - 右：控件面板（风格、模板、生成/导出、历史版本）
- **右侧面板内容**
  - 风格滑档A：详略（简略/中等/详细）
  - 风格滑档B：表达（通俗易懂/中等/深刻）
  - 模板勾选：Cards / Mock / MindMap
  - 操作：生成、导出、回退上一版、局部重生
  - 历史：最近3版记录（时间戳 + 风格标签）
- **内容画布交互**
  - 段落悬停 → “编辑”/“仅重生本段”
  - 图片/公式：点击查看大图/公式LaTeX；首处展示“目的说明”
  - 锚点跳转：点击 TOC 节点或问答来源直达
- **加载与占位**
  - 首次生成：全局 Skeleton
  - 局部重生：段落内 Skeleton，不影响整页滚动
- **错误与恢复**
  - 某段失败 → 在段落位置显示内联错误条 & “重试”
  - 批量失败 → 顶部横幅 + “从上一次成功阶段恢复”按钮
  - 恢复后保留用户的手动编辑（仅重写缺失部分）

### 3.4 Cards 视图

- **布局**：卡片网格（响应式：≥1200px 3列，≥768px 2列）
- **卡片元素**：概念 → 翻面 → 例题/答案
- **筛选**：按章节、按标签（核心/易错）
- **导出**：全选/按章节导出 PDF

### 3.5 Mock 视图

- **设置条**：模式（章节/整卷）、题量（步进器）、难度（低/中/高）、生成按钮
- **试卷**：题干 + 选项/填空/简答框，折叠“解析/关键点”
- **答题模式**：
  - 练习（逐题显示解析）
  - 模拟考试（统一交卷再显示）

### 3.6 MindMap 视图

- **画布**：中点为课程标题，向外放射/树形
- **交互**：拖拽、缩放（Ctrl/⌘ + 滚轮）、节点展开/收缩、节点点击跳转
- **导出**：PNG；可选“深浅主题”

### 3.7 Q&A Drawer（问答抽屉）

- **入口**：右下 FAB（24–28px，含“问”图标），悬停提示“学习助手”
- **模式**：Explain / Quiz 标签页
- **Explain**：输入框 + 回答区（附来源锚点）
- **Quiz**：生成3–5题；展示正确率与复习建议

------

## 4. 组件清单与契约（Component Inventory & Props）

> 所有组件需提供：`aria-*` 属性、`data-testid`、键盘可达（Tab/Shift+Tab）、受控/非受控两种用法。

### 4.1 FileUploader

- **Props**：`accept=['.pptx','.pdf']` `maxSizeMB=100` `onUpload(file)`
- **States**：`idle/uploading/success/error`
- **Errors**：`E_FILE_TOO_LARGE`、`E_TYPE_UNSUPPORTED`

### 4.2 ProgressBar (Segmented)

- **Props**：`segments=[{label, value}]`、`indeterminate`
- **Usage**：上传→解析→还原 三段进度

### 4.3 StylePanel（风格面板）

- **Props**：
  - `detailLevel: 'brief'|'medium'|'detailed'`
  - `expressionLevel: 'popular'|'standard'|'insightful'`
  - `onChange({detailLevel, expressionLevel})`
- **UI**：两条滑档 + 当前组合Tag（如“中等×深刻”）

### 4.4 TemplateSelector

- **Props**：`values: {notes: true, cards: false, mock: false, mindmap: false}`
- **Rule**：notes 固定开启；其他可选

### 4.5 TocTree（章节树）

- **Props**：`items=[{id,title,level,active}]` `onSelect(id)` `searchTerm`
- **Behavior**：选中高亮、自动滚动到可视范围、过滤与高亮命中词

### 4.6 ContentBlock

- **Types**：`paragraph | image | formula | table`
- **Common Props**：`id` `anchors[]` `editable` `onRegenerate(id)`
- **Image Props**：`src` `caption` `onZoom()`
- **Formula Props**：`latex` `caption` `onCopyLatex()`

### 4.7 HistoryBar

- **Props**：`items=[{id,timestamp,detail,expression}]` `onRevert(id)`
- **Rule**：最多显示最近3版

### 4.8 ExportModal

- **Props**：`targets=['notes','cards','mock','mindmap']` `format='md|pdf|png'` `onExport()`
- **Feedback**：导出进度 + 完成后展示文件名与下载

### 4.9 QaFab & QaDrawer

- **Fab Props**：`position='bottom-right'` `tooltip='学习助手'`
- **Drawer Props**：`mode='explain|quiz'` `onAsk(q)` `onGenerateQuiz(chapterId?)`

------

## 5. 状态与反馈（States & Feedback）

| 场景     | 视觉反馈                  | 行为                   |
| -------- | ------------------------- | ---------------------- |
| 全局生成 | 顶部进度条 + Skeleton     | 禁用风格滑档与生成按钮 |
| 局部重生 | 段落内 Skeleton           | 其他区域可交互         |
| 单段失败 | 红色内联错误条 + 重试按钮 | 展开“错误详情”         |
| 批量失败 | 顶部横幅                  | “从最近成功阶段恢复”   |
| 导出成功 | Toast + 下载按钮          | 记录导出历史           |
| 导出失败 | Modal 提示 + 重试         | “仅导出已完成部分”     |

**文案（建议）：**

- 解析中… 已完成 {done}/{total} 页
- 版式还原中… 请稍候
- 本节生成失败，已保留原内容（错误代码：{code}）
- 已回到上一次成功的版本

------

## 6. 交互细节与可用性（Usability）

- **键盘**：
  - 全局：`/` 聚焦 TOC 搜索；`g g` 跳到顶部；`Shift+g` 底部
  - Drawer：`Esc` 关闭；`Ctrl/⌘ + Enter` 发送提问
- **滚动同步**：TOC 与内容双向联动（Intersection Observer）
- **可编辑**：段落内轻量编辑（不跨段），重生不覆盖已手动编辑的内容
- **留白与排版**：正文行高 1.6–1.8；每节前后留白 ≥ 16px；列表项间距 8–12px
- **阅读模式**：宽屏中栏宽度 720–820px，避免长行疲劳
- **动画**：Skeleton、淡入淡出 120–180ms，避免跳变

------

## 7. 无障碍与国际化（A11y & i18n）

- **对比度**：正文与交互控件对比度 ≥ 4.5:1
- **ARIA**：树组件 `role="tree"`/`treeitem"`；抽屉 `aria-modal="true"`
- **焦点管理**：Modal/Drawer 打开后将焦点置于首个可交互元素
- **读屏**：图片/公式均提供 `alt` 与可复制的公式文本
- **语言**：中/英切换；数字/时间戳本地化；文案全部集中在 `i18n.json`

------

## 8. 遥测与埋点（可选但推荐）

- **关键事件**：`upload_start/success/fail`、`generate_start/success/fail`、`style_change`、`section_regen`、`export_start/success/fail`、`qa_open/ask/quiz_submit`
- **性能指标**：首次可读（Notes 首屏）时间、局部重生P95、导出完成时间
- **错误聚合**：按阶段分桶（解析/还原/生成/导出）

------

## 9. 断点与响应式（Responsive）

- **≥1440px**：三栏（TOC 280 / Content 820 / Panel 340）
- **≥1024px**：两栏（TOC 折叠为抽屉；Panel 固定）
- **≤768px**：单栏（底部 Tab 切换 Notes/Cards/Mock/MindMap；Panel 折叠为底部抽屉；FAB 保留）

------

## 10. 验收清单（Front-End Acceptance）

-  **三步闭环**：上传→设定→生成，在单页面完成
-  **九种风格**：切换不改变 TOC/锚点；仅密度/语气/举例变化
-  **页式还原**：图片与公式在首次出现处带 1 句“目的说明”
-  **局部重生**：仅刷新目标段落；光标位置不跳变
-  **多视图一致**：Cards / Mock / MindMap 与 Notes 共用同一会话数据
-  **导出**：提供 MD/PDF/PNG，失败可“仅导出已完成部分”
-  **问答**：抽屉含来源锚点跳转；Quiz 有正确率与复习建议
-  **A11y**：主要流程可全键盘完成；读屏读到锚点与标题层级
-  **性能**：Notes 首屏在生成完成后 ≤ 300ms 呈现（有 Skeleton 过渡）

------

## 11. 交付物与文件组织（前端）

```
/ui
  /pages
    dashboard.tsx
    session/[id]/workspace.tsx
  /components
    FileUploader.tsx
    ProgressBar.tsx
    StylePanel.tsx
    TemplateSelector.tsx
    TocTree.tsx
    ContentBlock/
      Paragraph.tsx
      Image.tsx
      Formula.tsx
      Table.tsx
    HistoryBar.tsx
    ExportModal.tsx
    QaFab.tsx
    QaDrawer.tsx
  /hooks
    useSessionState.ts
    useScrollSync.ts
    useSectionRegen.ts
  /styles
    tokens.css (颜色/间距/阴影)
  /i18n
    zh.json
    en.json
  /tests
    *.spec.tsx
```