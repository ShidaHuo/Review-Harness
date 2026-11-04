import tempfile
import unittest
from datetime import date
from pathlib import Path

from review_harness.module03_reporting import render_outline
from review_harness.module03_storage import (
    get_module03_run,
    latest_outline,
    module03_next_action,
    record_outline_feedback,
    save_outline_version,
    start_module03_outline,
)
from review_harness.module04_service import (
    _body_character_count,
    export_manuscript_markdown,
    module04_next_action,
    save_complete_manuscript,
    start_module04_manuscript,
)
from review_harness.module02_storage import (
    create_module02_run,
    finalize_research_comparison,
    finalize_review_anchor,
    save_perspectives,
    save_research_comparisons,
    save_trend_claims,
    select_perspective_branch,
    upsert_module02_research,
)
from review_harness.storage import (
    create_topic_run,
    finish_search_run,
    save_decision,
    start_search_run,
)


class Module03Tests(unittest.TestCase):
    def _module02_with_perspectives(self, db_path: Path) -> str:
        topic_run_id = create_topic_run(db_path, "测试主题", {
            "schema_version": "0.1.0",
            "topic": {"canonical_zh": "测试主题"},
            "time_windows": {"publication_from": "2024-11-03", "publication_to": "2026-11-03"},
            "queries": [{
                "id": "direct-01",
                "scope": "direct",
                "provider": "openalex",
                "query": "test topic",
            }],
        })
        search_id = start_search_run(
            db_path,
            topic_run_id=topic_run_id,
            query_id="direct-01",
            from_date="2024-11-03",
            to_date="2026-11-03",
            max_pages=1,
            raw_directory=db_path.parent / "module01-raw",
        )
        finish_search_run(db_path, search_id, records_received=0)
        save_decision(db_path, topic_run_id, "approved")
        module02_run_id = create_module02_run(db_path, topic_run_id)
        save_trend_claims(db_path, module02_run_id, [])
        finalize_review_anchor(db_path, module02_run_id, as_of=date(2026, 11, 3))
        paper_id, _ = upsert_module02_research(
            db_path,
            module02_run_id,
            {
                "paper_id": "W-EVIDENCE",
                "openalex_id": "https://openalex.org/W-EVIDENCE",
                "doi": "10.1000/evidence",
                "title": "Evidence Paper on Reconfigurable Logic",
                "normalized_title": "evidence paper on reconfigurable logic",
                "abstract": "The paper demonstrates a low-voltage reconfigurable logic device.",
                "publication_date": "2026-01-15",
                "publication_year": 2026,
                "work_type": "article",
                "source_name": "Test Journal",
                "issn_l": None,
                "cited_by_count": 2,
                "source_provider": "openalex",
                "retrieved_at": "2026-11-03T00:00:00+00:00",
            },
            origin="module02",
            scope="direct",
        )
        save_research_comparisons(db_path, module02_run_id, [{
            "paper_id": paper_id,
            "category": "new_direction",
            "matched_review_ids": [],
            "matched_trend_claim_ids": [],
            "matched_future_trends": [],
            "rationale": "Demonstrates low-voltage reconfigurable operation as a new device direction.",
            "confidence": "high",
        }])
        finalize_research_comparison(db_path, module02_run_id)
        save_perspectives(db_path, module02_run_id, [
            self._perspective(1, "评测基准"),
            self._perspective(2, "器件演化"),
            self._perspective(3, "系统集成"),
        ])
        return module02_run_id

    @staticmethod
    def _perspective(rank: int, title: str) -> dict:
        return {
            "rank": rank,
            "candidate_title": title,
            "central_question": f"视角{rank}的核心问题是什么？",
            "supporting_review_ids": [],
            "supporting_paper_ids": ["W-EVIDENCE"],
            "similarities": [],
            "differences": ["独立组织视角"],
            "recommended_scope": "测试范围",
            "risks": ["证据有限"],
        }

    @staticmethod
    def _outline(run_id: str, title: str) -> dict:
        def section(number: str, section_title: str, level: int) -> dict:
            return {
                "number": number,
                "title": section_title,
                "level": level,
                "purpose": f"说明{section_title}的任务。",
                "writing_logic": ["先界定问题", "再组织证据", "最后形成小结"],
                "rationale": f"该部分支撑{section_title}的整体叙事。",
                "key_questions": [f"{section_title}需要回答什么？"],
                "evidence_ids": ["W-EVIDENCE"] if number not in {"1", "4"} else [],
                "expected_takeaway": f"读者理解{section_title}。",
                "transition": None if number == "1" else "承接前文并引出下一部分。",
            }
        return {
            "schema_version": "0.1.0",
            "module03_run_id": run_id,
            "candidate_title": title,
            "title_rationale": "题目直接对应所选视角。",
            "organizing_principle": "按问题、机制和证据递进。",
            "intended_audience": "相关领域研究人员",
            "scope_statement": "只覆盖所选视角内的研究。",
            "sections": [
                section("1", "Introduction", 1),
                section("2", "Theoretical foundations and mechanisms", 1),
                section("2.1", "Input models", 2),
                section("2.1.1", "Linear mechanisms", 3),
                section("2.1.2", "Nonlinear mechanisms", 3),
                section("2.2", "Operational schemes", 2),
                section("3", "Performance evaluation", 1),
                section("3.1", "Metrics", 2),
                section("3.2", "Benchmarks", 2),
                section("4", "Future perspective", 1),
                section("4.1", "Scalable systems", 2),
                section("4.2", "Reliability", 2),
            ],
        }

    @staticmethod
    def _complete_manuscript(module04_run_id: str, outline: dict) -> dict:
        parts = [f"# {outline['candidate_title']}", "## 摘要", "本文围绕冻结视角综述相关研究。", "**关键词：**测试；综述"]
        for item in outline["sections"]:
            heading = "#" * (item["level"] + 1)
            parts.append(f"{heading} {item['number']} {item['title']}")
            parts.append(f"本节按照既定逻辑讨论{item['title']}。")
        parts.extend([
            "> **[图 1 置于此处：研究机制与评价框架]**",
            "> 建议内容：绘制机制、方法与指标之间的关系。",
            "> **[表 1 置于此处：代表性研究比较]**",
            "> 建议列项：研究对象、方法、结果和局限。",
        ])
        draft = "\n\n".join(parts)
        filler = "分析" * 6500
        draft = draft.replace("## 参考文献", "") + "\n\n" + filler
        current = _body_character_count(draft)
        if current < 15_000:
            draft += "补" * (15_000 - current)
        draft += "\n\n## 参考文献\n\n1. Evidence Paper on Reconfigurable Logic. Test Journal, 2026."
        return {
            "schema_version": "0.1.0",
            "module04_run_id": module04_run_id,
            "markdown": draft,
            "evidence_ids": ["W-EVIDENCE"],
        }

    def test_outline_granularity_and_direct_manuscript(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            module02_run_id = self._module02_with_perspectives(db_path)
            select_perspective_branch(db_path, module02_run_id, 1)
            module03_run_id = start_module03_outline(db_path, module02_run_id, 1)
            outline = self._outline(module03_run_id, "Review title")
            self.assertEqual(save_outline_version(db_path, module03_run_id, outline, actor="test"), 1)
            rendered = render_outline(db_path, module03_run_id, root / "outputs").read_text(encoding="utf-8")
            self.assertIn("Evidence Paper on Reconfigurable Logic", rendered)
            self.assertNotIn("W-EVIDENCE", rendered)
            record_outline_feedback(db_path, module03_run_id, "approved")
            module04_run_id = start_module04_manuscript(db_path, module03_run_id)
            action = module04_next_action(db_path, module04_run_id)
            self.assertEqual(action["action"], "write_complete_manuscript")
            self.assertTrue(action["must_continue"])
            manuscript = self._complete_manuscript(module04_run_id, outline)
            saved = save_complete_manuscript(db_path, module04_run_id, manuscript)
            self.assertGreaterEqual(saved["body_characters"], 13_500)
            self.assertEqual(module04_next_action(db_path, module04_run_id)["action"], "export_markdown")
            exported = export_manuscript_markdown(db_path, module04_run_id, root / "outputs" / "final")
            self.assertEqual(exported["message"], "MVP任务完成")
            final = Path(exported["output_path"]).read_text(encoding="utf-8")
            self.assertIn("## 2 Theoretical foundations and mechanisms", final)
            self.assertIn("### 3.2 Benchmarks", final)
            self.assertIn("[图 1 置于此处", final)
            self.assertNotIn("W-EVIDENCE", final)
            self.assertEqual(module04_next_action(db_path, module04_run_id)["action"], "mvp_complete")
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "mvp_complete")

    def test_outline_granularity_gate_rejects_shallow_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_path = Path(temporary_directory) / "research.sqlite3"
            module02_run_id = self._module02_with_perspectives(db_path)
            select_perspective_branch(db_path, module02_run_id, 1)
            module03_run_id = start_module03_outline(db_path, module02_run_id, 1)
            outline = self._outline(module03_run_id, "Shallow outline")
            outline["sections"] = [
                item for item in outline["sections"]
                if item["number"] not in {"3.1", "3.2"}
            ]
            with self.assertRaisesRegex(ValueError, "at least two second-level sections"):
                save_outline_version(db_path, module03_run_id, outline, actor="test")
            no_third_level = self._outline(module03_run_id, "No third level")
            no_third_level["sections"] = [
                item for item in no_third_level["sections"]
                if item["level"] != 3
            ]
            with self.assertRaisesRegex(ValueError, "requires at least one third-level section"):
                save_outline_version(db_path, module03_run_id, no_third_level, actor="test")

    def test_each_perspective_has_independent_outline_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_path = Path(temporary_directory) / "research.sqlite3"
            module02_run_id = self._module02_with_perspectives(db_path)
            select_perspective_branch(db_path, module02_run_id, 1)
            first = start_module03_outline(db_path, module02_run_id, 1)
            select_perspective_branch(db_path, module02_run_id, 2)
            second = start_module03_outline(db_path, module02_run_id, 2)
            self.assertNotEqual(first, second)
            self.assertEqual(start_module03_outline(db_path, module02_run_id, 1), first)
            self.assertEqual(get_module03_run(db_path, first)["current_version"], 0)
            self.assertEqual(get_module03_run(db_path, second)["current_version"], 0)


if __name__ == "__main__":
    unittest.main()
