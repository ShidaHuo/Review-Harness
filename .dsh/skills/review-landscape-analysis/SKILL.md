---
name: review-landscape-analysis
description: Analyze topic-specific review papers, then compare post-review research against normalized trend claims to propose differentiated review angles.
whenToUse: Use only after Module 01 is explicitly approved by the user.
metadata:
  version: "0.8"
user-invocable: true
---

# Module 02: Review Landscape and Post-Review Research

## Entry gate and reuse

Before entering Module 02, run `python runtime_adapter.py` and use its orchestration and interaction policy. OpenAlex credential handling is shared with Module 01. The Python client automatically reuses `OPENALEX_API_KEY` or project-root `OPENALEX_API_KEY.txt`; Module 02 must not ask the user to paste the key again. The Agent may check only whether a credential is configured and must never read or expose its value.

Read the latest Module 01 decision from SQLite.

- `rejected`: stop and do not run Module 02.
- `approved`: create or resume one Module 02 run.
- missing, timeout, or custom answer: remain pending.

Reuse the approved Module 01 TopicProfile, its research-paper records, semantic labels, and its attached Nature Index snapshot. Do not regenerate the topic boundary or fetch a second Nature Index directory when the Module 01 snapshot is still the verified source for this run.

Read `review-search-rules.md`, `fulltext-access.md`, and `report-template.md`.

## Mandatory cross-runtime conductor

After creating or resuming a Module 02 run, call `module02-next --module02-run-id <id>` after every persisted step. Execute the returned non-blocking action and call `module02-next` again. Do not end a turn with a progress-only message while `blocking_user_input` is false. Continue until the action is `render_outputs_and_select_perspective`, then render both outputs and present the perspective selection. A real user-operated SSO page or `request_institutional_access` may pause the loop; provider failure may stop with an explicit recoverable checkpoint. When no legal open PDF exists, persist `login_required` and offer the numbered institutional-access choice before any abstract-only downgrade.

The Python core refuses final Module 02 reports before `perspectives_ready`, refuses perspectives before research comparison is finalized, and exposes the next mandatory action identically to DeepSeek Harness, Kiro Crew, and Codex.

## Phase A: exact reviews with adjacent fallback

The Python core derives and hashes the Module 02 review-discovery plan from the frozen Module 01 direct queries. Execute each review query only by the `query_id` returned in `module02-next`; the Agent must never supply or rewrite review query text. Typed and untyped review-intent channels are encoded in that plan. Use cursor pagination up to 10 pages of 100 records and mark truncation.

After retrieval, screen every candidate in one complete title/abstract pass with `prompts/module02-review-screener.md` and persist `review-screening.schema.json`. Classify each candidate as `exact`, `adjacent`, or `excluded`, record a 0–1 semantic relevance score, and name the important matched topic keywords. If any exact-topic review exists, include the exact reviews. If none exists, explicitly report that no review anchors all core keywords, then deterministically include all of the highest-scoring eligible adjacent reviews up to five. Label them clearly as adjacent-topic evidence; do not present them as exact-topic reviews. Every selected adjacent review proceeds through the same full-text access, reason, structure, future-trend, TrendClaim, time-anchor, post-review research, and perspective analysis as an exact review. Do not stop after screening and do not access PDFs before screening is saved.

For every included review retain title, date, journal, Nature Index status, citation count with observation date, stable link, review motivation, actual structure, future trends, evidence level, and source URLs.

After semantic screening, follow `fulltext-access.md`: legal open access first, then a numbered user choice before downgrading. With a credentialed browser, the user completes institution SSO directly on the official page. Without one, the user may download entitled PDFs in their normal browser and place them under the suggested `runtime/institutional-pdfs/` paths for registration. If the institution lacks a subscription, save `institution_not_subscribed` and skip. Never collect credentials in chat or tool arguments. Public `web_fetch` does not carry the institution browser session.

Only a registered `oa_downloaded` or `institutional_downloaded` PDF can support `evidence_level=full_text`. Otherwise use `abstract_only` or `metadata_only`; do not invent structure or future trends.

Use bounded review-analysis batches of five records and bounded research-comparison batches of 25 records. DeepSeek Harness runs the two built-in Workflows. Kiro Crew uses its root agent or justified `workflow_run`/`spawn_run` batches. Codex and unknown runtimes process the same exported batch contracts with the root agent or bounded local execution. In all cases, persist review analyses and normalize TrendClaims before beginning research comparison.

