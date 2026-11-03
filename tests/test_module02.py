import tempfile
import unittest
from datetime import date
from pathlib import Path

from review_harness.module02_reporting import (
    _review_selection_context,
    render_module02_report,
    render_module02_summary,
)
from review_harness.module02_service import run_post_review_research_search, run_review_search
from review_harness.module02_storage import (
    attach_perspective_sessions,
    create_module02_run,
    export_research,
    export_reviews,
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
    upsert_review,
)
from review_harness.reference_storage import save_nature_index_snapshot
from review_harness.storage import (
    create_topic_run,
    finish_search_run,
    save_decision,
    start_search_run,
)


class FakeReviewClient:
    def search_works(self, **_: object):
        yield {
            "page_number": 1,
            "payload": {
                "meta": {"next_cursor": None},
                "results": [{
                    "id": "https://openalex.org/R1",
                    "doi": "https://doi.org/10.1000/review1",
                    "title": "Review of UV Computational Spectrometers",
                    "publication_date": "2026-08-31",
                    "publication_year": 2026,
                    "type": "review",
                    "abstract_inverted_index": {"Review": [0], "UV": [1], "spectrometers": [2]},
                    "primary_location": {
                        "landing_page_url": "https://example.org/review1",
                        "source": {"display_name": "Review Journal", "issn_l": "1234-5678"},
                    },
                    "cited_by_count": 12,
                }],
            },
        }


class FakeResearchClient:
    def search_works(self, **_: object):
        yield {
            "page_number": 1,
            "payload": {
                "meta": {"next_cursor": None},
                "results": [{
                    "id": "https://openalex.org/P1",
                    "doi": "https://doi.org/10.1000/paper1",
                    "title": "A New UV Computational Spectrometer",
                    "publication_date": "2026-09-15",
                    "publication_year": 2026,
                    "type": "article",
                    "abstract_inverted_index": {"New": [0], "UV": [1], "spectrometer": [2]},
                    "primary_location": {
                        "source": {"display_name": "Research Journal", "issn_l": "2222-3333"}
                    },
                    "cited_by_count": 2,
                }],
            },
        }


