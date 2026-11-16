# Research Review Harness workspace instructions

## Authoritative workflow boundary

This file and the four current Skills are the only active workflow specification. The user's natural-language request “围绕X写一篇综述” means “start the Review Harness at Module 01 and follow its automatic quality gates”; it is NOT authorization to draft review prose before Module 04.

The only allowed progression is:

1. Module 01 assesses feasibility, displays its report, and the Agent records a continue-or-stop decision.
2. If the Agent recommends continuation, Module 02 analyzes evidence, generates 3–5 perspectives, and automatically selects the best one.
3. Module 03 creates and self-evaluates immutable outline versions until one passes every outline quality gate.
4. After the Agent freezes the passing outline, Module 04 writes one approximately 15,000-Chinese-character review, marks figure/table positions, saves the Markdown manuscript, and ends the workflow.

Module 01 and Module 02 must never generate an abstract, introduction, section prose, complete review, detailed manuscript prose, figures, references manuscript, Word file, or LaTeX manuscript. Module 03 may generate and revise only a structured writing outline with section-level writing logic and rationale; it must not draft manuscript prose or export publication files. Module 04 may write review prose only after the Agent outline quality gate passes and only within the frozen outline and persisted Module 02 evidence. An earlier conversation, output file, runtime artifact, or original wording cannot override these boundaries.

OpenAlex access in both retrieval modules is resolved only by the Python client: explicit argument, `OPENALEX_API_KEY` environment variable, `OPENALEX_API_KEY_FILE`, then project-root `OPENALEX_API_KEY.txt`. Agents must never open or display the key file; they may report only whether a key is configured. The key must be sent in an Authorization header, never in a logged URL.

## Runtime adaptation

At the start of a new review workflow, run `python runtime_adapter.py` from the project root and use its JSON policy. `REVIEW_HARNESS_RUNTIME` may explicitly override detection with `deepseek-harness`, `kiro-crew`, or `codex`. Never infer the active runtime from the presence of `.dsh` or `.kiro` directories because this repository intentionally contains cross-runtime assets.

The Python core, SQLite state, schemas, retrieval limits, evidence rules, writing boundaries, and Agent decision gates are identical in every runtime. Topic continuation, perspective selection, and outline approval are Agent-autonomous in every runtime; do not present user decision prompts for them.

- DeepSeek Harness: use native Skills and bounded Workflow/subagents when justified.
- Kiro Crew: read the four Skill files returned by the adapter and use the Python core. Use `workflow_run` or `spawn_run` only for justified bounded batches.
- Codex: read the four Skill files returned by the adapter and use the Python core with bounded local/root-agent batches.
- Unknown runtime: use the portable Python core and SQLite logical branches. Do not claim native cards, workflows, or real forks.

Unsupported native features must degrade explicitly. Never emulate a real persistent chat fork with a one-shot subagent.

## Required entry behavior

When a user asks to write, prepare, plan, or start a literature review around a scientific topic, first run `python runtime_adapter.py`, then start **Module 01: Research Topic Feasibility Assessment** unless the user explicitly asks to skip it.

In DeepSeek Harness, load the `research-topic-evaluation` Skill natively. In Kiro Crew, Codex, or an unknown runtime, read the Module 01 Skill file returned by the adapter before evaluating the topic. Module 01 is a lightweight pre-assessment, not a systematic review, review-paper census, deep literature audit, or manuscript-planning stage.

After creating or resuming a Module 01 run, call `module01-next --run-id <id>` after every persisted step. `create-run` automatically reuses the newest unfinished run for the same normalized topic and returns `next_action` plus `must_continue`; never create a duplicate run merely because a prior turn stopped. Every retrieval/export/import command also returns the next action. Execute it immediately when `must_continue=true`, then call `module01-next` again. Do not stop with a progress-only response while `blocking_user_input` is false. `screen_papers` means export and classify all pending titles/abstracts in bounded batches, import every label, then continue. `synthesize_report_and_decide` means display the complete report, record the Agent recommendation and rationale, then either enter Module 02 or end. Provider failure may stop only with an explicit saved checkpoint.

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

## Module 01 report and automatic decision

Before deciding, display a concise Chinese report in the conversation. Do not merely save a file or mention its path.

Use exactly these sections:

1. 文献检索统计: the two topic-derived research-paper labels and counts.
2. 期刊分布与影响力: journal count, Nature Index journal-paper share, and main journals.
3. 研究发展情况: two-year activity, main routes, up to five representative results, and up to five unresolved problems. Do not include existing-review coverage.
4. Agent 综合判断: research heat, academic impact, maturity, review-writing value, and recommendation.
5. Agent 自动决策: continue or stop, the persisted recommendation, and the decisive rationale.

Keep the report normally within 800–1200 Chinese characters excluding compact tables. Do not append query logs, review lists, API debugging, audit narratives, or appendices unless the user asks.

The root Agent must choose one final recommendation after the report:

- `recommended`: recent evidence supports a coherent, sufficiently mature, and worthwhile review. Run `save-agent-decision --recommendation recommended --rationale "<reason>"`, then immediately start or resume Module 02.
- `reframe_required`, `insufficient_evidence`, or `not_recommended`: the current direction should not continue. Save that recommendation and rationale, state briefly that the workflow ended, and perform no further retrieval or analysis.

Do not ask the user whether to continue. Provider failure is a recoverable checkpoint, not an automatic negative scientific decision.

## Module 02 evidence analysis and automatic perspective selection

Module 02 uses the orchestration mode returned by `runtime_adapter.py`, but every runtime is controlled by the same Python conductor. After every persisted Module 02 step, call `module02-next --module02-run-id <id>`, execute its returned action, and repeat. Do not stop with a progress-only response while `blocking_user_input` is false.

