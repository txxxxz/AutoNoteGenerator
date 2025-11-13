from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class DetailPolicy:
    label: str
    length_ratio: tuple[float, float]
    summary: str
    examples: str
    structure: str
    figure_caption: str
    coverage: str


@dataclass(frozen=True)
class TonePolicy:
    label: str
    voice: str
    terminology: str
    sentence_length: str
    analogy: str
    formula_guidance: str
    variable_policy: str
    constraint_policy: str
    transition: str


DETAIL_POLICIES = {
    "brief": DetailPolicy(
        label="简略",
        length_ratio=(0.6, 0.8),
        summary="章节结尾可以省略总结；若必须总结，仅写 1 句“核心 takeaway”。",
        examples="避免展开案例；若资料只有案例，请提炼成一句结论即可。",
        structure="以 3-4 条短 bullet 或 1-2 句紧凑段落直接回答学生最关心的问题。",
        figure_caption="图表或公式只需 1 句说明其用途或趋势。",
        coverage="聚焦结论、关键定义与记忆提示，省略推导细节。",
    ),
    "medium": DetailPolicy(
        label="中等",
        length_ratio=(0.9, 1.1),
        summary="每节结尾提供 1-2 句总结，回答“学到了什么”。",
        examples="至少写出 1 个例子或场景，突出关键步骤或直观感受。",
        structure="段落与 bullet 均衡，段首使用“接下来/因此”等提示保持衔接。",
        figure_caption="图表或公式用 1-2 句说明目的与使用方式。",
        coverage="覆盖结论、定义与核心推理，必要时点出关键条件。",
    ),
    "detailed": DetailPolicy(
        label="详细",
        length_ratio=(1.4, 1.7),
        summary="总结需 2-4 句，可列要点清单，包含洞见与下一步提示。",
        examples="提供 2-3 个深入示例、推导节点或反例，说明条件与结果。",
        structure="以段落为主并穿插列表，明确因果、条件与跨页内容的延续关系。",
        figure_caption="图表或公式需要 2-4 句阐述背景、变量含义与适用边界。",
        coverage="涵盖结论、定义、推理、约束与常见误区或实验洞察。",
    ),
}


TONE_POLICIES = {
    "simple": TonePolicy(
        label="popular（亲切科普）",
        voice="使用亲切、贴近口语的语气，先给“人话结论”再解释原因。",
        terminology="每 100 词不超过 2 个术语，并立即用日常语言解释。",
        sentence_length="句长保持在 8-14 个中文词或等效长度，避免复合长句。",
        analogy="每个主题至少举 1 个贴近日常的比喻或生活场景。",
        formula_guidance="先用文字解释直觉，再引入最多 1 个关键公式，说明它解决的问题。",
        variable_policy="只点出最关键的变量含义，并融入句子而非罗列列表。",
        constraint_policy="强调最直接的使用注意事项即可，无需罗列复杂假设。",
        transition="多用“打个比方”“换句话说”“这意味着”等口头衔接表达。",
    ),
    "explanatory": TonePolicy(
        label="standard（课堂讲解）",
        voice="保持标准课堂讲解语气，逻辑清晰、步骤明确。",
        terminology="每 100 词使用 3-6 个术语，并附一句定义或用途。",
        sentence_length="句长控制在 12-20 个中文词，必要时拆成 bullet 提高清晰度。",
        analogy="仅在概念生涩时使用简短类比，更多通过因果或步骤解释。",
        formula_guidance="引入 1-2 个必要公式，并在同一句说明用途或适用条件。",
        variable_policy="变量出现时立即说明含义、单位或范围。",
        constraint_policy="每个主要概念至少写 1 条适用条件或限制。",
        transition="使用“因此”“接下来”“基于上述”等逻辑连接词维持递进。",
    ),
    "academic": TonePolicy(
        label="insightful（半学术）",
        voice="采用半学术语气，强调推理链与前提假设。",
        terminology="每 100 词可使用 6-10 个术语，可引用标准命名或定理编号。",
        sentence_length="句长允许 16-24 个中文词，包含多重从句但保持清晰。",
        analogy="以对比、反例或条件讨论替代生活化比喻。",
        formula_guidance="可呈现 2-3 个公式，并说明推导背景、变量角色与局限性。",
        variable_policy="提供变量表或依次写出“符号=含义=单位/范围”。",
        constraint_policy="明确写出 1-2 条边界条件、假设或不适用情形。",
        transition="使用“在…条件下”“因此”“从而”“综上”等逻辑连接词强调推理路径。",
    ),
}


