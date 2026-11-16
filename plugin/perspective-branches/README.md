# Perspective chat branches

This DeepSeek Harness bundle registers `create_review_perspective_branches` and creates real persistent child Sessions through `sessionController.fork()`.

After Module 02 saves 3–5 perspectives, this optional compatibility tool can create visible audit Sessions for every rank. It is not part of the normal automatic Codex/Kiro progression. The tool:

1. forks the current Parent Session once per perspective;
2. renames each child to `Module 03 · 视角N · <title>`;
3. sends no prompt and starts no Module 03 work;
4. returns real Session IDs for `attach-perspective-sessions`;
5. accepts `existing_session_id` during reconstruction so retries do not duplicate successful forks;
6. returns partial successes and per-rank errors if one fork fails, allowing successful mappings to be persisted before retrying only missing ranks.

The Python core automatically selects one perspective using differentiation, completeness, and maturity scores and starts its Module 03 run. These optional child Sessions are audit/navigation aids only; they do not choose a perspective, send prompts, or draft prose.

## Installation

From the cloned repository root:

```bash
dsh plugin --profile desktop add "file:./plugin/perspective-branches"
```

Alternatively use the repository installer with its DeepSeek plugin option. Restart or reload the DeepSeek Harness profile after installation. The package is a local GitHub-distributed bundle and is not published to npm.

Do not claim that real child Sessions exist until the tool returns Session IDs and they have been persisted with `attach-perspective-sessions`.