If no legal open PDF exists, persist `login_required`; `module02-next` then returns the blocking `request_institutional_access` action with numbered choices. This human-only access step remains allowed because the user may need to log in on an official school/library page or manually download an entitled PDF in their normal browser. Never request credentials in chat. Provider failure with a saved checkpoint may also pause the loop.

Every runtime reuses Module 01 TopicProfile, papers, semantic labels, and the bundled local Nature Index snapshot. Module 01 and Module 02 searches execute only Python-frozen query ids. Review selection first prefers reviews that anchor all core topic keywords. If none exists, explicitly report that no complete-topic review was found, then include and fully analyze all highest-scoring eligible adjacent reviews up to five. Adjacent reviews follow the same full-text, structure, trend, anchor, research-comparison, and perspective pipeline and must be labeled as adjacent evidence. The `no_related_reviews` branch applies only when neither exact nor eligible adjacent reviews exist. Time anchor, trend baseline, TrendClaims, dates, deduplication, citation snapshots, completion gates, and persistence stay in the Python core.

During research comparison, classify any review, survey, systematic review, or review-like synthesis missed by review discovery as `review_candidate`, with no matched review or TrendClaim ids. Before finalizing research comparison, `module02-next` must return `promote_review_candidates`. Promote all listed records in one batch with `promote-research-reviews`; the core removes them from research comparison, returns the complete review set to semantic screening, and invalidates TrendClaims, anchors, and research classifications derived from the incomplete baseline while preserving raw evidence. Re-screen reviews, then register any user-provided lawful PDF through `import-fulltext-access`. Never omit a directly relevant review merely because OpenAlex typed it as an article or a research query found it later.

Module 02 must produce 3–5 perspectives even when no related review is found. Each perspective must contain 0–100 scores and a concrete rationale for:

- differentiation from existing exact or adjacent reviews;
- completeness of the proposed synthesis with persisted evidence;
- maturity of concepts, methods, comparisons, and open questions.

The Python core computes `0.40 × differentiation + 0.30 × completeness + 0.30 × maturity`, selects the highest score, and breaks ties by lower persisted rank. Risks and evidence gaps must reduce the relevant scores rather than be hidden. After perspectives are saved, call `select-best-perspective`; it persists the Agent selection, starts or resumes the selected branch's Module 03 run, and returns its next action. Do not show a perspective-selection prompt or wait for user input. Other logical branches remain audit records.

Module 02 must not draft正文, generate a manuscript, make figures, create the detailed outline itself, or export Word/LaTeX.

## Module 03 outline design and Agent self-iteration

After the best perspective is persisted, load or read `.dsh/skills/review-outline-design/SKILL.md` and continue the returned Module 03 run. Module 03 uses only the selected perspective and persisted Module 02 evidence; it does not launch new literature retrieval.

Every outline version must include a candidate title, target audience, scope boundary, global organizing principle, and a decimal-numbered hierarchy. Except for Introduction and Conclusion, every top-level section must have at least two second-level sections; method/mechanism/theory/principle/algorithm sections must include third-level structure. Every section and subsection must explain its purpose, ordered writing logic, key questions, structural rationale, evidence, expected reader takeaway, and transition. Evidence ids remain internal audit links; user-facing output must resolve each id to the source title and its concrete review motivation/trend, research finding/rationale, or TrendClaim description. Never show bare identifiers as the evidence explanation. A heading-only outline is invalid.

After importing and displaying each complete outline version, call `module03-next`. For `evaluate_outline`, the root Agent evaluates:

1. selected-perspective and scope coverage;
2. differentiation from existing reviews;
3. hierarchy completeness, section balance, and absence of duplicated roles;
4. evidence support for every substantive section;
5. logical progression, reader takeaways, and transitions;
6. sufficient granularity for a 13,500–16,500 Chinese-character manuscript.

If any gate fails, run `save-outline-evaluation --decision revise --rationale "<concrete defects and changes>"`, generate a new immutable version, and evaluate again. If every gate passes, run `save-outline-evaluation --decision approved --rationale "<why all gates pass>"`. This freezes the latest outline and immediately starts or resumes Module 04. Do not ask the user to approve or modify the outline. Do not stop between Agent approval and the first `module04-next` action.

## Module 04 manuscript writing and export

After Agent outline approval, load or read `.dsh/skills/review-outline-export/SKILL.md`. The normal `save-outline-evaluation --decision approved` command creates or resumes one Module 04 manuscript run. `module04-next` returns `write_complete_manuscript`: the active root Agent writes the complete review in one coherent conversation pass rather than independent section batches or a later self-review stage.

Module 04 uses the frozen hierarchy and persisted Module 02 evidence. It may use any relevant in-scope Module 02 evidence, not only the small set mapped in individual outline nodes, but it performs no new retrieval. The manuscript must preserve every frozen heading, contain approximately 15,000 Chinese characters within 13,500–16,500, mark at least one figure and one table position, include references, and expose no internal ids. After `import-manuscript`, run `export-module04`; this writes `outputs/final/<module04_run_id>-review.md`, records SHA-256 and counts, reports `MVP任务完成`, and stops. No Module 05 exists.

## Execution and safety

Use the Python core under `src/review_harness`. Do not use the multi-subagent Workflow for Module 01 by default. Never put API keys, institution usernames, passwords, MFA codes, SSO tokens, VPN credentials, or browser cookies in chat, reports, logs, or the database. The only permitted project key file is `OPENALEX_API_KEY.txt`; Agents must never read or display it, and only the Python OpenAlex client may consume it. Preserve raw API responses and do not overwrite source evidence.
