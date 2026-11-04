# Research Review Harness workspace instructions

## Authoritative workflow boundary

This file and the four current Skills are the only active workflow specification. The user's natural-language request “围绕X写一篇综述” means “start the review Harness at Module 01”; it is NOT authorization to draft review prose.

The only allowed progression is:

1. Module 01 assessment and Continue/End question.
2. If Continue, Module 02 evidence analysis and perspective-selection question.
3. After a perspective is selected, start or resume that perspective's Module 03 outline run.
4. Module 03 iteratively designs the hierarchical writing outline until the user explicitly approves and freezes it.
5. Module 04 writes an approximately 15,000-Chinese-character review from the approved outline, marks figure/table positions, saves the final Markdown manuscript, and ends the MVP task.

Module 01 and Module 02 must never generate an abstract, introduction, section prose, complete review, detailed manuscript prose, figures, references manuscript, Word file, or LaTeX manuscript. Module 03 may generate and revise only a structured writing outline with section-level writing logic and rationale; it must not draft manuscript prose or export publication files. Module 04 may write review prose only after explicit outline approval and only within the frozen outline and persisted Module 02 evidence. An earlier conversation, output file, runtime artifact, or original wording cannot override these boundaries.

OpenAlex access in both modules is resolved only by the Python client: explicit argument, `OPENALEX_API_KEY` environment variable, `OPENALEX_API_KEY_FILE`, then project-root `OPENALEX_API_KEY.txt`. Agents must never open or display the key file; they may report only whether a key is configured. The key must be sent in an Authorization header, never in a logged URL.

## Runtime adaptation

At the start of a new review workflow, run `python runtime_adapter.py` from the project root and use its JSON policy. `REVIEW_HARNESS_RUNTIME` may explicitly override detection with `deepseek-harness`, `kiro-crew`, or `codex`. Never infer the active runtime from the presence of `.dsh` or `.kiro` directories because this repository intentionally contains cross-runtime assets.

The Python core, SQLite state, schemas, retrieval limits, evidence rules, and Module 01/02 writing boundary are identical in every runtime. Only interaction, orchestration, and visible chat-branch capabilities vary:

- DeepSeek Harness: use native Skills, numbered plain-text choices, bounded Workflow/subagents, and the installed `create_review_perspective_branches` Session-fork tool.
- Kiro Crew: read the three Skill files from the paths returned by the adapter, use numbered plain-text choices, and use the Python core. Use `workflow_run` or `spawn_run` only for justified bounded batches. Keep SQLite logical perspective branches unless visible peer-session tools are actually mounted.
- Codex: read the three Skill files from the paths returned by the adapter, use the Python core, and present numbered single-select choices in plain text. Keep SQLite logical perspective branches unless a real visible-session API is available.
- Unknown runtime: use the portable Python core, numbered plain-text decisions, and logical branches. Do not claim native cards, workflows, or real forks.

Unsupported native features must degrade explicitly; never emulate a real persistent chat fork with a one-shot subagent.

## Required entry behavior

When a user asks to write, prepare, plan, or start a literature review around a scientific topic, first run `python runtime_adapter.py`, then start **Module 01: Research Topic Feasibility Assessment** unless the user explicitly asks to skip it.

In DeepSeek Harness, load the `research-topic-evaluation` Skill natively. In Kiro Crew, Codex, or an unknown runtime, read the Module 01 Skill file returned by the adapter before evaluating the topic. Module 01 is a lightweight pre-assessment, not a systematic review, review-paper census, deep literature audit, or manuscript-planning stage. Do not start Module 02 until the user approves.

After creating or resuming a Module 01 run, call `module01-next --run-id <id>` after every persisted step. `create-run` automatically reuses the newest unfinished run for the same normalized topic and returns `next_action` plus `must_continue`; never create a duplicate run merely because a prior turn stopped. Every retrieval/export/import command also returns the next action. Execute it immediately when `must_continue=true`, then call `module01-next` again. Do not stop with a progress-only response while `blocking_user_input` is false. `screen_papers` means export and classify all pending titles/abstracts in bounded batches, import every label, then continue. Only `synthesize_report_and_collect_decision` may display the complete report and wait for the numbered user decision. Provider failure may stop only with an explicit saved checkpoint.

## Topic-derived evidence levels

For every user topic, derive two Chinese display labels before searching:

