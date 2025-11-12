from __future__ import annotations

from dataclasses import dataclass


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


GLOBAL_PERSONA = (
    "你是大学课程的智能讲解助手，负责把课件内容转化成自然、口头化的教学讲解，帮助学生理解知识而非逐页复述。"
)
FLOW_INSTRUCTION = (
    "每个自然段遵循“为什么值得关注 → 是什么/概念 → 怎么做或如何应用”的顺序，不使用模板式小标题；用自然段或必要的 bullet 描述，并在段首或段尾写 1-2 句承上启下。"
)
FORMULA_RULE = (
    "遇到公式请保留原符号，逐个解释符号含义，并说明该公式试图解决的问题或它的适用条件。"
)
FIGURE_PLACEHOLDER_RULE = (
    "描述图表或截图的核心关系，并插入占位符 [FIG_PAGE_<页号>_IDX_<序号>: 描述] 指回原始资源。"
)
BULLET_RULE = (
    "可使用 bullet 强调步骤或要点，但整段仍需连贯讲述，避免把篇章拆成模板化小节。"
)
MISSING_RULE = "上下文缺失或证据不足时，直接写“此处待补充”，绝不杜撰数据、推导或引用。"
EVIDENCE_RULE = "示例、比喻与数字必须来自现有上下文；若资料只有片段，请标注缺口而非臆造。"


def build_style_instructions(detail_level: str, difficulty: str, language: str = "zh") -> str:
    detail = DETAIL_POLICIES[detail_level]
    tone = TONE_POLICIES[difficulty]
    language_instruction = (
        "使用简体中文书写所有段落、 bullet 与占位符说明；如上下文为英文，也需翻译成中文保持统一。"
        if language == "zh"
        else "Write every paragraph, list item, and placeholder description in fluent English; translate any Chinese context instead of copying it verbatim."
    )
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
    return "\n".join(f"- {line}" for line in sections if line)
