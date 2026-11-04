import tempfile
import unittest
from pathlib import Path

from runtime_adapter import RuntimeName, build_policy, detect_runtime


class RuntimeAdapterTests(unittest.TestCase):
    def test_detects_kiro_crew_from_owned_marker(self) -> None:
        runtime, confidence, evidence = detect_runtime({"KIROCREW_PROJECT_DIR": "C:/project"})
        self.assertEqual(runtime, RuntimeName.KIRO_CREW)
        self.assertEqual(confidence, "high")
        self.assertEqual(evidence, ["KIROCREW_PROJECT_DIR"])

    def test_detects_deepseek_harness(self) -> None:
        runtime, confidence, _ = detect_runtime({"DSH_HOME": "C:/Users/test/.dsh"})
        self.assertEqual(runtime, RuntimeName.DEEPSEEK_HARNESS)
        self.assertEqual(confidence, "high")

    def test_detects_codex(self) -> None:
        runtime, confidence, _ = detect_runtime({"CODEX_HOME": "C:/Users/test/.codex"})
        self.assertEqual(runtime, RuntimeName.CODEX)
        self.assertEqual(confidence, "high")

    def test_explicit_override_wins_nested_markers(self) -> None:
        runtime, confidence, evidence = detect_runtime({
            "REVIEW_HARNESS_RUNTIME": "codex",
            "KIROCREW_PROJECT_DIR": "C:/project",
        })
        self.assertEqual(runtime, RuntimeName.CODEX)
        self.assertEqual(confidence, "explicit")
        self.assertEqual(evidence, ["REVIEW_HARNESS_RUNTIME"])

    def test_repository_directories_do_not_imply_runtime(self) -> None:
        runtime, confidence, evidence = detect_runtime({})
        self.assertEqual(runtime, RuntimeName.UNKNOWN)
        self.assertEqual(confidence, "low")
        self.assertEqual(evidence, [])

    def test_policy_exposes_runtime_specific_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            deepseek = build_policy(root, environment={}, forced_runtime="deepseek-harness")
            kiro = build_policy(root, environment={}, forced_runtime="kiro-crew")
            codex = build_policy(root, environment={}, forced_runtime="codex")
        self.assertIn("numbered plain text", deepseek.decision_interaction)
        self.assertTrue(deepseek.supports_real_chat_forks)
        self.assertEqual(deepseek.decision_interaction, kiro.decision_interaction)
        self.assertFalse(kiro.supports_real_chat_forks)
        self.assertEqual(kiro.decision_interaction, codex.decision_interaction)
        self.assertIn("module01-next", codex.module01_completion_gate)
        self.assertTrue(codex.module03_skill.endswith("review-outline-design\\SKILL.md") or codex.module03_skill.endswith("review-outline-design/SKILL.md"))
        self.assertTrue(codex.module04_skill.endswith("review-outline-export\\SKILL.md") or codex.module04_skill.endswith("review-outline-export/SKILL.md"))
        self.assertIn("one coherent approximately 15,000-character Markdown review", codex.strict_boundary)


if __name__ == "__main__":
    unittest.main()