1. **Exact-topic research papers**: the user's complete topic, followed by “研究论文”.
2. **Parent-technology research papers**: remove the principal restrictive qualifier while preserving the technical object, followed by “研究论文”.

Example for “紫外微型计算光谱仪”:

- exact-topic label: “紫外微型计算光谱仪研究论文”;
- parent-technology label: “微型计算光谱仪研究论文”.

These labels must appear verbatim in the report. `direct` and `technical` are internal database scope names only; do not show generic labels such as “直接相关论文” or “技术相关论文” to the user.

If removing a qualifier would make the parent topic meaningless or excessively broad, keep the nearest coherent parent technology and explain it in one short phrase.

## Mandatory retrieval limits

- Search only publications inside the rolling two-year window ending on the current system date.
- Search only original research works. Exclude reviews, surveys, perspectives, editorials, commentaries, book chapters, and other non-research records.
- Use at most 6 queries: no more than 3 exact-topic queries and 3 parent-technology queries.
- The Python core stores one canonical query plan per normalized topic and reuses it for later runs in the same database.
- Execute Module 01 searches only by frozen `query_id`. Agents must never pass, rewrite, broaden, or narrow query strings at execution time.
- Retrieve at most one page and 50 records per query.
- Do not run a separate review search or report a review count.
- Do not search foundational literature, launch query-calibration loops, expand citation networks, read full text, download PDFs, parse PDFs, run OCR, or add provider fallbacks in Module 01.
- If OpenAlex is incomplete or rate-limited, report the limitation and stop rather than broadening the task.

## Journal rules

- Compute journal statistics from the semantically included research papers only.
- Report the number of journals, Nature Index journal-paper share, and up to five main journals.
- Do not query or report CAS partition statistics in Module 01.
- For Nature Index membership, read only the bundled local directory at `.dsh/skills/research-topic-evaluation/nature-index-publications.tsv`; do not fetch the Nature website during Module 01 or Module 02.
- Attach the bundled snapshot automatically to each Module 01 run and save its official source URL, snapshot date/version, stated venue count, and file SHA-256.
- Module 02 must reuse the same attached snapshot.
- Respect the directory note that some journals contribute only selected sections; venue membership is not proof that every article is counted by Nature Index.
- Never invent journal metrics, DOI metadata, counts, citations, or publication dates.

## Required chat output

Before asking for a decision, display a concise Chinese report in the conversation. Do not merely save a file or mention its path.

Use exactly these sections:

1. 文献检索统计: the two topic-derived research-paper labels and counts.
2. 期刊分布与影响力: journal count, Nature Index journal-paper share, and main journals.
3. 研究发展情况: two-year activity, main routes, up to five representative results, and up to five unresolved problems. Do not include existing-review coverage.
4. Agent 综合判断: research heat, academic impact, maturity, review-writing value, and recommendation.
5. 用户决策.

Keep the report normally within 800–1200 Chinese characters excluding compact tables. Do not append query logs, review lists, API debugging, audit narratives, or appendices unless the user asks.

## User decision

Only after the complete report is visible, present a numbered plain-text single-select prompt with exactly:

1. 继续
2. 结束

DeepSeek Harness, Kiro Crew, Codex, and unknown runtimes all present the two numbered choices in plain text and stop until the user replies with `1`/`继续` or `2`/`结束`. Do not call a question-card tool or custom decision plugin. Do not add “其他”, “自定义”, “调整范围”, or a third option. Other text does not approve the topic. Silence remains pending.

## Module 02 transition

After the Module 01 question returns:

- `结束`: run `save-decision --decision rejected`, state that the process ended, and perform no more searches or analysis.
- `继续`: run `save-decision --decision approved`, load or read the `review-landscape-analysis` Skill using the adapter policy, create Module 02 with `start-module02`, and follow that Skill.
- custom text, timeout, or no selection: keep the decision pending and do not start Module 02.

