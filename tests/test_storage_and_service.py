import json
import tempfile
import unittest
from pathlib import Path

from review_harness.reporting import render_report
from review_harness.service import run_openalex_search
from review_harness.storage import (
    create_or_resume_topic_run,
    create_topic_run,
    finish_search_run,
    get_topic_run,
    module01_next_action,
    save_decision,
    save_module01_relevance,
    start_search_run,
    status_for_run,
)


class FakeOpenAlexClient:
    def search_works(self, **_: object):
        first = {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1000/shared",
            "title": "UV Computational Spectrometer",
            "publication_date": "2026-01-01",
            "publication_year": 2026,
            "type": "article",
            "abstract_inverted_index": {"UV": [0], "spectrometer": [1]},
            "primary_location": {"source": {"display_name": "Journal A", "issn_l": "1111-2222"}},
            "cited_by_count": 3,
        }
        duplicate = dict(first)
        duplicate["id"] = "https://openalex.org/W2"
        review = dict(first)
        review["id"] = "https://openalex.org/W3"
        review["doi"] = "https://doi.org/10.1000/review"
        review["title"] = "Review of UV Computational Spectrometers"
        review["type"] = "review"
        yield {
            "page_number": 1,
            "payload": {"meta": {"next_cursor": None}, "results": [first, duplicate, review]},
        }


