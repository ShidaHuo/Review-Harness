"""Detect the active agent runtime and expose Review Harness capabilities.

This adapter is intentionally dependency-free and never reads credentials. Agents
should run it once at the start of a review workflow:

    python runtime_adapter.py

Set REVIEW_HARNESS_RUNTIME to deepseek-harness, kiro-crew, or codex when a
launcher does not expose a reliable runtime marker.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping


class RuntimeName(StrEnum):
    DEEPSEEK_HARNESS = "deepseek-harness"
    KIRO_CREW = "kiro-crew"
    CODEX = "codex"
    UNKNOWN = "unknown"


RUNTIME_ALIASES = {
    "deepseek": RuntimeName.DEEPSEEK_HARNESS,
    "deepseek-harness": RuntimeName.DEEPSEEK_HARNESS,
    "dsh": RuntimeName.DEEPSEEK_HARNESS,
    "kiro": RuntimeName.KIRO_CREW,
    "kiro-crew": RuntimeName.KIRO_CREW,
    "kirocrew": RuntimeName.KIRO_CREW,
    "codex": RuntimeName.CODEX,
    "openai-codex": RuntimeName.CODEX,
}

RUNTIME_MARKERS = {
    RuntimeName.KIRO_CREW: (
        "KIROCREW_PROJECT_DIR",
        "KIROCREW_RUNTIME_AGENT",
        "KIROCREW_SCRATCH",
        "KIROCREW_SPAWN_HOME",
    ),
    RuntimeName.DEEPSEEK_HARNESS: (
        "DSH_HOME",
        "DSH_PROFILE",
        "DSH_SESSION_ID",
        "DEEPSEEK_HARNESS",
    ),
    RuntimeName.CODEX: (
        "CODEX_HOME",
        "CODEX_THREAD_ID",
        "CODEX_SANDBOX",
        "CODEX_CI",
        "OPENAI_CODEX",
    ),
}


@dataclass(frozen=True)
class RuntimePolicy:
    runtime: str
    confidence: str
    evidence: list[str]
    project_root: str
    module01_skill: str
    module02_skill: str
    module03_skill: str
    module04_skill: str
    decision_interaction: str
    module01_completion_gate: str
    module02_orchestration: str
    module02_completion_gate: str
    perspective_branches: str
    supports_real_chat_forks: bool
    selection_terminal_message: str
    strict_boundary: str


def _runtime_from_override(value: str | None) -> RuntimeName | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().casefold().replace("_", "-")
    try:
        return RUNTIME_ALIASES[normalized]
    except KeyError as exc:
        choices = ", ".join(sorted({item.value for item in RUNTIME_ALIASES.values()}))
        raise ValueError(f"Unsupported REVIEW_HARNESS_RUNTIME={value!r}; use one of: {choices}") from exc


def detect_runtime(environment: Mapping[str, str] | None = None) -> tuple[RuntimeName, str, list[str]]:
    """Detect runtime from an explicit override, then runtime-owned env names.

    Only environment variable names are returned as evidence. Values are never
    exposed because launch environments can contain sensitive paths or tokens.
    """
    env = os.environ if environment is None else environment
    override = _runtime_from_override(env.get("REVIEW_HARNESS_RUNTIME"))
    if override is not None:
        return override, "explicit", ["REVIEW_HARNESS_RUNTIME"]

    matches = {
        runtime: [name for name in markers if env.get(name)]
        for runtime, markers in RUNTIME_MARKERS.items()
    }
    active = [(runtime, names) for runtime, names in matches.items() if names]
    if len(active) == 1:
        runtime, names = active[0]
        return runtime, "high", names
    if len(active) > 1:
        # Nested launchers can leak parent markers. Kiro Crew markers identify
        # the active gateway more specifically than generic Kiro variables.
        for preferred in (
            RuntimeName.KIRO_CREW,
            RuntimeName.DEEPSEEK_HARNESS,
            RuntimeName.CODEX,
        ):
            names = matches[preferred]
            if names:
                evidence = [f"{preferred.value}:{name}" for name in names]
                evidence.append("multiple_runtime_marker_groups")
                return preferred, "medium", evidence
    return RuntimeName.UNKNOWN, "low", []


def policy_for(runtime: RuntimeName, project_root: Path, confidence: str, evidence: list[str]) -> RuntimePolicy:
    skill_root = project_root / ".dsh" / "skills"
    common = {
        "runtime": runtime.value,
        "confidence": confidence,
        "evidence": evidence,
        "project_root": str(project_root.resolve()),
        "module01_skill": str((skill_root / "research-topic-evaluation" / "SKILL.md").resolve()),
        "module02_skill": str((skill_root / "review-landscape-analysis" / "SKILL.md").resolve()),
        "module03_skill": str((skill_root / "review-outline-design" / "SKILL.md").resolve()),
        "module04_skill": str((skill_root / "review-outline-export" / "SKILL.md").resolve()),
        "selection_terminal_message": "Start or resume the selected Module 03 outline run.",
        "module01_completion_gate": "Repeat review-harness module01-next after every persisted step until the complete report decision.",
        "module02_completion_gate": "Repeat review-harness module02-next after every persisted step until perspective selection.",
        "strict_boundary": "Module 01/02 do not draft; Module 03 designs the outline; Module 04 writes the approved approximately 15,000-character Markdown review and ends the MVP.",
    }
    if runtime == RuntimeName.DEEPSEEK_HARNESS:
        return RuntimePolicy(
            **common,
            decision_interaction="numbered plain text: 1.继续 / 2.结束; wait for explicit reply",
            module02_orchestration="DeepSeek Harness Workflow and bounded subagents",
            perspective_branches="create_review_perspective_branches real Session fork",
            supports_real_chat_forks=True,
        )
    if runtime == RuntimeName.KIRO_CREW:
        return RuntimePolicy(
            **common,
            decision_interaction="numbered plain text: 1.继续 / 2.结束; wait for explicit reply",
            module02_orchestration="Python core; root agent or bounded workflow_run/spawn_run when justified",
            perspective_branches="SQLite logical branches; use visible peer sessions only when session tools are mounted",
            supports_real_chat_forks=False,
        )
    if runtime == RuntimeName.CODEX:
        return RuntimePolicy(
            **common,
            decision_interaction="numbered plain text: 1.继续 / 2.结束; wait for explicit reply",
            module02_orchestration="Python core with bounded local batches; no DeepSeek Workflow dependency",
            perspective_branches="SQLite logical branches with reconstructable perspective selection",
            supports_real_chat_forks=False,
        )
    return RuntimePolicy(
        **common,
        decision_interaction="plain-text numbered single-select 继续/结束; stop until explicit reply",
        module02_orchestration="Python core only",
        perspective_branches="SQLite logical branches only",
        supports_real_chat_forks=False,
    )


def build_policy(
    project_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
    forced_runtime: str | None = None,
) -> RuntimePolicy:
    env = dict(os.environ if environment is None else environment)
    if forced_runtime:
        env["REVIEW_HARNESS_RUNTIME"] = forced_runtime
    runtime, confidence, evidence = detect_runtime(env)
    root = (project_root or Path(__file__).resolve().parent).resolve()
    return policy_for(runtime, root, confidence, evidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect and adapt the Research Review Harness runtime")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument(
        "--runtime",
        choices=[item.value for item in RuntimeName if item != RuntimeName.UNKNOWN],
        help="Explicit runtime override for launchers without environment markers",
    )
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    args = parser.parse_args(argv)
    policy = build_policy(args.project_root, forced_runtime=args.runtime)
    print(json.dumps(asdict(policy), ensure_ascii=False, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
