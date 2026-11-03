from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .models import VALID_DECISIONS
from .module02_reporting import render_module02_report, render_module02_summary
from .module03_reporting import render_outline
from .module03_storage import (
    get_module03_run,
    module03_next_action,
    record_outline_feedback,
    save_outline_version,
    start_module03_outline,
)
from .module04_service import export_frozen_outline, module04_export_for_run
from .module02_service import run_post_review_research_search, run_review_search
from .module02_storage import (
    attach_perspective_sessions,
    create_module02_run,
    export_research,
    export_reviews,
    export_trend_claims,
    finalize_research_comparison,
    finalize_review_anchor,
    get_module02_run,
    list_perspective_branches,
    module02_next_action,
    plan_module02_research_queries,
    rebuild_perspective_selection,
    save_fulltext_access,
    save_perspectives,
    save_research_comparisons,
    save_review_analyses,
    save_review_screening,
    save_trend_claims,
    select_perspective_branch,
)
from .reference_storage import (
    attach_bundled_nature_index_snapshot,
    save_nature_index_snapshot,
)
from .reporting import render_report
from .service import run_openalex_search
from .storage import (
    create_or_resume_topic_run,
    export_module01_papers,
    init_db,
    module01_next_action,
    save_decision,
    save_module01_relevance,
    status_for_run,
)

DEFAULT_DB = Path("runtime/research.sqlite3")
DEFAULT_RAW_ROOT = Path("runtime/raw")
DEFAULT_OUTPUTS = Path("outputs")


