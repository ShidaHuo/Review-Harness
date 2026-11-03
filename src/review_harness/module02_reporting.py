from __future__ import annotations

from pathlib import Path
from typing import Any

from .module02_storage import (
    export_research,
    export_reviews,
    export_trend_claims,
    get_module02_run,
    list_perspective_branches,
)
from .storage import connect, get_topic_run


def _list_or_unavailable(values: list[str]) -> str:
    return "；".join(values) if values else "无法从当前证据核验"


def _nature_label(value: str) -> str:
    return {"yes": "是", "no": "否", "unverified": "暂无法核验"}.get(value, "暂无法核验")


def _access_label(value: str) -> str:
    return {
        "oa_downloaded": "开放获取PDF",
        "institutional_downloaded": "学校SSO授权PDF",
        "login_required": "需要用户完成学校SSO",
        "institution_not_subscribed": "学校未订阅，已跳过",
        "license_restricted": "许可不允许自动分析，已跳过",
        "download_failed": "允许访问但下载失败",
        "skipped": "已跳过",
        "not_checked": "尚未检查",
    }.get(value, "尚未检查")


def _review_selection_context(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    exact_count = sum(review.get("review_match_level") == "exact" for review in reviews)
    adjacent_count = sum(review.get("review_match_level") == "adjacent" for review in reviews)
    if exact_count:
        return {
            "mode": "exact_review_anchored",
            "exact_count": exact_count,
            "adjacent_count": adjacent_count,
            "message": f"发现{exact_count}篇完整主题综述，以下分析以完整主题综述为依据。",
        }
    if adjacent_count:
        return {
            "mode": "adjacent_review_fallback",
            "exact_count": 0,
            "adjacent_count": adjacent_count,
            "message": (
                "未发现同时锚定全部核心关键词的完整主题综述；"
                f"以下{adjacent_count}篇为相关度最高的邻近主题综述，"
                "按Module 02相同证据流程进行全文状态、结构、趋势、锚点和差异分析。"
            ),
        }
    return {
        "mode": "no_related_reviews",
        "exact_count": 0,
        "adjacent_count": 0,
        "message": "未发现完整主题综述，也没有达到纳入条件的邻近主题综述。",
    }


def _review_block(index: int, review: dict[str, Any]) -> str:
    cited = review.get("cited_by_count")
    cited_text = str(cited) if cited is not None else "暂无法核验"
    observed = str(review.get("citation_as_of") or "")[:10]
    evidence = {
        "full_text": "全文",
        "abstract_only": "仅摘要",
        "metadata_only": "仅元数据",
    }.get(review.get("evidence_level"), "尚未分析")
    match_level = {
        "exact": "完整主题综述",
        "adjacent": "邻近主题综述（关键词回退）",
    }.get(review.get("review_match_level"), "尚未分类")
    keywords = "、".join(review.get("matched_keywords", [])) or "无"
    return f"""### {index:02d}｜{review['title']}

- 相关层级：{match_level}
- 相关度：{review.get('review_relevance_score') if review.get('review_relevance_score') is not None else '暂无法核验'}；匹配关键词：{keywords}
- 发表时间：{review.get('publication_date') or review.get('publication_year') or '暂无法核验'}
- 发表期刊：{review.get('journal') or '暂无法核验'}
- Nature Index期刊：{_nature_label(review.get('nature_index_status', 'unverified'))}
- 引用次数：{cited_text}（截至 {observed or '暂无法核验'}，OpenAlex）
- 论文链接：[{review['paper_url']}]({review['paper_url']})
- Full-text访问：{_access_label(review.get('fulltext_access_status', 'not_checked'))}
- 做综述的原因：{review.get('review_reason') or '无法从当前证据核验'}
- 综述结构：{_list_or_unavailable(review.get('structure', []))}
- 未来发展趋势：{_list_or_unavailable(review.get('future_trends', []))}
- 证据等级：{evidence}
"""


def _research_lines(papers: list[dict[str, Any]], category: str) -> str:
    selected = [paper for paper in papers if paper.get("category") == category]
    if not selected:
        return "- 当前没有完成该类别的证据分类。"
    lines = []
    for paper in selected:
        link = f"https://doi.org/{paper['doi']}" if paper.get("doi") else paper.get("openalex_id")
        title = f"[{paper['title']}]({link})" if link else paper["title"]
        trends = _list_or_unavailable(paper.get("matched_future_trends", []))
        trend_ids = ", ".join(paper.get("matched_trend_claim_ids", [])) or "无"
        lines.append(
            f"- {title}（{paper.get('publication_date') or paper['publication_year']}）："
            f"{paper.get('rationale') or '待补充理由'}；TrendClaim：{trend_ids}；对应趋势：{trends}"
        )
    return "\n".join(lines)


def _branch_line(item: dict[str, Any]) -> str:
    version = item.get("module03_outline_version")
    version_text = f"（v{version}）" if version else ""
    return (
        f"- 视角{item['perspective_rank']}：{item['perspective_title']}；"
        f"聊天分支：{item.get('dsh_session_id') or '待创建'}；分支状态：{item['status']}；"
        f"大纲：{item.get('module03_outline_status') or '尚未开始'}{version_text}"
    )


def _perspective_blocks(perspectives: list[dict[str, Any]]) -> str:
    if not perspectives:
        return "尚未形成候选综述视角。"
    blocks = []
    for index, item in enumerate(sorted(perspectives, key=lambda value: value.get("rank", 99)), start=1):
        blocks.append(
            f"""### 视角 {index:02d}｜{item['candidate_title']}

- 核心问题：{item['central_question']}
- 与前述综述的相同点：{_list_or_unavailable(item.get('similarities', []))}
- 与前述综述的不同点：{_list_or_unavailable(item.get('differences', []))}
- 建议边界：{item['recommended_scope']}
- 风险与限制：{_list_or_unavailable(item.get('risks', []))}
"""
        )
    return "\n".join(blocks)


def _require_perspectives_ready(run: dict[str, Any]) -> None:
    if run.get("status") != "perspectives_ready" or len(run.get("perspectives", [])) < 3:
        raise ValueError(
            "Module 02 output is not ready; follow module02-next until perspectives_ready"
        )


def render_module02_report(db_path: Path, module02_run_id: str, output_directory: Path) -> Path:
    run = get_module02_run(db_path, module02_run_id)
    _require_perspectives_ready(run)
    topic_run = get_topic_run(db_path, run["topic_run_id"])
    topic_name = topic_run["profile"].get("topic", {}).get("canonical_zh", topic_run["topic"])
    reviews = [review for review in export_reviews(db_path, module02_run_id) if review["relevance_status"] == "included"]
    selection = _review_selection_context(reviews)
    research = export_research(db_path, module02_run_id)
    trend_claims = export_trend_claims(db_path, module02_run_id)
    with connect(db_path) as connection:
        search_rows = connection.execute(
            """
            SELECT phase, status, truncated FROM module02_searches
            WHERE module02_run_id = ? ORDER BY started_at
            """,
            (module02_run_id,),
        ).fetchall()
    incomplete_searches = sum(
        1 for row in search_rows if row["status"] != "completed" or row["truncated"]
    )
    completeness = (
        f"不完整：{incomplete_searches}/{len(search_rows)} 条查询失败或截断"
        if incomplete_searches
        else f"完整：{len(search_rows)} 条查询均未记录失败或截断"
    )

    review_blocks = "\n".join(_review_block(index, review) for index, review in enumerate(reviews, start=1))
    if not review_blocks:
        review_blocks = "尚无经过语义确认的主题相关综述。"

    anchor = next((review for review in reviews if review["id"] == run.get("newest_review_id")), None)
    baseline = next((review for review in reviews if review["id"] == run.get("trend_baseline_review_id")), None)
    anchor_level = (
        "邻近主题综述回退锚点"
        if anchor and anchor.get("review_match_level") == "adjacent"
        else "完整主题综述锚点"
    )
    anchor_text = (
        f"{anchor['title']}（{anchor.get('publication_date')}；{anchor_level}）"
        if anchor
        else ("无相关综述" if run.get("status") == "research_collection_no_review" else "尚未确定")
    )
    included_research = [
        paper for paper in research
        if paper.get("category") in {"trend_consistent", "trend_extension", "new_direction"}
    ]
    baseline_text = (
        f"{baseline['title']}（{baseline.get('publication_date')}；"
        f"{'邻近主题综述证据' if baseline.get('review_match_level') == 'adjacent' else '完整主题综述证据'}）"
        if baseline
        else "无可核验的全文趋势基线"
    )
    trend_text = "\n".join(
        f"- `{claim['id']}` {claim['canonical_label']}：{claim['description']}"
        for claim in trend_claims
    ) or "- 当前没有可由全文证据支持的标准化TrendClaim。"

    report = f"""# {topic_name} · 综述格局与最新研究分析

> Module 02 Run ID：`{module02_run_id}`
> Nature Index快照：`{run.get('nature_index_snapshot_id') or '未附加'}`
> 检索完整性：{completeness}

## A｜相关综述

**综述检索结论：** {selection['message']}

{review_blocks}

## B｜标准化未来趋势

- 时间锚点：{anchor_text}
- 趋势基线：{baseline_text}

{trend_text}

## C｜最新综述节点后的研究论文

- 最新综述节点：{anchor_text}
- 统计窗口：{run.get('research_from_date') or '待确定'} 至 {run.get('research_to_date') or '待确定'}
- 已纳入研究论文：{len(included_research)}

### 与综述未来趋势相符

{_research_lines(research, 'trend_consistent')}

### 对综述趋势的延伸

{_research_lines(research, 'trend_extension')}

### 综述之外的新研究

{_research_lines(research, 'new_direction')}

## D｜目前值得开展的综述视角

{_perspective_blocks(run.get('perspectives', []))}
"""

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{module02_run_id}.md"
    output_path.write_text(report, encoding="utf-8")
    return output_path


def render_module02_summary(db_path: Path, module02_run_id: str, output_directory: Path) -> Path:
    run = get_module02_run(db_path, module02_run_id)
    _require_perspectives_ready(run)
    topic_run = get_topic_run(db_path, run["topic_run_id"])
    topic_name = topic_run["profile"].get("topic", {}).get("canonical_zh", topic_run["topic"])
    reviews = [review for review in export_reviews(db_path, module02_run_id) if review["relevance_status"] == "included"]
    selection = _review_selection_context(reviews)
    exact_review_count = selection["exact_count"]
    adjacent_review_count = selection["adjacent_count"]
    research = export_research(db_path, module02_run_id)
    trends = export_trend_claims(db_path, module02_run_id)
    categories = {
        category: [paper for paper in research if paper.get("category") == category]
        for category in ("trend_consistent", "trend_extension", "new_direction")
    }
    branch = {
        "exact_review_anchored": "完整主题综述锚点分支",
        "adjacent_review_fallback": "邻近主题综述回退分支",
        "no_related_reviews": "无相关综述分支",
    }[selection["mode"]]
    perspectives = sorted(run.get("perspectives", []), key=lambda value: value.get("rank", 99))
    branches = list_perspective_branches(db_path, module02_run_id)
    perspective_lines = "\n".join(
        f"{index}. **{item['candidate_title']}**：{item['central_question']}；差异：{_list_or_unavailable(item.get('differences', []))}"
        for index, item in enumerate(perspectives[:5], start=1)
    ) or "尚未形成候选综述视角。"
    branch_lines = "\n".join(_branch_line(item) for item in branches) or "- 尚未创建视角分支记录。"

    summary = f"""# {topic_name} · Module 02简报

- 执行分支：{branch}
- 综述检索结论：{selection['message']}
- Nature Index快照：{run.get('nature_index_snapshot_id') or '未附加'}
- 相关综述：{len(reviews)}篇（完整主题{exact_review_count}篇，邻近主题回退{adjacent_review_count}篇）
- 时间锚点：{run.get('newest_review_date') or '无'}
- 趋势基线：{run.get('trend_baseline_review_date') or '无'}
- 标准化TrendClaim：{len(trends)}条
- 研究窗口：{run.get('research_from_date') or '待确定'} 至 {run.get('research_to_date') or '待确定'}
- 趋势相符：{len(categories['trend_consistent'])}篇
- 趋势延伸：{len(categories['trend_extension'])}篇
- 综述外新方向：{len(categories['new_direction'])}篇

## 推荐综述视角

{perspective_lines}

## 视角聊天分支

{branch_lines}

完整逐篇证据、链接、结构、趋势和分类保存在同一Module 02 run的完整报告中。状态为`perspectives_ready`；请从随后显示的问题卡选择一个视角。每个视角都有持久逻辑分支；附有Session ID时才代表真实DeepSeek聊天fork。选择视角会创建或恢复该分支的Module 03大纲设计run；Module 02本身不得生成大纲或正文。
"""
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{module02_run_id}.summary.md"
    output_path.write_text(summary, encoding="utf-8")
    return output_path
