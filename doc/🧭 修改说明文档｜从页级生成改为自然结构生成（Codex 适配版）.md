# 🧭 修改说明文档｜从页级生成改为自然结构生成（Codex 适配版）

## 0. 修改目标

将当前按页生成笔记的逻辑

> （即每页 PPT 独立 → 生成一段讲解 → 顺序拼接）

替换为

> **基于自然结构（章节 → 小节 → 知识点）** 的生成流程，
>  保证内容逻辑连贯、结构清晰，并兼容现有导出与前端 TOC 显示。

------

## 1. 受影响模块

| 模块                      | 原文件路径                                | 修改类型                          |
| ------------------------- | ----------------------------------------- | --------------------------------- |
| Structured Note Generator | `/modules/note/generate_notes.py`         | 替换核心生成逻辑                  |
| Chunk & Outline           | `/modules/chunk_outline/build_outline.py` | 增加自然结构提取                  |
| Orchestrator              | `/orchestrator/pipeline.py`               | 插入新阶段调用                    |
| Schema                    | `/schemas/note_doc.py`                    | 增加 `outline_tree_enhanced` 字段 |

------

## 2. 旧逻辑回顾

原实现为：

```
for slide in slides:
    prompt = f"请根据第 {slide.page_no} 页内容生成讲解。"
    result = llm_api(prompt)
    notes.append(result)
return "\n".join(notes)
```

问题：

1. 讲解被限制在页级，章节衔接断裂；
2. 相似页未合并，篇幅冗余；
3. 图片与公式上下文脱节。

------

## 3. 新逻辑概述

改为“两阶段 + 分层生成”模式：

1. **结构提取阶段（Outline Rebuilder）**
   - 从 layout_doc 识别标题层级与语义相似页，输出 `outline_tree_enhanced`。
2. **内容生成阶段（Section Generator）**
   - 按自然层级逐节生成讲解，每节可跨多页。
   - 在输出中插入 `[FIG_PAGE_x_IDX_y: caption]` 占位符以标识图像位置。

------

## 4. 详细修改说明

### 4.1 在 `build_outline.py` 中新增函数

```
def build_natural_outline(layout_doc):
    """
    根据 layout_doc 生成自然教学结构。
    返回 outline_tree_enhanced（章节→小节→要点）
    """
    slides = layout_doc["pages"]
    titles = extract_titles(slides)
    merged = merge_by_semantics(titles, threshold=0.8)

    outline = []
    for chap in merged:
        subtopics = infer_subtopics(chap["slides"])
        outline.append({
            "title": chap["title"],
            "children": subtopics,
            "anchors": collect_anchors(chap["slides"])
        })
    return {"root": {"children": outline}}
```

------

### 4.2 在 `generate_notes.py` 中替换生成逻辑

旧：

```
notes = [llm_api(prompt_per_page(slide)) for slide in slides]
```

新：

```
outline = build_natural_outline(layout_doc)
sections = flatten_outline(outline)

for sec in sections:
    prompt = f"""
    你是一名讲师。根据以下课程节点生成讲解：
    标题：{sec['title']}
    内容锚点：{sec['anchors']}
    要求：
    1. 承上启下；
    2. 段落连贯；
    3. 图片位置用占位符 [FIG_PAGE_x_IDX_y: caption]；
    """
    result = llm_api(prompt)
    notes.append({"section": sec["title"], "text": result})
```

------

### 4.3 在 `pipeline.py` 中注册新阶段

```
outline_doc = build_outline(layout_doc)
outline_enh = build_natural_outline(layout_doc)
note_doc = generate_notes_from_outline(outline_enh)
```

------

### 4.4 Schema 更新

在 `note_doc` 模型中增加：

```
outline_tree_enhanced: Optional[dict]
```

------

## 5. Prompt 模板建议

> 为 Codex 或 LLM 调用准备统一的 Prompt 模板：

```
系统提示（system）：
你是大学课程讲师。请根据输入的章节结构生成逻辑连贯的讲解。

用户提示（user）：
输入：
章节标题：{chapter_title}
小节要点：{key_points}
来源页：{pages}
输出要求：
- 生成完整讲解（非分页描述）
- 在提到图像/公式时，插入占位符 [FIG_PAGE_<页号>_IDX_<序号>: 说明]
- 结尾用 1–2 句总结本节核心思想
```

------

## 6. 验收标准

| 指标             | 要求                              |
| ---------------- | --------------------------------- |
| 章节合并准确率   | ≥ 90 %（人工抽样）                |
| 输出逻辑连贯度   | ≥ 85 %（人工评估）                |
| 图片占位符匹配率 | ≥ 95 %                            |
| 向后兼容性       | 原 TOC 与导出模块可直接读取新结构 |

------

## 7. 回退与兼容

- 若 `build_natural_outline()` 失败，回退到旧 `outline_tree`；
- 前端 TOC 自动根据 `outline_tree_enhanced || outline_tree` 渲染；
- 现有导出、问答、模板模块无须修改。