## Phase B: normalized TrendClaims

After review analysis, normalize semantically equivalent future-trend statements into `TrendClaim` objects matching `trend-claims.schema.json`. Each TrendClaim has a stable id, canonical label, description, source review ids, source statements, and scope note.

Only included full-text reviews with registered PDFs may source a TrendClaim. Persist the claims before research-paper comparison. Research papers compare against TrendClaims rather than every review independently.

## Phase C: time anchor and trend baseline

Maintain two separate references:

- time anchor: the newest semantically included review by publication date; it defines the research window start at six calendar months before publication;
- trend baseline: the newest included review with a registered PDF and non-empty future-trend evidence.

These may be different reviews. All valid TrendClaims from all included full-text reviews remain available for comparison.

If no related review exists, enter `no_related_reviews`: use the Module 01 two-year window, skip trend-consistent/trend-extension classification, analyze the included research as `new_direction`, and still produce three to five evidence-backed first-review perspectives. The no-review branch must continue through perspective persistence, chat-branch creation, and user perspective selection; it must not stop after reporting that no review exists.

## Phase D: reuse and gap-only research retrieval

Import qualifying Module 01 papers in the selected research window. Run `plan-module02-research` before any API call.

For every frozen TopicProfile query:

- `reuse_module01`: do not call OpenAlex again;
- `already_supplemented`: do not call OpenAlex again;
- `supplement`: retrieve because Module 01 failed, did not cover the whole window, or reached its 50-record page cap.

Module 02 may only run frozen TopicProfile queries whose ids are marked `supplement`. Call `search-post-review --query-id <id>`; the Python core resolves scope and query text. Use title-and-abstract search, up to 10 pages of 100 records, and mark truncation. Deduplicate against Module 01.

## Phase E: research comparison

Export research batches of 25 records by default. Classify each as:

- `trend_consistent`: realizes or validates one or more TrendClaims;
- `trend_extension`: materially extends one or more TrendClaims;
- `new_direction`: relevant but matches no TrendClaim;
- `excluded`: not sufficiently related.

Trend-consistent and trend-extension records must name valid TrendClaim ids. New-direction records must not claim a matched TrendClaim.

## Phase F: differentiated review angles

Propose three to five angles. Each includes candidate title, organizing question, supporting review/research ids, similarities, substantive differences, recommended scope, and evidence/overlap risks. Prioritize trend extensions and new directions.

## Final output

Generate two outputs:

1. concise chat brief from `render-module02-summary` with counts, anchors, TrendClaim count, category counts, and 3–5 recommended angles;
2. complete saved artifact from `render-module02-report` with every review, link, structure, trend, research classification, and comparison.

Display only the concise brief by default and provide the full artifact path. Then:

1. save the perspectives so their SQLite logical branch records exist in every runtime;
2. apply the adapter policy:
   - DeepSeek Harness: call `create_review_perspective_branches`; when rebuilding, pass persisted Session IDs as `existing_session_id`, save returned mappings with `attach-perspective-sessions`, and retry only missing/failed ranks;
   - Kiro Crew: create visible peer sessions only if a genuine persistent session tool is mounted; otherwise keep logical branches;
   - Codex or unknown: keep logical branches unless a genuine persistent visible-session API is available;
3. present one numbered plain-text option per perspective in every runtime, such as `1. 视角1｜评测基准与可靠性`, then stop until the user replies;
4. on selection, run `select-perspective --rank <N>`, which creates or resumes that perspective's Module 03 outline run;
5. DeepSeek Harness directs the user to the selected real child Session; Kiro Crew and Codex without visible branches continue in the selected logical branch;
6. load or read `review-outline-design` and begin its outline-only iteration;
7. leave all other branches available. When the user returns to this Parent and selects another perspective, create or resume that perspective's independent Module 03 outline run.

Logical perspective branches are always sufficient for selection reconstruction. Do not claim a real Session fork exists unless a real Session ID was attached.

The parent stays at status `perspectives_ready` and acts as the reusable perspective-selection hub.

Module 02 MUST NOT draft review prose, generate a manuscript, create the detailed outline itself, produce figures, or export Word/LaTeX. Selecting a perspective authorizes only a handoff to that perspective's Module 03 outline run.