class Module02Tests(unittest.TestCase):
    def _topic_run(self, db_path: Path, *, records_received: int = 0) -> str:
        run_id = create_topic_run(
            db_path,
            "紫外微型计算光谱仪",
            {
                "schema_version": "0.1.0",
                "topic": {"canonical_zh": "紫外微型计算光谱仪"},
                "display_labels": {
                    "exact_research_label": "紫外微型计算光谱仪研究论文",
                    "parent_research_label": "微型计算光谱仪研究论文",
                },
                "time_windows": {
                    "publication_from": "2024-11-03",
                    "publication_to": "2026-11-03",
                },
                "queries": [{
                    "id": "direct-en-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "UV computational spectrometer",
                }],
            },
        )
        search_id = start_search_run(
            db_path,
            topic_run_id=run_id,
            query_id="direct-en-01",
            from_date="2024-11-03",
            to_date="2026-11-03",
            max_pages=1,
            raw_directory=db_path.parent / "module01-test-raw",
        )
        finish_search_run(db_path, search_id, records_received=records_received)
        return run_id

    def test_module02_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_path = Path(temporary_directory) / "research.sqlite3"
            run_id = self._topic_run(db_path)
            with self.assertRaisesRegex(PermissionError, "explicit Module 01 decision"):
                create_module02_run(db_path, run_id)
            save_decision(db_path, run_id, "rejected")
            with self.assertRaisesRegex(PermissionError, "not permitted"):
                create_module02_run(db_path, run_id)

    def test_complete_module02_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = self._topic_run(db_path, records_received=50)
            save_decision(db_path, run_id, "approved")
            module02_run_id = create_module02_run(db_path, run_id)

            review_result = run_review_search(
                db_path=db_path,
                raw_root=root / "raw",
                module02_run_id=module02_run_id,
                query_id="review-typed-01",
                client=FakeReviewClient(),
            )
            self.assertEqual(review_result["new_reviews_retained"], 1)
            review = export_reviews(db_path, module02_run_id)[0]
            save_review_screening(db_path, module02_run_id, [{
                "review_id": review["id"],
                "match_level": "exact",
                "relevance_score": 1.0,
                "matched_keywords": ["UV computational spectrometer"],
                "confidence": "high",
                "reason": "The complete topic is central to the review.",
            }])
            pdf_path = root / "review.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n% test fixture\n")
            save_fulltext_access(db_path, module02_run_id, [{
                "review_id": review["id"],
                "status": "institutional_downloaded",
                "source_url": "https://example.org/review1.pdf",
                "pdf_path": str(pdf_path.resolve()),
                "license": "institutional-reading-access",
                "note": "User completed SSO in the institution browser.",
            }])
            save_review_analyses(db_path, module02_run_id, [{
                "review_id": review["id"],
                "review_match_level": "exact",
                "nature_index_status": "no",
                "fulltext_access_status": "institutional_downloaded",
                "evidence_level": "full_text",
                "review_reason": "The field needed a synthesis.",
                "structure": ["Devices", "Reconstruction"],
                "future_trends": ["Wider ultraviolet coverage"],
                "source_urls": ["https://example.org/review1"],
                "limitations": [],
            }])
            save_trend_claims(db_path, module02_run_id, [{
                "trend_id": "trend_wider_uv",
                "canonical_label": "Wider ultraviolet coverage",
                "description": "Extend reconstruction across a wider ultraviolet band.",
                "source_review_ids": [review["id"]],
                "source_statements": ["Future devices should cover a wider ultraviolet range."],
                "scope_note": None,
            }])

            anchor = finalize_review_anchor(db_path, module02_run_id, as_of=date(2026, 11, 3))
            self.assertEqual(anchor["newest_review_date"], "2026-08-31")
            self.assertEqual(anchor["research_from_date"], "2026-02-28")
            self.assertEqual(anchor["research_to_date"], "2026-11-03")

            research_result = run_post_review_research_search(
                db_path=db_path,
                raw_root=root / "raw",
                module02_run_id=module02_run_id,
                query_id="direct-en-01",
                client=FakeResearchClient(),
            )
            self.assertEqual(research_result["new_research_records"], 1)
            paper = export_research(db_path, module02_run_id)[0]
            save_research_comparisons(db_path, module02_run_id, [{
                "paper_id": paper["id"],
                "category": "trend_extension",
                "matched_review_ids": [review["id"]],
                "matched_trend_claim_ids": ["trend_wider_uv"],
                "matched_future_trends": ["Wider ultraviolet coverage"],
                "rationale": "Extends the predicted wavelength range.",
                "confidence": "high",
            }])
            finalize_research_comparison(db_path, module02_run_id)
            save_perspectives(db_path, module02_run_id, [{
                "rank": 1,
                "candidate_title": "Ultraviolet pathways for computational spectrometers",
                "central_question": "How can mature architectures move into the UV?",
                "supporting_review_ids": [review["id"]],
                "supporting_paper_ids": [paper["id"]],
                "similarities": ["Uses the same device taxonomy"],
                "differences": ["Centers ultraviolet constraints"],
                "recommended_scope": "UV materials, encoding, calibration, and benchmarks",
                "risks": ["Small exact-topic corpus"],
            }, {
                "rank": 2,
                "candidate_title": "Reliability benchmarks for UV computational spectrometers",
                "central_question": "Which stability metrics permit fair comparison?",
                "supporting_review_ids": [review["id"]],
                "supporting_paper_ids": [paper["id"]],
                "similarities": ["Uses the same reconstruction literature"],
                "differences": ["Centers measurement reliability"],
                "recommended_scope": "Calibration drift, noise, and benchmark spectra",
                "risks": ["Limited raw measurements"],
            }, {
                "rank": 3,
                "candidate_title": "Manufacturing pathways for UV computational spectrometers",
                "central_question": "Which fabrication routes can scale reliably?",
                "supporting_review_ids": [review["id"]],
                "supporting_paper_ids": [paper["id"]],
                "similarities": ["Uses the same device evidence"],
                "differences": ["Centers manufacturability"],
                "recommended_scope": "Scalable fabrication and integration",
                "risks": ["Limited yield reporting"],
            }])
            self.assertEqual(get_module02_run(db_path, module02_run_id)["status"], "perspectives_ready")
            branches = list_perspective_branches(db_path, module02_run_id)
            self.assertEqual(len(branches), 3)
            self.assertTrue(all(branch["status"] == "available" for branch in branches))
            attach_perspective_sessions(db_path, module02_run_id, [
                {"rank": 1, "session_id": "session-perspective-1"},
                {"rank": 2, "session_id": "session-perspective-2"},
                {"rank": 3, "session_id": "session-perspective-3"},
            ])
            rebuilt = rebuild_perspective_selection(db_path, module02_run_id)
            self.assertEqual(len(rebuilt["options"]), 3)
            self.assertEqual(rebuilt["message"], "请选择视角以开始Module 03大纲设计")
            selected = select_perspective_branch(db_path, module02_run_id, 1)
            self.assertEqual(selected["status"], "selected_for_module03")
            self.assertEqual(selected["dsh_session_id"], "session-perspective-1")
            self.assertEqual(selected["message"], "Module 03大纲设计已授权")
            second = select_perspective_branch(db_path, module02_run_id, 2)
            self.assertEqual(second["dsh_session_id"], "session-perspective-2")
            third = select_perspective_branch(db_path, module02_run_id, 3)
            self.assertEqual(third["dsh_session_id"], "session-perspective-3")
            selected_branches = list_perspective_branches(db_path, module02_run_id)
            self.assertTrue(all(branch["status"] == "selected_for_module03" for branch in selected_branches))
            rebuilt_after = rebuild_perspective_selection(db_path, module02_run_id)
            self.assertTrue(all(option["branch_status"] == "selected_for_module03" for option in rebuilt_after["options"]))
            self.assertEqual(rebuilt_after["message"], "请选择视角以开始Module 03大纲设计")

            report_path = render_module02_report(db_path, module02_run_id, root / "outputs")
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("综述格局与最新研究分析", report)
            self.assertIn("Review of UV Computational Spectrometers", report)
            self.assertIn("对综述趋势的延伸", report)
            self.assertIn("Ultraviolet pathways for computational spectrometers", report)
            summary_path = render_module02_summary(db_path, module02_run_id, root / "outputs")
            summary = summary_path.read_text(encoding="utf-8")
            self.assertIn("Module 02简报", summary)
            self.assertIn("标准化TrendClaim：1条", summary)
            self.assertIn("session-perspective-1", summary)

    def test_no_review_branch_reuses_module01_and_nature_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = self._topic_run(db_path)
            snapshot_id = save_nature_index_snapshot(db_path, run_id, {
                "source_url": "https://www.nature.com/nature-index/faq",
                "retrieved_at": "2026-11-03T00:00:00+00:00",
                "edition": "2026-06",
                "content_sha256": "a" * 64,
                "stated_journal_count": 1,
                "stated_other_venue_count": 0,
                "publications": [{
                    "canonical_name": "Example Journal",
                    "publication_type": "journal",
                    "issn": None,
                    "eissn": None,
                    "restriction_note": None,
                }],
            })
            save_decision(db_path, run_id, "approved")
            module02_run_id = create_module02_run(db_path, run_id)
            self.assertEqual(get_module02_run(db_path, module02_run_id)["nature_index_snapshot_id"], snapshot_id)

            save_trend_claims(db_path, module02_run_id, [])
            anchor = finalize_review_anchor(db_path, module02_run_id, as_of=date(2026, 11, 3))
            self.assertEqual(anchor["branch"], "no_related_reviews")
            self.assertIsNone(anchor["newest_review_id"])
            self.assertIsNone(anchor["trend_baseline_review_id"])
            self.assertEqual(anchor["research_from_date"], "2024-11-03")
            plan = plan_module02_research_queries(db_path, module02_run_id)
            self.assertEqual(plan[0]["action"], "reuse_module01")
            with self.assertRaisesRegex(ValueError, "does not need retrieval"):
                run_post_review_research_search(
                    db_path=db_path,
                    raw_root=root / "raw",
                    module02_run_id=module02_run_id,
                    query_id="direct-en-01",
                    client=FakeResearchClient(),
                )
            finalize_research_comparison(db_path, module02_run_id)
            save_perspectives(db_path, module02_run_id, [{
                "rank": 1,
                "candidate_title": "First focused review of the emerging topic",
                "central_question": "How has the new research cluster formed?",
                "supporting_review_ids": [],
                "supporting_paper_ids": [],
                "similarities": [],
                "differences": ["No prior topic-specific review was found"],
                "recommended_scope": "Use the Module 01 two-year research corpus",
                "risks": ["No review baseline exists"],
            }, {
                "rank": 2,
                "candidate_title": "Methods and benchmarks in the emerging topic",
                "central_question": "Which methods and metrics can be compared?",
                "supporting_review_ids": [],
                "supporting_paper_ids": [],
                "similarities": [],
                "differences": ["Builds a benchmark taxonomy without a review baseline"],
                "recommended_scope": "Methods and evaluation",
                "risks": ["Sparse evidence"],
            }, {
                "rank": 3,
                "candidate_title": "Applications and unresolved boundaries",
                "central_question": "Where are the strongest emerging applications?",
                "supporting_review_ids": [],
                "supporting_paper_ids": [],
                "similarities": [],
                "differences": ["Maps applications directly from research clusters"],
                "recommended_scope": "Applications and limitations",
                "risks": ["No review baseline exists"],
            }])
            self.assertEqual(len(list_perspective_branches(db_path, module02_run_id)), 3)
            rebuilt = rebuild_perspective_selection(db_path, module02_run_id)
            self.assertEqual(rebuilt["options"][0]["session_id"], None)
            selected = select_perspective_branch(db_path, module02_run_id, 1)
            self.assertEqual(selected["message"], "Module 03大纲设计已授权")

    def test_time_anchor_and_trend_baseline_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = self._topic_run(db_path)
            save_decision(db_path, run_id, "approved")
            module02_run_id = create_module02_run(db_path, run_id)

            older_id, _ = upsert_review(db_path, module02_run_id, {
                "openalex_id": "https://openalex.org/R-older",
                "doi": "10.1000/older",
                "title": "Older Full Review",
                "normalized_title": "older full review",
                "abstract": "Abstract",
                "publication_date": "2026-08-31",
                "publication_year": 2026,
                "journal": "Journal",
                "issn_l": "1234-5678",
                "cited_by_count": 3,
                "citation_as_of": "2026-11-03T00:00:00+00:00",
                "paper_url": "https://doi.org/10.1000/older",
            })
            newer_id, _ = upsert_review(db_path, module02_run_id, {
                "openalex_id": "https://openalex.org/R-newer",
                "doi": "10.1000/newer",
                "title": "Newer Abstract Review",
                "normalized_title": "newer abstract review",
                "abstract": "Abstract",
                "publication_date": "2026-10-01",
                "publication_year": 2026,
                "journal": "Journal",
                "issn_l": "1234-5678",
                "cited_by_count": 1,
                "citation_as_of": "2026-11-03T00:00:00+00:00",
                "paper_url": "https://doi.org/10.1000/newer",
            })
            pdf_path = root / "older.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n% fixture\n")
            save_review_screening(db_path, module02_run_id, [
                {"review_id": older_id, "match_level": "exact", "relevance_score": 1.0, "matched_keywords": ["UV"], "confidence": "high", "reason": "Exact topic."},
                {"review_id": newer_id, "match_level": "exact", "relevance_score": 1.0, "matched_keywords": ["UV"], "confidence": "high", "reason": "Exact topic."},
            ])
            save_fulltext_access(db_path, module02_run_id, [
                {
                    "review_id": older_id,
                    "status": "oa_downloaded",
                    "source_url": "https://example.org/older.pdf",
                    "pdf_path": str(pdf_path.resolve()),
                    "license": "open",
                    "note": None,
                },
                {
                    "review_id": newer_id,
                    "status": "skipped",
                    "source_url": "https://example.org/newer",
                    "pdf_path": None,
                    "license": None,
                    "note": "No full text available.",
                },
            ])
            save_review_analyses(db_path, module02_run_id, [
                {
                    "review_id": older_id,
                    "review_match_level": "exact",
                    "nature_index_status": "no",
                    "fulltext_access_status": "oa_downloaded",
                    "evidence_level": "full_text",
                    "review_reason": "Full review",
                    "structure": ["Methods"],
                    "future_trends": ["Trend A"],
                    "source_urls": ["https://example.org/older.pdf"],
                    "limitations": [],
                },
                {
                    "review_id": newer_id,
                    "review_match_level": "exact",
                    "nature_index_status": "no",
                    "fulltext_access_status": "skipped",
                    "evidence_level": "abstract_only",
                    "review_reason": "Abstract evidence",
                    "structure": [],
                    "future_trends": [],
                    "source_urls": ["https://example.org/newer"],
                    "limitations": ["No full text"],
                },
            ])
            save_trend_claims(db_path, module02_run_id, [])
            anchor = finalize_review_anchor(db_path, module02_run_id, as_of=date(2026, 11, 3))
            self.assertEqual(anchor["newest_review_id"], newer_id)
            self.assertEqual(anchor["trend_baseline_review_id"], older_id)
            self.assertEqual(anchor["research_from_date"], "2026-04-01")

    def test_unsubscribed_review_is_skipped_and_cannot_claim_full_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = self._topic_run(db_path)
            save_decision(db_path, run_id, "approved")
            module02_run_id = create_module02_run(db_path, run_id)
            run_review_search(
                db_path=db_path,
                raw_root=root / "raw",
                module02_run_id=module02_run_id,
                query_id="review-typed-01",
                client=FakeReviewClient(),
            )
            review = export_reviews(db_path, module02_run_id)[0]
            save_review_screening(db_path, module02_run_id, [{
                "review_id": review["id"],
                "match_level": "exact",
                "relevance_score": 1.0,
                "matched_keywords": ["UV computational spectrometer"],
                "confidence": "high",
                "reason": "The complete topic is central to the review.",
            }])
            save_fulltext_access(db_path, module02_run_id, [{
                "review_id": review["id"],
                "status": "institution_not_subscribed",
                "source_url": "https://example.org/review1",
                "pdf_path": None,
                "license": None,
                "note": "Institution login succeeded but no entitlement was available.",
            }])
            with self.assertRaisesRegex(ValueError, "requires a registered PDF"):
                save_review_analyses(db_path, module02_run_id, [{
                    "review_id": review["id"],
                    "review_match_level": "exact",
                    "nature_index_status": "no",
                    "fulltext_access_status": "institution_not_subscribed",
                    "evidence_level": "full_text",
                    "review_reason": "Unsupported full-text claim.",
                    "structure": ["Should not be accepted"],
                    "future_trends": [],
                    "source_urls": ["https://example.org/review1"],
                    "limitations": [],
                }])
    def test_adjacent_review_fallback_keeps_top_five_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = self._topic_run(db_path)
            save_decision(db_path, run_id, "approved")
            module02_run_id = create_module02_run(db_path, run_id)
            records = []
            for rank in range(1, 7):
                review_id, _ = upsert_review(db_path, module02_run_id, {
                    "openalex_id": f"https://openalex.org/AR{rank}",
                    "doi": f"10.1000/adjacent{rank}",
                    "title": f"Adjacent Review {rank}",
                    "normalized_title": f"adjacent review {rank}",
                    "abstract": "Computational spectrometer technology review.",
                    "publication_date": f"2026-0{rank}-01",
                    "publication_year": 2026,
                    "journal": "Review Journal",
                    "issn_l": None,
                    "cited_by_count": rank,
                    "citation_as_of": "2026-11-03T00:00:00+00:00",
                    "paper_url": f"https://doi.org/10.1000/adjacent{rank}",
                })
                records.append({
                    "review_id": review_id,
                    "match_level": "adjacent",
                    "relevance_score": rank / 10,
                    "matched_keywords": ["computational spectrometer"],
                    "confidence": "high",
                    "reason": "Covers an important parent technology.",
                })
            save_review_screening(db_path, module02_run_id, records)
            included = export_reviews(db_path, module02_run_id, included_only=True)
            self.assertEqual(len(included), 5)
            self.assertNotIn("Adjacent Review 1", {item["title"] for item in included})
            self.assertTrue(all(item["review_match_level"] == "adjacent" for item in included))
            save_fulltext_access(db_path, module02_run_id, [
                {
                    "review_id": item["id"],
                    "status": "skipped",
                    "source_url": item["paper_url"],
                    "pdf_path": None,
                    "license": None,
                    "note": "No legal PDF was available.",
                }
                for item in included
            ])
            save_review_analyses(db_path, module02_run_id, [
                {
                    "review_id": item["id"],
                    "review_match_level": "adjacent",
                    "nature_index_status": "no",
                    "fulltext_access_status": "skipped",
                    "evidence_level": "abstract_only",
                    "review_reason": "Adjacent abstract evidence.",
                    "structure": [],
                    "future_trends": [],
                    "source_urls": [item["paper_url"]],
                    "limitations": ["No legal full text"],
                }
                for item in included
            ])
            save_trend_claims(db_path, module02_run_id, [])
            anchor = finalize_review_anchor(db_path, module02_run_id, as_of=date(2026, 11, 3))
            self.assertEqual(anchor["branch"], "adjacent_review_fallback")
            self.assertIn(anchor["newest_review_id"], {item["id"] for item in included})

    def test_exact_reviews_disable_adjacent_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = self._topic_run(db_path)
            save_decision(db_path, run_id, "approved")
            module02_run_id = create_module02_run(db_path, run_id)
            screening = []
            for rank, match_level in enumerate(("exact", "adjacent"), start=1):
                review_id, _ = upsert_review(db_path, module02_run_id, {
                    "openalex_id": f"https://openalex.org/ER{rank}",
                    "doi": f"10.1000/exact-fallback{rank}",
                    "title": f"Review {rank}",
                    "normalized_title": f"review {rank}",
                    "abstract": "Review abstract.",
                    "publication_date": "2026-01-01",
                    "publication_year": 2026,
                    "journal": "Review Journal",
                    "issn_l": None,
                    "cited_by_count": rank,
                    "citation_as_of": "2026-11-03T00:00:00+00:00",
                    "paper_url": f"https://doi.org/10.1000/exact-fallback{rank}",
                })
                screening.append({
                    "review_id": review_id,
                    "match_level": match_level,
                    "relevance_score": 1.0 if match_level == "exact" else 0.9,
                    "matched_keywords": ["UV computational spectrometer"],
                    "confidence": "high",
                    "reason": "Screened against the frozen topic.",
                })
            save_review_screening(db_path, module02_run_id, screening)
            included = export_reviews(db_path, module02_run_id, included_only=True)
            self.assertEqual([item["review_match_level"] for item in included], ["exact"])
    def test_module02_next_action_drives_nonblocking_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            run_id = self._topic_run(db_path, records_received=50)
            save_decision(db_path, run_id, "approved")
            module02_run_id = create_module02_run(db_path, run_id)
            with self.assertRaisesRegex(ValueError, "module02-next"):
                render_module02_summary(db_path, module02_run_id, root / "outputs")
            first = module02_next_action(db_path, module02_run_id)
            self.assertEqual(first["action"], "search_reviews")
            self.assertEqual(len(first["queries"]), 2)
            for query in first["queries"]:
                run_review_search(
                    db_path=db_path,
                    raw_root=root / "raw",
                    module02_run_id=module02_run_id,
                    query_id=query["id"],
                    client=FakeReviewClient(),
                )
            self.assertEqual(module02_next_action(db_path, module02_run_id)["action"], "screen_reviews")
            review = export_reviews(db_path, module02_run_id)[0]
            save_review_screening(db_path, module02_run_id, [{
                "review_id": review["id"],
                "match_level": "exact",
                "relevance_score": 1.0,
                "matched_keywords": ["UV computational spectrometer"],
                "confidence": "high",
                "reason": "Exact topic.",
            }])
            self.assertEqual(module02_next_action(db_path, module02_run_id)["action"], "check_fulltext")
            save_fulltext_access(db_path, module02_run_id, [{
                "review_id": review["id"],
                "status": "login_required",
                "source_url": review["paper_url"],
                "pdf_path": None,
                "license": None,
                "note": "No legal open PDF; institutional choice required.",
            }])
            access_action = module02_next_action(db_path, module02_run_id)
            self.assertEqual(access_action["action"], "request_institutional_access")
            self.assertTrue(access_action["blocking_user_input"])
            self.assertEqual(len(access_action["prompt"]), 3)
            with self.assertRaisesRegex(ValueError, "Resolve institutional access choice"):
                save_review_analyses(db_path, module02_run_id, [{
                    "review_id": review["id"],
                    "review_match_level": "exact",
                    "nature_index_status": "no",
                    "fulltext_access_status": "login_required",
                    "evidence_level": "abstract_only",
                    "review_reason": "Must not pass while login is pending.",
                    "structure": [],
                    "future_trends": [],
                    "source_urls": [review["paper_url"]],
                    "limitations": [],
                }])
            save_fulltext_access(db_path, module02_run_id, [{
                "review_id": review["id"],
                "status": "skipped",
                "source_url": review["paper_url"],
                "pdf_path": None,
                "license": None,
                "note": "User chose abstract-only continuation.",
            }])
            self.assertEqual(module02_next_action(db_path, module02_run_id)["action"], "analyze_reviews")
            save_review_analyses(db_path, module02_run_id, [{
                "review_id": review["id"],
                "review_match_level": "exact",
                "nature_index_status": "no",
                "fulltext_access_status": "skipped",
                "evidence_level": "abstract_only",
                "review_reason": "Abstract evidence only.",
                "structure": [],
                "future_trends": [],
                "source_urls": [review["paper_url"]],
                "limitations": ["No legal full text"],
            }])
            self.assertEqual(module02_next_action(db_path, module02_run_id)["action"], "normalize_trend_claims")
            save_trend_claims(db_path, module02_run_id, [])
            self.assertEqual(module02_next_action(db_path, module02_run_id)["action"], "finalize_review_anchor")
            finalize_review_anchor(db_path, module02_run_id, as_of=date(2026, 11, 3))
            self.assertEqual(module02_next_action(db_path, module02_run_id)["action"], "search_research")
    def test_adjacent_selection_message_is_explicit(self) -> None:
        context = _review_selection_context([
            {"review_match_level": "adjacent"},
            {"review_match_level": "adjacent"},
        ])
        self.assertEqual(context["mode"], "adjacent_review_fallback")
        self.assertIn("未发现同时锚定全部核心关键词", context["message"])
        self.assertIn("以下2篇", context["message"])
        self.assertIn("按Module 02相同证据流程", context["message"])


if __name__ == "__main__":
    unittest.main()
