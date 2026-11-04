import tempfile
import unittest
import zipfile
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
    assemble_manuscript,
    module04_export_for_run,
    module04_next_action,
    save_manuscript_section,
    start_module04_manuscript,
)
from review_harness.module05_service import (
    export_final_docx,
    module05_next_action,
    save_manuscript_evaluation,
    save_revised_manuscript,
    start_module05_evaluation,
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
            "time_windows": {
                "publication_from": "2024-11-03",
                "publication_to": "2026-11-03",
            },
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
                "evidence_ids": ["W-EVIDENCE"] if number == "2.1" else [],
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
                section("2", "Theoretical foundations", 1),
                section("2.1", "Operational schemes", 2),
                section("3", "Future perspective", 1),
            ],
        }

    def test_outline_iteration_and_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "research.sqlite3"
            module02_run_id = self._module02_with_perspectives(db_path)
            with self.assertRaisesRegex(PermissionError, "Select the perspective"):
                start_module03_outline(db_path, module02_run_id, 1)
            select_perspective_branch(db_path, module02_run_id, 1)
            module03_run_id = start_module03_outline(db_path, module02_run_id, 1)
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "create_outline")

            version = save_outline_version(
                db_path,
                module03_run_id,
                self._outline(module03_run_id, "Review title v1"),
                actor="test-agent",
            )
            self.assertEqual(version, 1)
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "collect_outline_feedback")
            path = render_outline(db_path, module03_run_id, root / "outputs")
            rendered = path.read_text(encoding="utf-8")
            self.assertIn("分级写作大纲", rendered)
            self.assertIn("写作逻辑", rendered)
            self.assertIn("这样安排的原因", rendered)
            self.assertIn("Evidence Paper on Reconfigurable Logic", rendered)
            self.assertIn("Demonstrates low-voltage reconfigurable operation", rendered)
            self.assertNotIn("W-EVIDENCE", rendered)

            record_outline_feedback(
                db_path,
                module03_run_id,
                "revise",
                "加强理论基础与未来展望之间的衔接。",
            )
            next_action = module03_next_action(db_path, module03_run_id)
            self.assertEqual(next_action["action"], "revise_outline")
            self.assertIn("加强理论基础", next_action["latest_feedback"])
            self.assertEqual(
                save_outline_version(
                    db_path,
                    module03_run_id,
                    self._outline(module03_run_id, "Review title v2"),
                    actor="test-agent",
                ),
                2,
            )
            record_outline_feedback(db_path, module03_run_id, "approved")
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "run_module04")
            self.assertEqual(get_module03_run(db_path, module03_run_id)["status"], "outline_approved")
            self.assertEqual(latest_outline(db_path, module03_run_id)["version"], 2)
            module04_run_id = start_module04_manuscript(db_path, module03_run_id)
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "continue_module04")
            while True:
                action = module04_next_action(db_path, module04_run_id)
                if action["action"] != "draft_manuscript_sections":
                    break
                for section in action["sections"]:
                    cite = section["section_key"] == "2"
                    marker = "[@W-EVIDENCE]" if cite else ""
                    markdown = (
                        f"## {section['section_title']}\n\n"
                        + "论述" * (section["target_characters"] // 2)
                        + marker
                    )
                    figures = []
                    tables = []
                    if section["section_key"] == "2":
                        figures = [{
                            "title": "器件机制示意图",
                            "purpose": "解释器件工作机制",
                            "content_spec": "绘制材料、界面和传输路径",
                            "source_evidence_ids": ["W-EVIDENCE"],
                        }]
                    if section["section_key"] == "3":
                        tables = [{
                            "title": "代表性性能比较",
                            "purpose": "比较关键性能指标",
                            "content_spec": "列出器件类型、工作电压和应用",
                            "source_evidence_ids": ["W-EVIDENCE"],
                        }]
                    save_manuscript_section(db_path, module04_run_id, {
                        "section_key": section["section_key"],
                        "markdown": markdown,
                        "cited_evidence_ids": ["W-EVIDENCE"] if cite else [],
                        "figure_placeholders": figures,
                        "table_placeholders": tables,
                    })
            self.assertEqual(action["action"], "assemble_manuscript")
            exported = assemble_manuscript(
                db_path, module04_run_id, root / "outputs" / "final"
            )
            self.assertEqual(exported["message"], "Module 04完成，进入Module 05评价与修订")
            self.assertGreaterEqual(exported["body_characters"], 13_500)
            self.assertLessEqual(exported["body_characters"], 16_500)
            self.assertEqual(exported["figure_placeholders"], 1)
            self.assertEqual(exported["table_placeholders"], 1)
            final_path = Path(exported["output_path"])
            self.assertTrue(final_path.is_file())
            final_text = final_path.read_text(encoding="utf-8")
            self.assertIn("Module 04状态：Markdown稿件完成", final_text)
            self.assertIn("[图 1 置于此处", final_text)
            self.assertIn("[表 1 置于此处", final_text)
            self.assertIn("## 参考文献", final_text)
            self.assertNotIn("## 用户反馈", final_text)
            self.assertNotIn("W-EVIDENCE", final_text)
            self.assertEqual(module04_next_action(db_path, module04_run_id)["action"], "start_module05")
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "start_module05")
            self.assertEqual(module04_export_for_run(db_path, module03_run_id)["status"], "completed")

            module05_run_id = start_module05_evaluation(db_path, module04_run_id)
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "continue_module05")
            self.assertEqual(module05_next_action(db_path, module05_run_id)["action"], "evaluate_manuscript")

            def dimension(score: int, weakness: str, change: str) -> dict:
                return {
                    "score": score,
                    "strengths": ["稿件保持了冻结大纲的主线。"],
                    "weaknesses": [weakness],
                    "evidence": ["Theoretical foundations与Future perspective之间的推导仍可加强。"],
                    "required_changes": [change],
                }

            evaluation = {
                "module05_run_id": module05_run_id,
                "overall_assessment": "稿件视角清楚，但差异化论证和章节闭环需要具体加强。",
                "dimensions": {
                    "review_perspective": dimension(4, "视角在中段弱化。", "在理论章节重申评测视角。"),
                    "differentiation": dimension(3, "与既有综述差异缺少集中比较。", "增加差异比较段。"),
                    "logic": dimension(3, "理论与展望衔接不足。", "增加因果过渡。"),
                    "completeness": dimension(4, "局限性讨论较分散。", "集中总结适用边界。"),
                },
                "priority_revisions": [
                    {
                        "id": "R1",
                        "priority": "high",
                        "location": "Theoretical foundations结尾",
                        "problem": "没有把机制分析收束到评测视角。",
                        "change_instruction": "增加一段机制到评测指标的映射。",
                        "success_criterion": "读者可以从机制直接推导出评测维度。",
                    },
                    {
                        "id": "R2",
                        "priority": "high",
                        "location": "Future perspective开头",
                        "problem": "与既有综述的差异没有集中呈现。",
                        "change_instruction": "增加与既有综述组织逻辑的对照段。",
                        "success_criterion": "明确说明本稿新增的组织轴和结论。",
                    },
                ],
                "revision_strategy": ["先修复核心逻辑链", "再强化差异化结论"],
            }
            save_manuscript_evaluation(db_path, module05_run_id, evaluation)
            self.assertEqual(module05_next_action(db_path, module05_run_id)["action"], "revise_manuscript")
            revised_text = final_text.replace(
                "## 参考文献",
                "## 内容修订说明\n\n机制分析现已映射到评测维度，并集中说明与既有综述的差异。\n\n## 参考文献",
            )
            save_revised_manuscript(db_path, module05_run_id, {
                "module05_run_id": module05_run_id,
                "revised_markdown": revised_text,
                "addressed_revision_ids": ["R1", "R2"],
                "change_log": [
                    {
                        "revision_id": "R1",
                        "location": "Theoretical foundations结尾",
                        "change_summary": "增加机制与评测维度映射。",
                    },
                    {
                        "revision_id": "R2",
                        "location": "Future perspective开头",
                        "change_summary": "增加与既有综述的集中差异比较。",
                    },
                ],
            })
            self.assertEqual(module05_next_action(db_path, module05_run_id)["action"], "export_final_docx")
            docx = export_final_docx(db_path, module05_run_id, root / "outputs" / "final")
            self.assertEqual(docx["status"], "completed")
            docx_path = Path(docx["final_docx_path"])
            self.assertTrue(docx_path.is_file())
            self.assertGreater(docx_path.stat().st_size, 1000)
            with zipfile.ZipFile(docx_path) as archive:
                self.assertIn("word/document.xml", archive.namelist())
                document_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("内容修订说明", document_xml)
            self.assertEqual(module05_next_action(db_path, module05_run_id)["action"], "mvp_complete")
            self.assertEqual(module03_next_action(db_path, module03_run_id)["action"], "mvp_complete")

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
