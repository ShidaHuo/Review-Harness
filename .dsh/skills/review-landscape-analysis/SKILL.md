---
name: review-landscape-analysis
description: Analyze topic-specific review papers, then compare post-review research against normalized trend claims to propose differentiated review angles.
whenToUse: Use only after Module 01 records an Agent recommendation to continue.
metadata:
  version: "0.12"
user-invocable: true
---

# Module 02: Review Landscape and Post-Review Research

## Entry gate and reuse

Before entering Module 02, run `python runtime_adapter.py` and use its orchestration and interaction policy. OpenAlex credential handling is shared with Module 01. The Python client automatically reuses `OPENALEX_API_KEY` or project-root `OPENALEX_API_KEY.txt`; Module 02 must not ask the user to paste the key again. The Agent may check only whether a credential is configured and must never read or expose its value.

Read the latest Module 01 decision from SQLite.

- Agent recommendation `recommended`: create or resume one Module 02 run.
- `reframe_required`, `insufficient_evidence`, or `not_recommended`: stop; Module 02 is not permitted.
- missing decision: return to Module 01 and complete its automatic decision action.

Reuse the approved Module 01 TopicProfile, its research-paper records, semantic labels, and its attached Nature Index snapshot. Do not regenerate the topic boundary or fetch a second Nature Index directory when the Module 01 snapshot is still the verified source for this run.

Read `review-search-rules.md`, `fulltext-access.md`, and `report-template.md`.

## Mandatory cross-runtime conductor

After creating or resuming a Module 02 run, call `module02-next --module02-run-id <id>` after every persisted step. Execute the returned non-blocking action and call `module02-next` again. Do not end a turn with a progress-only message while `blocking_user_input` is false. Continue through `select_best_perspective`: render both outputs, score every perspective, call `select-best-perspective`, and immediately enter the returned Module 03 run. A real user-operated SSO page or `request_institutional_access` may still pause the loop because credentials and entitlement are human-only; provider failure may stop with an explicit recoverable checkpoint. When no legal open PDF exists, persist `login_required` and offer the numbered institutional-access choice before any abstract-only downgrade.

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

If no related review exists, enter `no_related_reviews`: use the Module 01 two-year window, skip trend-consistent/trend-extension classification, analyze the included research as `new_direction`, and still produce three to five evidence-backed first-review perspectives. The no-review branch must continue through perspective persistence, automatic scoring and selection, and Module 03 startup; it must not stop after reporting that no review exists.

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
- `review_candidate`: the record is actually a review-like synthesis missed by review discovery; assign no matched ids and explain the title/abstract evidence;
- `excluded`: not sufficiently related.

Trend-consistent and trend-extension records must name valid TrendClaim ids. New-direction and review-candidate records must not claim a matched TrendClaim.

When any `review_candidate` exists, `module02-next` returns `promote_review_candidates`. Export all candidates into one JSON payload and call `promote-research-reviews`; the Python core moves them out of research comparison, returns every review to semantic screening, invalidates TrendClaims/anchors/research classifications that used the incomplete baseline, and preserves raw evidence. Re-screen the complete review set before registering a user-provided lawful PDF with `import-fulltext-access`. Never continue research comparison while a review candidate remains.

## Phase F: differentiated review angles

Propose three to five angles. Each includes candidate title, organizing question, supporting review/research ids, similarities, substantive differences, recommended scope, evidence/overlap risks, and three 0–100 scores:

- `differentiation_score`: distance from the organization, claims, and scope of existing exact or adjacent reviews;
- `completeness_score`: whether persisted evidence can support a balanced, end-to-end review within the proposed scope;
- `maturity_score`: whether the concepts, methods, comparisons, and open questions are mature enough for synthesis rather than speculation.

Add a concrete `selection_rationale` for each perspective. The Python core computes `0.40 × differentiation + 0.30 × completeness + 0.30 × maturity` and selects the highest score, breaking ties by lower persisted rank. Scores must reflect risks and evidence gaps rather than hide them. Prioritize trend extensions and new directions only when they still support a complete and mature review.

## Final output

Generate two outputs:

1. concise chat brief from `render-module02-summary` with counts, anchors, TrendClaim count, category counts, and 3–5 recommended angles;
2. complete saved artifact from `render-module02-report` with every review, link, structure, trend, research classification, and comparison.

Display only the concise brief by default and provide the full artifact path. Then:

1. save all 3–5 perspectives so their SQLite logical branch records exist;
2. render the candidate scores and rationales for audit;
3. when `module02-next` returns `select_best_perspective`, run `select-best-perspective --module02-run-id <id>`;
4. accept the Python-weighted highest-scoring perspective, persist its selection rationale, and create or resume its Module 03 outline run;
5. load or read `review-outline-design` and continue immediately with `module03-next`;
6. keep the unselected logical branches as audit records. Compatibility commands may reopen them only when explicitly requested outside the normal automatic workflow.

Do not present a perspective-selection question or wait for user input. Do not claim a real Session fork exists unless a real Session ID was attached.

The Module 02 run remains at `perspectives_ready` as the auditable source of all candidates and their scores. The selected branch alone proceeds automatically to Module 03.

Module 02 MUST NOT draft review prose, generate a manuscript, create the detailed outline itself, produce figures, or export Word/LaTeX. The persisted Agent selection authorizes only the handoff to Module 03 outline design.
