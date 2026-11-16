import json
import os
import shutil
import subprocess
import sys
import tempfile
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
            PROJECT_ROOT / "schemas" / "manuscript.schema.json",
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
        self.assertIn("save-agent-decision", skill)
        self.assertNotIn("1. 继续\n2. 结束", skill)

        module02_skill = (
            PROJECT_ROOT / ".dsh" / "skills" / "review-landscape-analysis" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(module02_skill.startswith("---\n"))
        self.assertIn("name: review-landscape-analysis", module02_skill)
        self.assertIn("user-invocable: true", module02_skill)
        self.assertIn("select-best-perspective", module02_skill)
        self.assertIn("differentiation_score", module02_skill)

        module03_skill = (
            PROJECT_ROOT / ".dsh" / "skills" / "review-outline-design" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(module03_skill.startswith("---\n"))
        self.assertIn("name: review-outline-design", module03_skill)
        self.assertIn("user-invocable: true", module03_skill)
        self.assertIn("save-outline-evaluation", module03_skill)
        self.assertNotIn("满意，冻结大纲", module03_skill)

        module04_skill = (
            PROJECT_ROOT / ".dsh" / "skills" / "review-outline-export" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(module04_skill.startswith("---\n"))
        self.assertIn("name: review-manuscript-writing", module04_skill)
        self.assertIn("user-invocable: true", module04_skill)

    def test_global_codex_skill_contract_and_locator(self) -> None:
        skill_root = PROJECT_ROOT / "codex-skill" / "review-harness"
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\n"))
        self.assertIn("name: review-harness", skill)
        self.assertIn("description:", skill)
        self.assertIn("runtime_adapter.py --runtime codex", skill)
        self.assertIn("run_review_harness.py", skill)
        self.assertIn("end-to-end task", skill)

        openai_yaml = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$review-harness", openai_yaml)
        self.assertIn("allow_implicit_invocation: true", openai_yaml)

        environment = os.environ.copy()
        environment["REVIEW_HARNESS_HOME"] = str(PROJECT_ROOT)
        completed = subprocess.run(
            [sys.executable, str(skill_root / "scripts" / "locate_review_harness.py")],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(Path(result["project_root"]), PROJECT_ROOT)
        self.assertNotIn("OPENALEX_API_KEY", completed.stdout)

        with tempfile.TemporaryDirectory() as temporary_directory:
            installed_skill = Path(temporary_directory) / "review-harness"
            scripts = installed_skill / "scripts"
            scripts.mkdir(parents=True)
            shutil.copyfile(
                skill_root / "scripts" / "locate_review_harness.py",
                scripts / "locate_review_harness.py",
            )
            shutil.copyfile(
                skill_root / "scripts" / "run_review_harness.py",
                scripts / "run_review_harness.py",
            )
            (installed_skill / "project-root.txt").write_text(
                f"{PROJECT_ROOT}\n", encoding="utf-8"
            )
            pointer_environment = os.environ.copy()
            pointer_environment.pop("REVIEW_HARNESS_HOME", None)
            pointer_result = subprocess.run(
                [sys.executable, "-S", str(scripts / "locate_review_harness.py")],
                cwd=temporary_directory,
                env=pointer_environment,
                capture_output=True,
                text=True,
                check=True,
            )
            resolved = json.loads(pointer_result.stdout)
            self.assertEqual(Path(resolved["project_root"]), PROJECT_ROOT)

            runner_result = subprocess.run(
                [sys.executable, "-S", str(scripts / "run_review_harness.py"), "--help"],
                cwd=temporary_directory,
                env=pointer_environment,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("module01-next", runner_result.stdout)
            self.assertIn("module04-next", runner_result.stdout)

            subprocess.run(
                [sys.executable, str(scripts / "run_review_harness.py"), "init-db"],
                cwd=temporary_directory,
                env=pointer_environment,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertTrue((Path(temporary_directory) / "runtime" / "research.sqlite3").is_file())

    def test_real_session_fork_plugin_contract(self) -> None:
        plugin = (PROJECT_ROOT / "plugin" / "perspective-branches" / "index.js").read_text(encoding="utf-8")
        self.assertIn("sessionController.fork", plugin)
        self.assertIn("existing_session_id", plugin)
        self.assertIn("complete: errors.length === 0", plugin)


if __name__ == "__main__":
    unittest.main()