@dataclass(frozen=True)
class StyleProfile:
    text: str
    directives: Dict[str, Any]
    example_snippet: str


GLOBAL_PERSONA = (
    "你是大学课程的智能讲解助手，负责把课件内容转化成自然、口头化的教学讲解，帮助学生理解知识而非逐页复述。"
)
FLOW_INSTRUCTION = (
    "每个自然段遵循“为什么值得关注 → 是什么/概念 → 怎么做或如何应用”的顺序，不使用模板式小标题；用自然段或必要的 bullet 描述，并在段首或段尾写 1-2 句承上启下。"
)
FORMULA_RULE = (
    "遇到公式请保留原符号，逐个解释符号含义，并说明该公式试图解决的问题或它的适用条件；"
    "所有公式必须使用 `$$公式$$` 包裹，例如 `$$x-1$$` 而不是 `(x-1)`。"
)
FIGURE_PLACEHOLDER_RULE = (
    "描述图表或截图的核心关系，插入占位符 [FIG_PAGE_<页号>_IDX_<序号>: 描述] 指回原始资源，并紧接着用 1-2 句自然语言解释图像；算法/流程/网络结构图需额外交代关键步骤。"
)
BULLET_RULE = (
    "可使用 bullet 强调步骤或要点，但整段仍需连贯讲述，避免把篇章拆成模板化小节。"
)
MISSING_RULE = "上下文缺失或证据不足时，直接写“此处待补充”，绝不杜撰数据、推导或引用。"
EVIDENCE_RULE = "示例、比喻与数字必须来自现有上下文；若资料只有片段，请标注缺口而非臆造。"


def build_style_profile(detail_level: str, difficulty: str, language: str = "zh") -> StyleProfile:
    detail = DETAIL_POLICIES[detail_level]
    tone = TONE_POLICIES[difficulty]
    language_instruction = _build_language_instruction(language)
    sections = [
        f"【角色设定】{GLOBAL_PERSONA}",
        f"【讲解顺序】{FLOW_INSTRUCTION}",
        f"【篇幅与重点｜{detail.label}】目标篇幅 {detail.length_ratio[0]:.1f}-{detail.length_ratio[1]:.1f}× 大纲基线；{detail.coverage}",
        f"【结构倾向】{detail.structure}",
        f"【总结与示例】{detail.summary} {detail.examples}",
        f"【语气与衔接｜{tone.label}】{tone.voice} {tone.transition}",
        f"【术语与句长】{tone.terminology} {tone.sentence_length}",
        f"【比喻/修辞】{tone.analogy}",
        f"【公式与图表】{detail.figure_caption} {tone.formula_guidance} {FORMULA_RULE}",
        f"【变量与约束】{tone.variable_policy} {tone.constraint_policy}",
        f"【bullet 使用】{BULLET_RULE}",
        f"【图像占位符】{FIGURE_PLACEHOLDER_RULE}",
        f"【缺失或不确定信息】{MISSING_RULE}",
        f"【示例与依据】{EVIDENCE_RULE}",
        f"【语言】{language_instruction}",
    ]
    text = "\n".join(f"- {line}" for line in sections if line)
    directives = _compose_directives(detail_level, difficulty, language)
    example_snippet = _build_example_snippet(detail, tone, directives, language)
    return StyleProfile(text=text, directives=directives, example_snippet=example_snippet)


def build_style_instructions(detail_level: str, difficulty: str, language: str = "zh") -> str:
    """
    Backward compatible helper that exposes the legacy string instructions.
    Code that only understands textual prompts can continue using this API,
    while the new StyleProfile carries richer directives.
    """
    return build_style_profile(detail_level, difficulty, language).text


def _build_language_instruction(language: str) -> str:
    if language == "zh":
        return (
            "使用简体中文书写所有段落、 bullet 与占位符说明；如上下文为英文，也需翻译成中文保持统一。"
        )
    return (
        "Write every paragraph, list item, and placeholder description in fluent English; "
        "translate any Chinese context instead of copying it verbatim."
    )


