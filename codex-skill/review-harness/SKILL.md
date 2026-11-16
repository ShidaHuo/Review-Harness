---
name: review-harness
description: Start or resume the installed Review Harness for scientific literature-review requests. Use when the user asks Codex to write, prepare, plan, assess, or continue a scientific review.
metadata:
  short-description: Run the staged scientific review workflow
---

# Review Harness launcher

Use this Skill as the global Codex entrypoint to the installed Review Harness. It locates the installation and hands control to the repository's authoritative workflow contract. It does not replace or duplicate that contract.

## Locate the installation

Run the bundled `scripts/locate_review_harness.py` script, resolving the path relative to this `SKILL.md`. The script first reads the installer-managed, non-secret `project-root.txt` pointer, then checks only bounded fallback locations and returns JSON.

- If `status` is `ready`, use the returned `project_root` to locate code and module Skills. Keep the user's original working folder as the working directory for commands and generated files.
- If resolution fails, stop and ask the user to run the repository's Codex installer. Do not search the whole home directory.
- Keep workflow state, raw responses, intermediate files, and generated outputs in the user's working folder. Use the same folder when resuming that workflow.

## Enter the workflow

Read the contract and run the runtime adapter from the resolved installation root. Run the launcher commands from the user's working folder:

1. Read `AGENTS.md`. It is the authoritative workflow boundary.
2. Run `python runtime_adapter.py --runtime codex` from that root.
3. Read the module Skill path returned by the adapter before executing that module.
4. For every command shown as `python -m review_harness ...`, invoke the bundled `scripts/run_review_harness.py ...` runner instead. Resolve it relative to this global Skill. The runner loads the installation source while keeping the working folder for SQLite, raw responses, and outputs. Use paths inside that folder for explicit output arguments.
5. After every mutating command, execute the returned `next_action` immediately and then call the corresponding `module01-next`, `module02-next`, `module03-next`, or `module04-next` through the runner.

Never call OpenAlex directly, use a web-search substitute, or create an ad hoc database. The Python conductor is the only retrieval and persistence path. If research comparison discovers a review-like paper missed by review discovery, classify it as `review_candidate`, execute the returned `promote_review_candidates` action, and re-screen the complete review set. A matching user-provided lawful PDF is registered only after promotion and semantic inclusion; do not leave the review in the research list.

A normal request to write, prepare, plan, or start a scientific review begins at Module 01 unless the user explicitly asks to skip that assessment. A request to continue an existing run must resume persisted state rather than create a duplicate.

## Completion contract

Treat one review request as an end-to-end task. Do not end the response after retrieval, title/abstract screening, a Module 01 report, perspective generation, or an outline version. Process bounded batches sequentially and continue until one of these conditions occurs:

- Module 01 records a negative Agent recommendation and terminates;
- Module 04 exports the final Markdown and reports `MVP任务完成`;
- a real external blocker requires user action, such as institutional login, missing credentials, provider failure, or a platform-enforced execution limit.

For a review request, the intended completion is the final Module 04 Markdown manuscript. The only workflow decisions that normally stop before it are a persisted negative Module 01 decision, or Module 02 needing the user to supply the listed unavailable review PDFs. In the latter case provide the complete list with titles and links and resume the same run after the PDFs arrive; do not offer to skip full text or proceed from abstracts. Retry recoverable provider failures and retain checkpoints; if a persistent external failure or platform limit makes execution impossible, report the actual blocker rather than inventing evidence or claiming completion.

A large pending screening set is work to continue, not a reason to return a progress update. Never claim state was saved unless the runner command succeeded and the next conductor action can read it back.

For `screen_papers`, immediately export the records and classify all entries with a null `relevance_label` by reading their titles and abstracts. Write and import bounded JSON batches with `paper_id`, `label`, `confidence`, `reason`, and `actor`; call `module01-next` after each import and repeat until screening is complete. A progress update may be sent while working, but it must not end the turn. Before any final response, check the current conductor action: if it is nonterminal and not blocked, continue executing it. Instructions cannot guarantee execution after an external interruption; resume the persisted run if interrupted.

## Boundaries

- The project `AGENTS.md` and its four module Skills are the only workflow specification. If this launcher and the project differ, follow the project.
- Do not draft manuscript prose before the project authorizes Module 04.
- Do not broaden retrieval limits, bypass evidence or safety gates, or invent evidence.
- Never read or display `OPENALEX_API_KEY.txt`. Only the project Python client may consume credentials, and chat may report only whether a key is configured.
- Keep all SQLite state, raw responses, reports, and manuscripts under the user's working folder.
