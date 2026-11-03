from __future__ import annotations

from pathlib import Path

from .models import rolling_two_year_window, utc_now
from .reference_storage import (
    nature_index_journal_names,
    nature_index_snapshot_for_topic,
    normalize_publication_name,
)
from .storage import connect, status_for_run

RESEARCH_WORK_TYPES = ("article", "preprint", "conference-paper", "proceedings-article")


def render_report(db_path: Path, run_id: str, output_directory: Path) -> Path:
    status = status_for_run(db_path, run_id)
    run = status["run"]
    profile = run["profile"]
    planned_queries = profile.get("queries", [])
    attempted_ids = {item.get("query_id") for item in status["searches"] if item.get("query_id")}
    attempted_legacy = {(item["scope"], item["query"]) for item in status["searches"]}
    missing_queries = [
        item["id"] for item in planned_queries
        if item["id"] not in attempted_ids
        and (item["scope"], item["query"]) not in attempted_legacy
    ]
    if missing_queries:
        raise ValueError(f"Module 01 query plan is incomplete: {missing_queries}")
    with connect(db_path) as connection:
        pending_relevance = connection.execute(
            """
            SELECT COUNT(DISTINCT paper_id) FROM run_papers
            WHERE topic_run_id = ? AND relevance_label IS NULL
            """,
            (run_id,),
        ).fetchone()[0]
    if pending_relevance:
        raise ValueError(
            f"Module 01 report is not ready: {pending_relevance} papers still need semantic screening"
        )
    counts = status["paper_counts_by_relevance"]
    labels = profile.get("display_labels", {})
    topic_name = profile.get("topic", {}).get("canonical_zh", run["topic"])
    exact_label = labels.get("exact_research_label", f"{topic_name}研究论文")
    parent_label = labels.get("parent_research_label", "上位技术研究论文")
    publication_from, publication_to = rolling_two_year_window()

    work_type_placeholders = ",".join("?" for _ in RESEARCH_WORK_TYPES)
    base_parameters = (run_id, *RESEARCH_WORK_TYPES)
    with connect(db_path) as connection:
        journal_count = connection.execute(
            f"""
            SELECT COUNT(DISTINCT p.source_name)
            FROM papers p
            JOIN run_papers rp ON rp.paper_id = p.id
            WHERE rp.topic_run_id = ?
              AND rp.retrieval_scope IN ('direct', 'technical')
              AND rp.relevance_label IN ('direct', 'technical')
              AND p.work_type IN ({work_type_placeholders})
              AND p.source_name IS NOT NULL
            """,
            base_parameters,
        ).fetchone()[0]
        top_journals = connection.execute(
            f"""
            SELECT p.source_name, COUNT(DISTINCT p.id) AS paper_count
            FROM papers p
            JOIN run_papers rp ON rp.paper_id = p.id
            WHERE rp.topic_run_id = ?
              AND rp.retrieval_scope IN ('direct', 'technical')
              AND rp.relevance_label IN ('direct', 'technical')
              AND p.work_type IN ({work_type_placeholders})
              AND p.source_name IS NOT NULL
            GROUP BY p.source_name
            ORDER BY paper_count DESC, p.source_name
            LIMIT 5
            """,
            base_parameters,
        ).fetchall()
        journal_papers = connection.execute(
            """
            SELECT DISTINCT p.id, p.source_name
            FROM papers p
            JOIN run_papers rp ON rp.paper_id = p.id
            WHERE rp.topic_run_id = ?
              AND rp.relevance_label IN ('direct', 'technical')
              AND p.work_type = 'article'
              AND p.source_name IS NOT NULL
            """,
            (run_id,),
        ).fetchall()

    snapshot = nature_index_snapshot_for_topic(db_path, run_id)
    if snapshot:
        directory_names = nature_index_journal_names(snapshot)
        matched = sum(
            normalize_publication_name(row["source_name"]) in directory_names
            for row in journal_papers
        )
        denominator = len(journal_papers)
        percentage = (100 * matched / denominator) if denominator else 0.0
        nature_text = (
            f"{matched}/{denominator} = {percentage:.1f}%（本地目录快照 "
            f"{snapshot.get('edition') or snapshot.get('retrieved_at', '')[:10]}）"
        )
    else:
        nature_text = "暂无法核验；当前run未附加本地Nature Index目录"

    journal_text = "、".join(f"{row['source_name']}（{row['paper_count']}）" for row in top_journals)
    if not journal_text:
        journal_text = "暂无法核验"

    report = f"""# {topic_name} · 选题可行性评估

> 检索时间窗口：{publication_from} 至 {publication_to}（系统日期前两年）。只统计经过题名/摘要语义分类的研究型论文。

## 01｜文献检索统计

| 指标 | 当前记录数 |
|---|---:|
| {exact_label} | {counts.get('direct', 0)} |
| {parent_label} | {counts.get('technical', 0)} |

数据源：OpenAlex；最多6条查询，每条最多50条、1页；只访问题名、摘要和元数据，非研究型记录不纳入统计。生成时间：{utc_now()}。

## 02｜期刊分布与影响力

| 指标 | 结果 |
|---|---|
| 涉及期刊数量 | {journal_count} |
| Nature Index 期刊论文占比 | {nature_text} |
| 主要发表期刊 | {journal_text} |

## 03｜研究发展情况

- **研究热度与两年内变化：** 待比较两个主题层级在前后12个月的研究论文数量。
- **主要研究方向及技术路线：** 待从纳入的研究论文中归纳，最多5项。
- **代表性研究成果：** 待列出最多5篇研究论文。
- **尚未解决的关键问题：** 待归纳最多5项。

## 04｜Agent 综合判断

- 研究热度：暂无法判断
- 学术影响力：暂无法判断
- 研究成熟度：暂无法判断
- 综述写作价值：暂无法判断
- **综合建议：`insufficient_evidence`，完成轻量语义筛选和 Nature Index 核验后更新。**

## 05｜用户决策

是否继续开展该主题的综述撰写？

报告完整显示后，根Agent使用编号纯文本并等待用户明确回复：`1. 继续`或`2. 结束`。
"""

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{run_id}.md"
    output_path.write_text(report, encoding="utf-8")
    return output_path