def _compose_directives(detail_level: str, tone_level: str, language: str) -> Dict[str, Any]:
    summary_mode = (
        "none" if detail_level == "brief" else "takeaway" if detail_level == "medium" else "insight"
    )
    formula_mode = (
        "light" if tone_level == "simple" else "balanced" if tone_level == "explanatory" else "extended"
    )
    return {
        "detail_level": detail_level,
        "tone": tone_level,
        "language": language,
        "summary_mode": summary_mode,
        "use_table": detail_level != "brief",
        "analogy_required": tone_level == "simple",
        "formula_mode": formula_mode,
        "formula_caption_scope": "contextual" if tone_level != "academic" else "rigorous",
        "page_header_template": "### 第{page}页" if language == "zh" else "### Page {page}",
        "blockquote_required": detail_level != "brief",
        "require_summary": summary_mode != "none",
        "validator": {
            "ensure_page_headers": True,
            "ensure_summary": summary_mode != "none",
            "ensure_blockquote": detail_level != "brief",
        },
    }


def _build_example_snippet(
    detail: DetailPolicy, tone: TonePolicy, directives: Dict[str, Any], language: str
) -> str:
    header_template = directives.get("page_header_template", "### 第{page}页")
    sample_header = header_template.format(page=3)
    detail_label_en = {"brief": "concise", "medium": "balanced", "detailed": "in-depth"}
    tone_label_en = {
        "simple": "approachable",
        "explanatory": "classroom-style",
        "academic": "academic",
    }
    detail_adj = detail_label_en.get(directives.get("detail_level"), detail.label)
    tone_adj = tone_label_en.get(directives.get("tone"), tone.label)
    if language == "zh":
        intro = "## 示例：多头注意力如何聚焦 (p.3-4)"
        bullets = [
            "- 先一句“人话”解释它为什么重要，再拆成概念与应用。",
            "- 把 PPT bullet 改写成完整语句，并交代承上启下。",
        ]
        style_hint = f"*风格提示：保持「{detail.label}」篇幅和「{tone.label}」的叙述节奏。*"
        analogy_line = "> 💡 打个比方：注意力像手电筒，会把光束集中在关键片段。"
        table_header = "| 对比项 | 直觉 | 提示 |\n| --- | --- | --- |\n| Query | 要问的问题 | 代表当前词 |"
        table_row = "| Key/Value | 候选信息 | 输出时作为权重参考 |"
        formula_line = "$$a = \\frac{qk^T}{\\sqrt{d_k}}$$ —— 解释 q/k/d_k 分别表示当前词、检索词与维度。"
        summary_takeaway = "> **一句话总结：** 聚焦 = 权重重分配。"
        insight_line = "> **章节洞察：** 通过表格与公式说明了注意力兼顾直觉与推理。"
        pending = "（请在正式输出中替换示例内容）"
    else:
        intro = "## Example: How multi-head attention focuses (p.3-4)"
        bullets = [
            "- Lead with the practical reason students should care before definitions.",
            "- Rewrite deck bullets into flowing sentences with transitions.",
        ]
        style_hint = f"*Style cue: keep the notes {detail_adj} while sounding {tone_adj}.*"
        analogy_line = "> 💡 Analogy: attention is a spotlight that sweeps over the canvas."
        table_header = "| Aspect | Intuition | Tip |\n| --- | --- | --- |\n| Query | Question we ask | Current token |"
        table_row = "| Key/Value | Candidate memory | Weight reference |"
        formula_line = "$$a = \\frac{qk^T}{\\sqrt{d_k}}$$ — explain what each symbol captures."
        summary_takeaway = "> **One-sentence takeaway:** Focus comes from re-weighting evidence."
        insight_line = "> **Section insight:** Tables + formulas keep both intuition and rigor aligned."
        pending = "(Replace placeholder text in real output.)"

    snippet_parts = [intro, style_hint, sample_header]
    snippet_parts.extend(bullets)

    if directives.get("analogy_required"):
        snippet_parts.append(analogy_line)

    if directives.get("use_table"):
        snippet_parts.extend([table_header, table_row])

    if directives.get("formula_mode") == "extended":
        snippet_parts.append(formula_line)

    summary_mode = directives.get("summary_mode", "none")
    if summary_mode == "takeaway":
        snippet_parts.append(summary_takeaway)
    elif summary_mode == "insight":
        snippet_parts.append(insight_line)

    snippet_parts.append(pending)
    return "\n".join(snippet_parts).strip()