def _json_file(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _write_json_file(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _write_batches(
    output_directory: Path,
    *,
    prefix: str,
    key: str,
    items: list[dict[str, Any]],
    batch_size: int,
    module02_run_id: str,
) -> list[str]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for start in range(0, len(items), batch_size):
        batch_number = start // batch_size + 1
        path = output_directory / f"{prefix}-{batch_number:04d}.json"
        _write_json_file(path, {
            "schema_version": "0.1.0",
            "module02_run_id": module02_run_id,
            key: items[start:start + batch_size],
        })
        paths.append(str(path.resolve()))
    return paths


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review-harness")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create or migrate the local SQLite schema")

    create = subparsers.add_parser("create-run", help="Create a Module 01 topic-evaluation run")
    create.add_argument("--topic", required=True)
    create.add_argument("--profile", required=True, help="Path to a TopicProfile JSON file")

    import_nature = subparsers.add_parser(
        "import-nature-index-snapshot", help="Attach an explicitly supplied Nature Index snapshot to Module 01"
    )
    import_nature.add_argument("--run-id", required=True)
    import_nature.add_argument("--input", type=Path, required=True)

    bundled_nature = subparsers.add_parser(
        "attach-bundled-nature-index",
        help="Attach the local Nature Index directory bundled with the Module 01 Skill",
    )
    bundled_nature.add_argument("--run-id", required=True)

    search = subparsers.add_parser("search-openalex", help="Retrieve one frozen Module 01 query")
    search.add_argument("--run-id", required=True)
    search.add_argument("--query-id", required=True, help="Query id from the run's frozen TopicProfile")
    search.add_argument("--max-pages", type=int, default=1, choices=[1])
    search.add_argument("--per-page", type=int, default=50, choices=range(1, 51), metavar="1..50")
    search.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)

    import_relevance = subparsers.add_parser(
        "import-module01-relevance", help="Persist Module 01 title/abstract relevance labels"
    )
    import_relevance.add_argument("--run-id", required=True)
    import_relevance.add_argument("--input", type=Path, required=True)

    status = subparsers.add_parser("status", help="Show persisted Module 01 state")
    status.add_argument("--run-id", required=True)

    next_module01 = subparsers.add_parser(
        "module01-next", help="Return the next mandatory cross-runtime Module 01 action"
    )
    next_module01.add_argument("--run-id", required=True)

    export_module01 = subparsers.add_parser(
        "export-module01-papers", help="Export deduplicated Module 01 papers for semantic screening"
    )
    export_module01.add_argument("--run-id", required=True)
    export_module01.add_argument("--output", type=Path, required=True)

    report = subparsers.add_parser("render-report", help="Render a Module 01 Markdown draft")
    report.add_argument("--run-id", required=True)
    report.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUTS)

    decision = subparsers.add_parser("save-decision", help="Save the explicit Module 01 user decision")
    decision.add_argument("--run-id", required=True)
    decision.add_argument("--decision", required=True, choices=sorted(VALID_DECISIONS))
    decision.add_argument("--notes")

    start_module02 = subparsers.add_parser("start-module02", help="Start Module 02 after approved Module 01")
    start_module02.add_argument("--run-id", required=True, help="Approved Module 01 topic run id")

    search_reviews = subparsers.add_parser("search-reviews", help="Run one frozen Module 02 review query")
    search_reviews.add_argument("--module02-run-id", required=True)
    search_reviews.add_argument("--query-id", required=True, help="Query id from the Python-derived review plan")
    search_reviews.add_argument("--per-page", type=int, default=100, choices=range(1, 101), metavar="1..100")
    search_reviews.add_argument("--max-pages", type=int, default=10, choices=range(1, 11), metavar="1..10")
    search_reviews.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)

    export_review_parser = subparsers.add_parser("export-reviews", help="Export review records for analysis")
    export_review_parser.add_argument("--module02-run-id", required=True)
    export_review_parser.add_argument("--output", type=Path, required=True)

    import_screening = subparsers.add_parser("import-review-screening", help="Persist title/abstract review screening")
    import_screening.add_argument("--module02-run-id", required=True)
    import_screening.add_argument("--input", type=Path, required=True)

    review_batches = subparsers.add_parser("export-review-batches", help="Export bounded review-analysis batches")
    review_batches.add_argument("--module02-run-id", required=True)
    review_batches.add_argument("--output-directory", type=Path, required=True)
    review_batches.add_argument("--batch-size", type=int, default=5)

    import_fulltext_parser = subparsers.add_parser(
        "import-fulltext-access", help="Persist SSO/OA PDF access outcomes"
    )
    import_fulltext_parser.add_argument("--module02-run-id", required=True)
    import_fulltext_parser.add_argument("--input", type=Path, required=True)

    import_review_parser = subparsers.add_parser("import-review-analysis", help="Persist structured review analyses")
    import_review_parser.add_argument("--module02-run-id", required=True)
    import_review_parser.add_argument("--input", type=Path, required=True)

    import_trends = subparsers.add_parser("import-trend-claims", help="Persist normalized review TrendClaims")
    import_trends.add_argument("--module02-run-id", required=True)
    import_trends.add_argument("--input", type=Path, required=True)

    export_trends = subparsers.add_parser("export-trend-claims", help="Export normalized review TrendClaims")
    export_trends.add_argument("--module02-run-id", required=True)
    export_trends.add_argument("--output", type=Path, required=True)

    anchor = subparsers.add_parser("finalize-review-anchor", help="Use the newest included review as research anchor")
    anchor.add_argument("--module02-run-id", required=True)

    plan_research = subparsers.add_parser("plan-module02-research", help="Plan reuse versus missing-query retrieval")
    plan_research.add_argument("--module02-run-id", required=True)

    next_module02 = subparsers.add_parser(
        "module02-next", help="Return the next mandatory cross-runtime Module 02 action"
    )
    next_module02.add_argument("--module02-run-id", required=True)

    finalize_comparison = subparsers.add_parser(
        "finalize-research-comparison",
        help="Mark research comparison complete after every paper is classified",
    )
    finalize_comparison.add_argument("--module02-run-id", required=True)

    post_review = subparsers.add_parser("search-post-review", help="Run one frozen post-anchor research query")
    post_review.add_argument("--module02-run-id", required=True)
    post_review.add_argument("--query-id", required=True, help="Query id from the frozen Module 01 TopicProfile")
    post_review.add_argument("--per-page", type=int, default=100, choices=range(1, 101), metavar="1..100")
    post_review.add_argument("--max-pages", type=int, default=10, choices=range(1, 11), metavar="1..10")
    post_review.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)

    export_research_parser = subparsers.add_parser("export-module02-research", help="Export research for trend comparison")
    export_research_parser.add_argument("--module02-run-id", required=True)
    export_research_parser.add_argument("--output", type=Path, required=True)

    research_batches = subparsers.add_parser("export-research-batches", help="Export bounded trend-comparison batches")
    research_batches.add_argument("--module02-run-id", required=True)
    research_batches.add_argument("--output-directory", type=Path, required=True)
    research_batches.add_argument("--batch-size", type=int, default=25)

    import_comparison = subparsers.add_parser("import-research-comparison", help="Persist review-trend comparisons")
    import_comparison.add_argument("--module02-run-id", required=True)
    import_comparison.add_argument("--input", type=Path, required=True)

    import_perspectives = subparsers.add_parser("import-review-perspectives", help="Persist proposed review angles")
    import_perspectives.add_argument("--module02-run-id", required=True)
    import_perspectives.add_argument("--input", type=Path, required=True)

    list_branches = subparsers.add_parser("list-perspective-branches", help="List reusable Module 03 chat branches")
    list_branches.add_argument("--module02-run-id", required=True)

    rebuild_selection = subparsers.add_parser(
        "rebuild-perspective-selection", help="Rebuild the Module 02 perspective question options"
    )
    rebuild_selection.add_argument("--module02-run-id", required=True)

    attach_branches = subparsers.add_parser("attach-perspective-sessions", help="Attach DeepSeek session ids to perspectives")
    attach_branches.add_argument("--module02-run-id", required=True)
    attach_branches.add_argument("--input", type=Path, required=True)

    select_branch = subparsers.add_parser("select-perspective", help="Select one existing branch for Module 03")
    select_branch.add_argument("--module02-run-id", required=True)
    select_branch.add_argument("--rank", type=int, required=True, choices=range(1, 6), metavar="1..5")

    render_module02 = subparsers.add_parser("render-module02-report", help="Render the Module 02 report")
    render_module02.add_argument("--module02-run-id", required=True)
    render_module02.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUTS)

    render_summary = subparsers.add_parser("render-module02-summary", help="Render the concise Module 02 chat brief")
    render_summary.add_argument("--module02-run-id", required=True)
    render_summary.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUTS)

    start_module03 = subparsers.add_parser(
        "start-module03", help="Start or resume outline design for a selected perspective"
    )
    start_module03.add_argument("--module02-run-id", required=True)
    start_module03.add_argument("--rank", type=int, required=True, choices=range(1, 6), metavar="1..5")

    module03_status = subparsers.add_parser("module03-status", help="Show a Module 03 outline run")
    module03_status.add_argument("--module03-run-id", required=True)

    module03_next = subparsers.add_parser("module03-next", help="Return the next outline iteration action")
    module03_next.add_argument("--module03-run-id", required=True)

    import_outline = subparsers.add_parser("import-outline", help="Persist a new immutable outline version")
    import_outline.add_argument("--module03-run-id", required=True)
    import_outline.add_argument("--input", type=Path, required=True)
    import_outline.add_argument("--actor", default="root-agent")

    outline_feedback = subparsers.add_parser("save-outline-feedback", help="Approve or request outline revision")
    outline_feedback.add_argument("--module03-run-id", required=True)
    outline_feedback.add_argument("--decision", required=True, choices=["approved", "revise"])
    outline_feedback.add_argument("--feedback")
    outline_feedback.add_argument(
        "--final-output-directory", type=Path, default=DEFAULT_OUTPUTS / "final"
    )

    render_module03 = subparsers.add_parser("render-outline", help="Render the latest Module 03 outline")
    render_module03.add_argument("--module03-run-id", required=True)
    render_module03.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUTS)

    run_module04 = subparsers.add_parser(
        "run-module04", help="Export an approved outline to final Markdown and complete the MVP"
    )
    run_module04.add_argument("--module03-run-id", required=True)
    run_module04.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUTS / "final")

    module04_status = subparsers.add_parser("module04-status", help="Show the final outline export")
    module04_status.add_argument("--module03-run-id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init-db":
            init_db(args.db)
            _print_json({"database": str(args.db.resolve()), "status": "ready"})
        elif args.command == "create-run":
            profile = _json_file(args.profile)
            run_id, resumed = create_or_resume_topic_run(args.db, args.topic, profile)
            snapshot_id = attach_bundled_nature_index_snapshot(args.db, run_id)
            next_action = module01_next_action(args.db, run_id)
            _print_json({
                "run_id": run_id,
                "status": status_for_run(args.db, run_id)["run"]["status"],
                "resumed_existing_run": resumed,
                "nature_index_snapshot_id": snapshot_id,
                "nature_index_source": "bundled_skill_directory",
                "next_action": next_action,
                "must_continue": not next_action["blocking_user_input"] and not next_action["terminal"],
            })
        elif args.command == "import-nature-index-snapshot":
            payload = _json_file(args.input)
            snapshot_id = save_nature_index_snapshot(args.db, args.run_id, payload)
            _print_json({"snapshot_id": snapshot_id, "status": "attached"})
        elif args.command == "attach-bundled-nature-index":
            snapshot_id = attach_bundled_nature_index_snapshot(args.db, args.run_id)
            _print_json({
                "snapshot_id": snapshot_id,
                "status": "attached",
                "source": "bundled_skill_directory",
            })
        elif args.command == "search-openalex":
            result = run_openalex_search(
                db_path=args.db,
                raw_root=args.raw_root,
                topic_run_id=args.run_id,
                query_id=args.query_id,
                max_pages=args.max_pages,
                per_page=args.per_page,
            )
            next_action = module01_next_action(args.db, args.run_id)
            result["next_action"] = next_action
            result["must_continue"] = not next_action["blocking_user_input"] and not next_action["terminal"]
            _print_json(result)
        elif args.command == "import-module01-relevance":
            payload = _json_file(args.input)
            updated = save_module01_relevance(args.db, args.run_id, payload.get("papers", []))
            next_action = module01_next_action(args.db, args.run_id)
            _print_json({
                "updated_papers": updated,
                "next_action": next_action,
                "must_continue": not next_action["blocking_user_input"] and not next_action["terminal"],
            })
        elif args.command == "status":
            _print_json(status_for_run(args.db, args.run_id))
        elif args.command == "module01-next":
            _print_json(module01_next_action(args.db, args.run_id))
        elif args.command == "export-module01-papers":
            path = _write_json_file(args.output, {
                "schema_version": "0.1.0",
                "run_id": args.run_id,
                "papers": export_module01_papers(args.db, args.run_id),
            })
            next_action = module01_next_action(args.db, args.run_id)
            _print_json({
                "output": str(path.resolve()),
                "status": "exported",
                "next_action": next_action,
                "must_continue": not next_action["blocking_user_input"] and not next_action["terminal"],
            })
        elif args.command == "render-report":
            path = render_report(args.db, args.run_id, args.output_directory)
            _print_json({"report": str(path.resolve()), "status": "rendered"})
        elif args.command == "save-decision":
            result = save_decision(args.db, args.run_id, args.decision, args.notes)
            result["next_action"] = module01_next_action(args.db, args.run_id)
            _print_json(result)
        elif args.command == "start-module02":
            _print_json({"module02_run_id": create_module02_run(args.db, args.run_id), "status": "review_discovery"})
        elif args.command == "search-reviews":
            _print_json(run_review_search(
                db_path=args.db,
                raw_root=args.raw_root,
                module02_run_id=args.module02_run_id,
                query_id=args.query_id,
                per_page=args.per_page,
                max_pages=args.max_pages,
            ))
        elif args.command == "export-reviews":
            path = _write_json_file(args.output, {
                "schema_version": "0.1.0",
                "module02_run_id": args.module02_run_id,
                "reviews": export_reviews(args.db, args.module02_run_id),
            })
            _print_json({"output": str(path.resolve()), "status": "exported"})
        elif args.command == "import-review-screening":
            payload = _json_file(args.input)
            updated = save_review_screening(args.db, args.module02_run_id, payload.get("reviews", []))
            _print_json({"screened_reviews": updated})
        elif args.command == "export-review-batches":
            paths = _write_batches(
                args.output_directory,
                prefix="review-batch",
                key="reviews",
                items=export_reviews(args.db, args.module02_run_id, included_only=True),
                batch_size=args.batch_size,
                module02_run_id=args.module02_run_id,
            )
            _print_json({"batch_files": paths, "batch_count": len(paths)})
        elif args.command == "import-fulltext-access":
            payload = _json_file(args.input)
            updated = save_fulltext_access(args.db, args.module02_run_id, payload.get("reviews", []))
            _print_json({"updated_fulltext_access_records": updated})
        elif args.command == "import-review-analysis":
            payload = _json_file(args.input)
            updated = save_review_analyses(args.db, args.module02_run_id, payload.get("reviews", []))
            _print_json({"updated_reviews": updated})
        elif args.command == "import-trend-claims":
            payload = _json_file(args.input)
            count = save_trend_claims(args.db, args.module02_run_id, payload.get("trend_claims", []))
            _print_json({"saved_trend_claims": count})
        elif args.command == "export-trend-claims":
            path = _write_json_file(args.output, {
                "schema_version": "0.1.0",
                "module02_run_id": args.module02_run_id,
                "trend_claims": export_trend_claims(args.db, args.module02_run_id),
            })
            _print_json({"output": str(path.resolve()), "status": "exported"})
        elif args.command == "finalize-review-anchor":
            _print_json(finalize_review_anchor(args.db, args.module02_run_id))
        elif args.command == "plan-module02-research":
            _print_json({
                "module02_run_id": args.module02_run_id,
                "queries": plan_module02_research_queries(args.db, args.module02_run_id),
            })
        elif args.command == "module02-next":
            _print_json(module02_next_action(args.db, args.module02_run_id))
        elif args.command == "finalize-research-comparison":
            _print_json(finalize_research_comparison(args.db, args.module02_run_id))
        elif args.command == "search-post-review":
            _print_json(run_post_review_research_search(
                db_path=args.db,
                raw_root=args.raw_root,
                module02_run_id=args.module02_run_id,
                query_id=args.query_id,
                per_page=args.per_page,
                max_pages=args.max_pages,
            ))
        elif args.command == "export-module02-research":
            path = _write_json_file(args.output, {
                "schema_version": "0.1.0",
                "module02_run_id": args.module02_run_id,
                "papers": export_research(args.db, args.module02_run_id),
            })
            _print_json({"output": str(path.resolve()), "status": "exported"})
        elif args.command == "export-research-batches":
            paths = _write_batches(
                args.output_directory,
                prefix="research-batch",
                key="papers",
                items=export_research(args.db, args.module02_run_id),
                batch_size=args.batch_size,
                module02_run_id=args.module02_run_id,
            )
            _print_json({"batch_files": paths, "batch_count": len(paths)})
        elif args.command == "import-research-comparison":
            payload = _json_file(args.input)
            updated = save_research_comparisons(args.db, args.module02_run_id, payload.get("papers", []))
            _print_json({"updated_papers": updated})
        elif args.command == "import-review-perspectives":
            payload = _json_file(args.input)
            perspectives = payload.get("perspectives", [])
            save_perspectives(args.db, args.module02_run_id, perspectives)
            _print_json({"saved_perspectives": len(perspectives)})
        elif args.command == "list-perspective-branches":
            _print_json({
                "module02_run_id": args.module02_run_id,
                "branches": list_perspective_branches(args.db, args.module02_run_id),
            })
        elif args.command == "rebuild-perspective-selection":
            _print_json(rebuild_perspective_selection(args.db, args.module02_run_id))
        elif args.command == "attach-perspective-sessions":
            payload = _json_file(args.input)
            updated = attach_perspective_sessions(args.db, args.module02_run_id, payload.get("branches", []))
            _print_json({"attached_branches": updated})
        elif args.command == "select-perspective":
            selection = select_perspective_branch(args.db, args.module02_run_id, args.rank)
            module03_run_id = start_module03_outline(args.db, args.module02_run_id, args.rank)
            selection["module03_run_id"] = module03_run_id
            selection["module03_status"] = get_module03_run(args.db, module03_run_id)["status"]
            _print_json(selection)
        elif args.command == "render-module02-report":
            path = render_module02_report(args.db, args.module02_run_id, args.output_directory)
            _print_json({"report": str(path.resolve()), "status": "rendered"})
        elif args.command == "render-module02-summary":
            path = render_module02_summary(args.db, args.module02_run_id, args.output_directory)
            _print_json({"summary": str(path.resolve()), "status": "rendered"})
        elif args.command == "start-module03":
            run_id = start_module03_outline(args.db, args.module02_run_id, args.rank)
            _print_json({"module03_run_id": run_id, "status": get_module03_run(args.db, run_id)["status"]})
        elif args.command == "module03-status":
            _print_json(get_module03_run(args.db, args.module03_run_id))
        elif args.command == "module03-next":
            _print_json(module03_next_action(args.db, args.module03_run_id))
        elif args.command == "import-outline":
            payload = _json_file(args.input)
            version = save_outline_version(
                args.db, args.module03_run_id, payload, actor=args.actor
            )
            _print_json({"module03_run_id": args.module03_run_id, "version": version, "status": "awaiting_outline_feedback"})
        elif args.command == "save-outline-feedback":
            result = record_outline_feedback(
                args.db,
                args.module03_run_id,
                args.decision,
                args.feedback,
            )
            if args.decision == "approved":
                result["module04"] = export_frozen_outline(
                    args.db,
                    args.module03_run_id,
                    args.final_output_directory,
                )
                result["task_status"] = "completed"
            _print_json(result)
        elif args.command == "render-outline":
            path = render_outline(args.db, args.module03_run_id, args.output_directory)
            _print_json({"outline": str(path.resolve()), "status": "rendered"})
        elif args.command == "run-module04":
            _print_json(export_frozen_outline(
                args.db, args.module03_run_id, args.output_directory
            ))
        elif args.command == "module04-status":
            _print_json({
                "module03_run_id": args.module03_run_id,
                "export": module04_export_for_run(args.db, args.module03_run_id),
            })
        else:
            raise AssertionError(f"Unhandled command: {args.command}")
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0