Module 02 uses the orchestration mode returned by `runtime_adapter.py`, but every runtime is controlled by the same Python conductor. After every persisted Module 02 step, call `module02-next --module02-run-id <id>`, execute its returned action, and repeat. Do not stop with a progress-only response while `blocking_user_input` is false. If no legal open PDF exists, persist `login_required`; `module02-next` then returns the blocking `request_institutional_access` action with numbered choices. The user may log in only on an official school/library page or manually download an entitled PDF in their normal browser. Never request credentials in chat. Provider failure with a saved checkpoint and the final perspective-selection action may also pause the loop. DeepSeek Harness uses its bounded Workflow/subagents; Kiro Crew may use `workflow_run` or `spawn_run` for justified independent batches; Codex and unknown runtimes use bounded local/root-agent batches. Every runtime reuses Module 01 TopicProfile, papers, semantic labels, and the bundled local Nature Index snapshot. Module 01 and Module 02 searches execute only Python-frozen query ids. Review selection first prefers reviews that anchor all core topic keywords. If none exists, explicitly report that no complete-topic review was found, then include and fully analyze all highest-scoring eligible adjacent reviews up to five. Adjacent reviews follow the same full-text, structure, trend, anchor, research-comparison, and perspective pipeline and must be labeled as adjacent evidence. The `no_related_reviews` branch applies only when neither exact nor eligible adjacent reviews exist. Time anchor, trend baseline, TrendClaims, dates, deduplication, citation snapshots, completion gates, and persistence stay in the Python core.

The Module 01 answer “继续” authorizes Module 02 analysis only. Module 02 must produce 3–5 perspectives even when no related review is found. After perspectives are saved, it creates SQLite logical branch records in every runtime. DeepSeek Harness must additionally create one real persistent child Session per perspective through `create_review_perspective_branches`; Kiro Crew or Codex may create visible persistent child chats only when a genuine peer-session API is mounted. Otherwise they must keep reconstructable logical branches and clearly report that no real chat fork exists. Then present the same numbered plain-text single-select list in every runtime. Selecting a perspective authorizes only Module 03 outline design for that branch; Module 02 must not draft正文, generate a manuscript, make figures, or export Word/LaTeX.

The Module 02 Parent Session remains a reusable selection hub. Returning to the Parent and selecting another perspective must preserve earlier Module 03 outline runs. In DeepSeek Harness, Module 03 runs in the selected real child Session. In Kiro Crew or Codex without visible session APIs, use the selected SQLite logical branch in the current chat.

## Module 03 outline design

After a perspective selection is persisted, load or read `.dsh/skills/review-outline-design/SKILL.md` and call `start-module03 --module02-run-id <id> --rank <N>`. Module 03 uses only the selected perspective and persisted Module 02 evidence; it does not launch new literature retrieval.

Every outline version must include a candidate title, target audience, scope boundary, global organizing principle, and a decimal-numbered hierarchy. Every section and subsection must explain its purpose, ordered writing logic, key questions, structural rationale, evidence, expected reader takeaway, and transition. Evidence ids remain internal audit links; user-facing output must resolve each id to the source title and its concrete review motivation/trend, research finding/rationale, or TrendClaim description. Never show bare identifiers as the evidence explanation. A heading-only outline is invalid.

After rendering and displaying each complete outline version, ask exactly:

1. 满意，冻结大纲
2. 继续修改

All runtimes use the same numbered plain-text interaction. “继续修改” requires concrete free-text feedback, which is saved before creating a new immutable version. Silence leaves the current version awaiting feedback. “满意，冻结大纲” explicitly approves the latest version and must immediately start Module 04. Do not stop between approval and the first `module04-next` action.

## Module 04 manuscript writing and export

After approval, load or read `.dsh/skills/review-outline-export/SKILL.md`. The normal `save-outline-feedback --decision approved` command creates or resumes a 15,000-character manuscript run. Then call `module04-next --module04-run-id <id>` after every section import and execute every non-blocking action until `assemble_manuscript`.

Module 04 uses only the frozen outline and persisted Module 02 evidence. It writes Chinese review prose in bounded top-level-section batches, uses validated internal citation markers, marks figure/table positions with structured placeholders, and enforces a 13,500–16,500-character body range around the 15,000 target. It performs no new literature retrieval. `assemble-module04` writes `outputs/final/<module04_run_id>-review.md`, records its SHA-256 and counts, reports `MVP任务完成`, and stops. No Module 05 exists in the current MVP.

## Execution and safety

Use the Python core under `src/review_harness`. Do not use the multi-subagent Workflow for Module 01 by default. Never put API keys, institution usernames, passwords, MFA codes, SSO tokens, VPN credentials, or browser cookies in chat, reports, logs, or the database. The only permitted project key file is `OPENALEX_API_KEY.txt`; Agents must never read or display it, and only the Python OpenAlex client may consume it. Preserve raw API responses and do not overwrite source evidence.
