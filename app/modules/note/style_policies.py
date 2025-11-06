from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetailPolicy:
    length_ratio: tuple[float, float]
    requires_summary: bool
    summary_length: tuple[int, int]
    examples_per_section: int
    paragraph_bias: str
    figure_caption_style: str
    section_blueprint: tuple[str, ...]


@dataclass(frozen=True)
class DifficultyPolicy:
    tone: str
    terminology_density: str
    sentence_length: str
    formula_usage: str
    variable_policy: str
    constraints: str


DETAIL_POLICIES = {
    "brief": DetailPolicy(
        length_ratio=(0.6, 0.8),
        requires_summary=False,
        summary_length=(1, 2),
        examples_per_section=0,
        paragraph_bias="Use bullet lists with no more than 4 items.",
        figure_caption_style="Explain each figure in one sentence focusing on purpose.",
        section_blueprint=(
            "## 核心要点：2-3 条精炼 bullet，总结本节最重要的事实或结论。",
            "## 必记术语：列出关键词并给出一句释义；无内容时写“待补充”。",
            "## 速记提示：给出记忆口诀或课堂提醒；若缺少信息请标注“待补充”。",
        ),
    ),
    "medium": DetailPolicy(
        length_ratio=(0.9, 1.1),
        requires_summary=True,
        summary_length=(1, 2),
        examples_per_section=1,
        paragraph_bias="Balance between paragraphs and bullet lists.",
        figure_caption_style="Explain each figure in 1-2 sentences covering purpose and usage.",
        section_blueprint=(
            "## 概要：1-2 段交代主题、背景与学习目标。",
            "## 核心概念：条列关键术语，附 1-2 句标准定义与作用。",
            "## 推导 / 示例：使用段落或列表说明关键推理步骤，至少包含一个例子。",
            "## 条件与限制：列举适用前提、常见误区或对比。",
            "## 小结：1 段概括学习收获与下一步建议。",
        ),
    ),
    "detailed": DetailPolicy(
        length_ratio=(1.4, 1.7),
        requires_summary=True,
        summary_length=(2, 4),
        examples_per_section=3,
        paragraph_bias="Prefer explanatory paragraphs complemented by lists.",
        figure_caption_style="Provide 2-4 sentence captions describing purpose, background, and limitations.",
        section_blueprint=(
            "## 章节导论：交代理论来源、前置知识与研究意义。",
            "## 概念体系：分层阐述术语、公式及彼此关系，可使用子标题。",
            "## 推导与证明：分步骤书写公式、变量解释与结论，必要时加入伪代码或编号列表。",
            "## 案例与应用：给出至少一个深入案例/实验，说明步骤、结论与启示。",
            "## 条件、限制与扩展：详述假设、边界条件、常见反例与延伸阅读。",
            "## 总结与后续学习：总结关键洞见并推荐进阶资料或思考题。",
        ),
    ),
}


DIFFICULTY_POLICIES = {
    "simple": DifficultyPolicy(
        tone="Use popular science tone with approachable analogies.",
        terminology_density="Limit technical terms to 2 per 100 words.",
        sentence_length="Keep sentences between 8 and 14 Chinese words or equivalent brevity.",
        formula_usage="Delay formulas; present one key equation only after verbal explanation.",
        variable_policy="Only define critical variables inline.",
        constraints="Avoid unqualified claims; focus on practical clarity.",
    ),
    "explanatory": DifficultyPolicy(
        tone="Use standard instructional tone appropriate for undergraduates.",
        terminology_density="Use 3-6 key terms per 100 words with concise definitions.",
        sentence_length="Use sentences between 12 and 20 Chinese words or equivalent.",
        formula_usage="Include 1-2 necessary formulas with one sentence purpose.",
        variable_policy="Define key variables as they appear.",
        constraints="Highlight at least one applicable condition or limitation per major concept.",
    ),
    "academic": DifficultyPolicy(
        tone="Adopt an insightful academic tone with logical connectors.",
        terminology_density="Use 6-10 domain terms per 100 words with definitions or references.",
        sentence_length="Allow sentences between 16 and 24 Chinese words or equivalent complexity.",
        formula_usage="Provide 2-3 formulas and a variable table where applicable.",
        variable_policy="Add a variable table enumerating symbol, name, and unit/domain.",
        constraints="State 1-2 applicability constraints or boundary conditions explicitly.",
    ),
}


def build_style_instructions(detail_level: str, difficulty: str) -> str:
    detail = DETAIL_POLICIES[detail_level]
    difficulty_policy = DIFFICULTY_POLICIES[difficulty]
    summary_policy = (
        f"Provide section summaries of {detail.summary_length[0]}-{detail.summary_length[1]} sentences."
        if detail.requires_summary
        else "Section summaries are optional; include them only if they aid clarity."
    )
    example_policy = (
        f"Include {detail.examples_per_section} illustrative example(s) per section."
        if detail.examples_per_section
        else "Skip detailed examples; focus on conclusions and key definitions."
    )
    structure_lines = "\n  ".join(
        f"{index + 1}. {item}" for index, item in enumerate(detail.section_blueprint)
    )
    instructions = [
        f"Target total length between {detail.length_ratio[0]:.1f}x and {detail.length_ratio[1]:.1f}x of the base outline.",
        "Follow the Markdown section skeleton below:\n  " + structure_lines,
        "Only fill a section when the retrieved context covers it; otherwise write “待补充”。",
        detail.paragraph_bias,
        detail.figure_caption_style,
        summary_policy,
        example_policy,
        difficulty_policy.tone,
        difficulty_policy.terminology_density,
        difficulty_policy.sentence_length,
        difficulty_policy.formula_usage,
        difficulty_policy.variable_policy,
        difficulty_policy.constraints,
        "Use anchors from the outline when referencing sources; format as `参考锚点：anchor:...`.",
        "When contextual evidence is missing, state “待补充” instead of fabricating details.",
    ]
    return "\n".join(f"- {line}" for line in instructions)
