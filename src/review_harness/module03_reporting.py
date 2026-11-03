from __future__ import annotations

import json
from pathlib import Path

from .module03_storage import get_module03_run, latest_outline
from .storage import connect


def _compact(value: str | None, limit: int = 420) -> str:
    text = " ".join((value or "").split())
    if not text:
        return "当前结构化证据没有提供进一步内容说明。"
    return text if len(text) <= limit else f"{text[:limit].rstrip()}……"


def _resolve_evidence_content(
    db_path: Path, module02_run_id: str, evidence_ids: list[str]
) -> list[str]:
    """Resolve internal evidence ids to user-facing titles and substantive content."""
    descriptions: list[str] = []
    with connect(db_path) as connection:
        for evidence_id in evidence_ids:
            review = connection.execute(
                """
                SELECT title, review_match_level, review_reason, future_trends_json
                FROM module02_reviews
                WHERE module02_run_id = ? AND id = ? AND relevance_status = 'included'
                """,
                (module02_run_id, evidence_id),
            ).fetchone()
            if review is not None:
                level = "完整主题综述" if review["review_match_level"] == "exact" else "邻近主题综述"
                trends = json.loads(review["future_trends_json"] or "[]")
                details = _compact(review["review_reason"])
                if trends:
                    details = f"{details}；可用于本节的趋势内容：{'；'.join(trends)}"
                descriptions.append(f"《{review['title']}》（{level}）：{details}")
                continue

            paper = connection.execute(
                """
                SELECT p.title, p.abstract, p.publication_date, mr.category, mr.rationale
                FROM module02_research mr
                JOIN papers p ON p.id = mr.paper_id
                WHERE mr.module02_run_id = ? AND mr.paper_id = ? AND mr.category != 'excluded'
                """,
                (module02_run_id, evidence_id),
            ).fetchone()
            if paper is not None:
                category = {
                    "trend_consistent": "与既有趋势相符",
                    "trend_extension": "对既有趋势的延伸",
                    "new_direction": "综述之外的新方向",
                    "pending": "待分类研究",
                }.get(paper["category"], "研究论文")
                details = _compact(paper["rationale"] or paper["abstract"])
                date_text = f"，{paper['publication_date']}" if paper["publication_date"] else ""
                descriptions.append(f"《{paper['title']}》（{category}{date_text}）：{details}")
                continue

            trend = connection.execute(
                """
                SELECT canonical_label, description
                FROM module02_trend_claims
                WHERE module02_run_id = ? AND id = ?
                """,
                (module02_run_id, evidence_id),
            ).fetchone()
            if trend is not None:
                descriptions.append(
                    f"趋势“{trend['canonical_label']}”：{_compact(trend['description'])}"
                )
                continue

            descriptions.append("一条已登记证据当前无法解析具体内容，需要在冻结大纲前复核。")
    return descriptions


def _evidence_block(db_path: Path, module02_run_id: str, evidence_ids: list[str]) -> str:
    descriptions = _resolve_evidence_content(db_path, module02_run_id, evidence_ids)
    if not descriptions:
        return "  - 本节属于框架、范围或过渡说明，当前不绑定具体论文证据。"
    return "\n".join(f"  - {description}" for description in descriptions)


def build_outline_markdown(
    db_path: Path,
    module03_run_id: str,
    *,
    include_feedback_prompt: bool,
) -> tuple[str, int]:
    run = get_module03_run(db_path, module03_run_id)
    latest = latest_outline(db_path, module03_run_id)
    if latest is None:
        raise ValueError("No Module 03 outline version is available to render")
    outline = latest["outline"]
    sections: list[str] = []
    for item in outline["sections"]:
        heading_level = min(int(item["level"]) + 1, 6)
        heading = "#" * heading_level
        evidence_content = _evidence_block(
            db_path, run["module02_run_id"], item.get("evidence_ids", [])
        )
        transition = item.get("transition") or "本节为起始部分或不需要额外过渡。"
        logic_lines = "\n".join(
            f"  {index}. {value}" for index, value in enumerate(item["writing_logic"], start=1)
        )
        question_lines = "\n".join(f"  - {value}" for value in item["key_questions"])
        sections.append(
            f"""{heading} {item['number']} {item['title']}

- **本节目的：** {item['purpose']}
- **写作逻辑：**
{logic_lines}
- **关键问题：**
{question_lines}
- **这样安排的原因：** {item['rationale']}
- **证据内容：**
{evidence_content}
- **预期读者收获：** {item['expected_takeaway']}
- **与前后章节的衔接：** {transition}
"""
        )

    feedback = ""
    if include_feedback_prompt:
        feedback = """
## 用户反馈

请回复编号：

1. 满意，冻结大纲
2. 继续修改

如果选择“继续修改”，请说明需要增加、删除、合并、拆分、调整顺序或改变重点的具体内容。Agent必须基于当前版本生成新版本，不能覆盖历史版本。

Module 03当前只设计和迭代大纲，不撰写摘要、引言、章节正文、参考文献稿，不生成图表、Word或LaTeX。
"""

    content = f"""# {outline['candidate_title']}

> Module 03 Run：`{module03_run_id}`
> 选择视角：视角{run['perspective_rank']}｜{run['perspective_title']}
> 大纲版本：v{latest['version']}
> 状态：{run['status']}

## 总体组织逻辑

- **目标读者：** {outline['intended_audience']}
- **范围边界：** {outline['scope_statement']}
- **组织原则：** {outline['organizing_principle']}
- **题目与结构这样设计的原因：** {outline['title_rationale']}

## 分级写作大纲

{''.join(sections)}{feedback}"""
    return content, int(latest["version"])


def render_outline(db_path: Path, module03_run_id: str, output_directory: Path) -> Path:
    content, version = build_outline_markdown(
        db_path, module03_run_id, include_feedback_prompt=True
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / f"{module03_run_id}-outline-v{version:02d}.md"
    path.write_text(content, encoding="utf-8")
    return path