class StorageAndServiceTests(unittest.TestCase):
    def test_offline_run_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "runtime" / "research.sqlite3"
            raw_root = root / "runtime" / "raw"
            output_root = root / "outputs"
            profile = {
                "schema_version": "0.1.0",
                "original_request": "围绕紫外微型计算光谱仪写一篇文献综述",
                "boundaries": {
                    "direct": "Direct boundary",
                    "technical": "Technical boundary",
                    "foundational": "Foundational boundary",
                    "excluded": "Excluded boundary",
                },
                "queries": [{
                    "id": "direct-test-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "UV computational spectrometer",
                }],
            }
            run_id = create_topic_run(db_path, "紫外微型计算光谱仪", profile)
            self.assertEqual(module01_next_action(db_path, run_id)["action"], "search_literature")

            result = run_openalex_search(
                db_path=db_path,
                raw_root=raw_root,
                topic_run_id=run_id,
                query_id="direct-test-01",
                client=FakeOpenAlexClient(),
            )
            self.assertEqual(result["records_received"], 3)
            self.assertEqual(result["non_research_records_filtered"], 1)
            self.assertEqual(result["new_unique_papers"], 1)
            self.assertEqual(result["matched_existing_papers"], 1)

            raw_directory = Path(result["raw_directory"])
            self.assertTrue((raw_directory / "manifest.json").exists())
            self.assertTrue((raw_directory / "page-0001.json").exists())
            manifest = json.loads((raw_directory / "manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("api_key", manifest)
            self.assertEqual(manifest["per_page"], 50)
            self.assertEqual(manifest["max_pages"], 1)
            self.assertEqual(int(manifest["to_date"][:4]) - int(manifest["from_date"][:4]), 2)
            screening_action = module01_next_action(db_path, run_id)
            self.assertEqual(screening_action["action"], "screen_papers")
            self.assertEqual(screening_action["paper_count"], 1)

            status = status_for_run(db_path, run_id)
            self.assertEqual(status["paper_counts_by_retrieval_scope"]["direct"], 1)
            self.assertEqual(Path(status["searches"][0]["raw_directory"]), raw_directory)
            self.assertEqual(save_module01_relevance(db_path, run_id, [{
                "paper_id": "W1",
                "label": "direct",
                "confidence": "high",
                "reason": "Title and abstract satisfy the exact topic boundary.",
                "actor": "test-classifier",
            }]), 1)
            self.assertEqual(status_for_run(db_path, run_id)["paper_counts_by_relevance"]["direct"], 1)
            ready_action = module01_next_action(db_path, run_id)
            self.assertEqual(ready_action["action"], "synthesize_report_and_collect_decision")
            self.assertTrue(ready_action["blocking_user_input"])

            report_path = render_report(db_path, run_id, output_root)
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("选题可行性评估", report)
            self.assertIn("紫外微型计算光谱仪研究论文 | 1 |", report)
            self.assertNotIn("相关综述", report)
            self.assertNotIn("中科院一区", report)
            self.assertIn("insufficient_evidence", report)

            decision = save_decision(db_path, run_id, "approved")
            self.assertTrue(decision["module_02_permitted"])
            self.assertEqual(status_for_run(db_path, run_id)["run"]["status"], "approved")
            self.assertEqual(module01_next_action(db_path, run_id)["action"], "start_module02")

    def test_search_budget_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_path = Path(temporary_directory) / "research.sqlite3"
            profile = {
                "schema_version": "0.1.0",
                "queries": [
                    {
                        "id": f"direct-{index}",
                        "scope": "direct",
                        "provider": "openalex",
                        "query": f"direct query {index}",
                    }
                    for index in range(4)
                ],
            }
            with self.assertRaisesRegex(ValueError, "at most 3 direct queries"):
                create_topic_run(db_path, "bounded topic", profile)

    def test_search_page_size_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = create_topic_run(db_path, "bounded topic", {
                "schema_version": "0.1.0",
                "queries": [{
                    "id": "direct-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "bounded query",
                }],
            })
            with self.assertRaisesRegex(ValueError, "at most 50 records"):
                run_openalex_search(
                    db_path=db_path,
                    raw_root=root / "raw",
                    topic_run_id=run_id,
                    query_id="direct-01",
                    per_page=51,
                    client=FakeOpenAlexClient(),
                )
    def test_same_topic_reuses_canonical_query_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_path = Path(temporary_directory) / "research.sqlite3"
            first = {
                "schema_version": "0.1.0",
                "topic": {"canonical_zh": "同一主题"},
                "queries": [{
                    "id": "direct-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "first frozen query",
                }],
            }
            second = {
                "schema_version": "0.1.0",
                "topic": {"canonical_zh": "同一主题"},
                "queries": [{
                    "id": "agent-rewrite",
                    "scope": "technical",
                    "provider": "openalex",
                    "query": "runtime attempted rewrite",
                }],
            }
            first_id = create_topic_run(db_path, "同一主题", first)
            second_id = create_topic_run(db_path, "同一主题", second)
            first_run = get_topic_run(db_path, first_id)
            second_run = get_topic_run(db_path, second_id)
            self.assertEqual(first_run["query_plan_sha256"], second_run["query_plan_sha256"])
            self.assertEqual(first_run["profile"]["queries"], second_run["profile"]["queries"])
            self.assertEqual(second_run["profile"]["queries"][0]["query"], "first frozen query")

    def test_unknown_query_id_cannot_override_frozen_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = create_topic_run(db_path, "locked topic", {
                "schema_version": "0.1.0",
                "queries": [{
                    "id": "direct-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "locked query",
                }],
            })
            with self.assertRaisesRegex(KeyError, "Unknown frozen query id"):
                run_openalex_search(
                    db_path=db_path,
                    raw_root=root / "raw",
                    topic_run_id=run_id,
                    query_id="agent-supplied-query",
                    client=FakeOpenAlexClient(),
                )
    def test_report_and_approval_require_semantic_screening(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = create_topic_run(db_path, "screening gate topic", {
                "schema_version": "0.1.0",
                "queries": [{
                    "id": "direct-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "screening gate topic",
                }],
            })
            run_openalex_search(
                db_path=db_path,
                raw_root=root / "raw",
                topic_run_id=run_id,
                query_id="direct-01",
                client=FakeOpenAlexClient(),
            )
            with self.assertRaisesRegex(ValueError, "semantic screening"):
                render_report(db_path, run_id, root / "outputs")
            with self.assertRaisesRegex(ValueError, "semantically unclassified"):
                save_decision(db_path, run_id, "approved")
    def test_create_or_resume_reuses_unfinished_same_topic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_path = Path(temporary_directory) / "research.sqlite3"
            profile = {
                "schema_version": "0.1.0",
                "topic": {"canonical_zh": "可恢复主题"},
                "queries": [{
                    "id": "direct-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "resumable topic",
                }],
            }
            first_id, first_resumed = create_or_resume_topic_run(db_path, "可恢复主题", profile)
            second_id, second_resumed = create_or_resume_topic_run(db_path, "可恢复主题", profile)
            self.assertFalse(first_resumed)
            self.assertTrue(second_resumed)
            self.assertEqual(first_id, second_id)
            self.assertEqual(module01_next_action(db_path, second_id)["action"], "search_literature")
            search_id = start_search_run(
                db_path,
                topic_run_id=first_id,
                query_id="direct-01",
                from_date="2024-11-03",
                to_date="2026-11-03",
                max_pages=1,
                raw_directory=Path(temporary_directory) / "raw",
            )
            finish_search_run(db_path, search_id, records_received=0)
            save_decision(db_path, first_id, "rejected")
            third_id, third_resumed = create_or_resume_topic_run(db_path, "可恢复主题", profile)
            self.assertFalse(third_resumed)
            self.assertNotEqual(third_id, first_id)


if __name__ == "__main__":
    unittest.main()
