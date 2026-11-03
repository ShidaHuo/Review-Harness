import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ContractFileTests(unittest.TestCase):
    def test_json_contracts_and_example_are_valid_json(self) -> None:
        files = [
            PROJECT_ROOT / "schemas" / "topic-profile.schema.json",
            PROJECT_ROOT / "schemas" / "paper-record.schema.json",
            PROJECT_ROOT / "schemas" / "assessment.schema.json",
            PROJECT_ROOT / "schemas" / "decision.schema.json",
            PROJECT_ROOT / "schemas" / "review-analysis.schema.json",
            PROJECT_ROOT / "schemas" / "research-trend-comparison.schema.json",
            PROJECT_ROOT / "schemas" / "review-perspectives.schema.json",
            PROJECT_ROOT / "schemas" / "fulltext-access.schema.json",
            PROJECT_ROOT / "schemas" / "nature-index-snapshot.schema.json",
            PROJECT_ROOT / "schemas" / "trend-claims.schema.json",
            PROJECT_ROOT / "schemas" / "paper-relevance.schema.json",
            PROJECT_ROOT / "schemas" / "review-screening.schema.json",
            PROJECT_ROOT / "schemas" / "perspective-branches.schema.json",
            PROJECT_ROOT / "schemas" / "perspective-selection.schema.json",
            PROJECT_ROOT / "schemas" / "review-outline.schema.json",
            PROJECT_ROOT / "examples" / "uv-miniature-computational-spectrometer.topic-profile.json",
        ]
        for path in files:
            with self.subTest(path=path):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(value, dict)

    def test_skill_has_required_frontmatter(self) -> None:
        skill = (
            PROJECT_ROOT / ".dsh" / "skills" / "research-topic-evaluation" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\n"))
        self.assertIn("name: research-topic-evaluation", skill)
        self.assertIn("user-invocable: true", skill)

        module02_skill = (
            PROJECT_ROOT / ".dsh" / "skills" / "review-landscape-analysis" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(module02_skill.startswith("---\n"))
        self.assertIn("name: review-landscape-analysis", module02_skill)
        self.assertIn("user-invocable: true", module02_skill)

        module03_skill = (
            PROJECT_ROOT / ".dsh" / "skills" / "review-outline-design" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(module03_skill.startswith("---\n"))
        self.assertIn("name: review-outline-design", module03_skill)
        self.assertIn("user-invocable: true", module03_skill)

        module04_skill = (
            PROJECT_ROOT / ".dsh" / "skills" / "review-outline-export" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(module04_skill.startswith("---\n"))
        self.assertIn("name: review-outline-export", module04_skill)
        self.assertIn("user-invocable: true", module04_skill)

    def test_real_session_fork_plugin_contract(self) -> None:
        plugin = (PROJECT_ROOT / "plugin" / "perspective-branches" / "index.js").read_text(encoding="utf-8")
        self.assertIn("sessionController.fork", plugin)
        self.assertIn("existing_session_id", plugin)
        self.assertIn("complete: errors.length === 0", plugin)


if __name__ == "__main__":
    unittest.main()
