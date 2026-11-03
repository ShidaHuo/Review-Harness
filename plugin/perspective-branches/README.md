# Perspective chat branches

This DeepSeek Harness bundle registers `create_review_perspective_branches` and creates real persistent child Sessions through `sessionController.fork()`.

After Module 02 saves 1–5 perspectives, the root Agent passes every rank and title. The tool:

1. forks the current Parent Session once per perspective;
2. renames each child to `Module 03 · 视角N · <title>`;
3. sends no prompt and starts no Module 03 work;
4. returns real Session IDs for `attach-perspective-sessions`;
5. accepts `existing_session_id` during reconstruction so retries do not duplicate successful forks;
6. returns partial successes and per-rank errors if one fork fails, allowing successful mappings to be persisted before retrying only missing ranks.

The Parent remains the reusable selection hub. Selecting a perspective persists its rank and authorizes the independent Module 03 outline run for that branch. The plugin itself still sends no prompt and never drafts prose.

## Installation

From the cloned repository root:

```bash
dsh plugin --profile desktop add "file:./plugin/perspective-branches"
```

Alternatively use the repository installer with its DeepSeek plugin option. Restart or reload the DeepSeek Harness profile after installation. The package is a local GitHub-distributed bundle and is not published to npm.

Do not claim that real child Sessions exist until the tool returns Session IDs and they have been persisted with `attach-perspective-sessions`.
