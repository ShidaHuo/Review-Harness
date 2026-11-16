---
name: research-topic-evaluation
description: Produce a lightweight two-year research-paper snapshot for deciding whether to continue with a scientific review topic.
whenToUse: Use when the user asks to write, prepare, plan, or assess a literature review around a scientific topic.
metadata:
  version: "0.12"
user-invocable: true
---

# Research Topic Evaluation

## Purpose

Module 01 is a concise topic pre-assessment. It retrieves original research papers at two topic levels, summarizes the field briefly, displays the result, and makes an auditable Agent decision to continue or stop without asking the user.

Before this Skill, run `python runtime_adapter.py` and follow its interaction policy. DeepSeek Harness loads this file as a native Skill; Kiro Crew and Codex may read the same file directly. The scientific workflow and boundaries are identical in every runtime.

Read `search-rules.md`, `evaluation-criteria.md`, `nature-index-source-policy.md`, and `report-template.md` before running.

## Mandatory cross-runtime conductor

After creating or resuming Module 01, call `module01-next --run-id <id>` after every persisted step. `create-run` reuses the newest unfinished run for the same normalized topic instead of creating a duplicate, and every Module 01 command returns `next_action` plus `must_continue`. When `must_continue=true`, execute the action in the same turn; do not end with a progress-only message.

- `search_literature`: execute every returned frozen query id.
- `screen_papers`: export with `export-module01-papers`, classify every pending title/abstract in batches of about 25, import all labels, then continue.

For each screening batch, import a JSON object with a `papers` array; each item has `paper_id`, `label` (`direct`, `technical`, `excluded`, or `uncertain`), `confidence` (`low`, `medium`, or `high`), `reason`, and `actor`. After each import call `module01-next` and continue with any remaining null `relevance_label` records. The number of pending records is not a stopping condition.
- `synthesize_report_and_decide`: synthesize and display the complete five-section report, assess research heat, academic impact, maturity, evidence sufficiency, and review-writing value, then persist the Agent decision with `save-agent-decision`.
- `start_module02`: transition immediately after an Agent `recommended` decision.
- `module01_complete`: stop after any other final recommendation.

A 50-record cap is a report limitation, not a reason to skip semantic screening. Provider failure may stop only after its checkpoint is persisted.

## Step 1: Derive two topic levels

Create two user-facing Chinese labels:

- `exact_research_label`: the complete user topic + “研究论文”;
- `parent_research_label`: the nearest coherent parent technology + “研究论文”.

Example:

- user topic: 紫外微型计算光谱仪;
- exact label: 紫外微型计算光谱仪研究论文;
- parent label: 微型计算光谱仪研究论文.

The report must use these labels instead of generic “直接相关” and “技术相关”. Store them in `display_labels` in the TopicProfile.

## Step 2: Freeze a bounded profile

Create:

- a strict `direct` boundary for the complete topic;
- a `technical` boundary for the parent technology;
- an exclusion boundary;
- at most 3 direct and 3 technical OpenAlex queries;
- one rolling two-year publication window calculated from the system date.

Do not create review or foundational queries. Only original research works are in scope. Module 01 may read metadata, titles, and abstracts only. It must not resolve, download, parse, OCR, or send PDF/full-text content to the model; all PDF acquisition belongs to Module 02 after approval.

## Step 3: Run retrieval

Before the first OpenAlex call, let the Python client resolve credentials in this order: explicit process argument, `OPENALEX_API_KEY` environment variable, `OPENALEX_API_KEY_FILE`, then project-root `OPENALEX_API_KEY.txt`. The Agent must never read, print, summarize, copy, or pass the TXT content as a tool argument. It may report only `configured` or `not configured`.

The TXT file contains exactly one non-empty line: the raw key, without quotes or an `OPENALEX_API_KEY=` prefix. The Python client sends it only as an `Authorization: Bearer` header.

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m review_harness init-db
python -m review_harness create-run --topic "<topic>" --profile "<topic-profile-json>"
python -m review_harness search-openalex --run-id <run_id> --query-id <frozen-query-id> --max-pages 1 --per-page 50
```

`create-run` stores one canonical query plan per normalized topic. Later runs for the same topic automatically reuse that plan even if an Agent proposes different query strings. Execute only by `query_id`; the Python core resolves query text and scope and rejects unknown ids. Stop after every frozen id has been attempted. Do not pass or rewrite query strings at execution time.

Do not switch providers, search reviews, download PDFs, or perform a deep audit when a query fails. Classify every returned research-paper title and abstract, then persist every label with `import-module01-relevance` before rendering the report or asking for approval. The Python core rejects both final report rendering and `approved` decisions while any linked paper remains unclassified or any frozen query remains unattempted.

## Step 4: Check journal context

Use only the semantically included research papers. Report:

- distinct journal count;
- Nature Index journal-paper share using the bundled local directory;
- up to five main journals.

`create-run` automatically parses `.dsh/skills/research-topic-evaluation/nature-index-publications.tsv`, verifies all 177 rows, computes its SHA-256, and attaches the immutable snapshot. Do not access the Nature website. Module 02 reuses the attached snapshot id. If the local file is invalid or missing, report Nature Index coverage as unavailable rather than using another source.

Do not query or report CAS partitions.

## Step 5: Display the report

Render `report-template.md` directly in the conversation before any decision tool call. Normal length is 800–1200 Chinese characters excluding compact tables. Do not include review statistics, existing-review lists, query logs, API debugging, audit narratives, or appendices.

## Step 6: Make the Agent decision

After the complete report is visible, the root Agent makes one final recommendation and records a concrete rationale:

- `recommended`: the topic has enough coherent recent evidence, identifiable technical routes or debates, and review-writing value; run `save-agent-decision --recommendation recommended --rationale "<reason>"` and continue immediately to Module 02.
- `reframe_required`, `insufficient_evidence`, or `not_recommended`: the current topic should not continue; save that recommendation and rationale, state briefly that the workflow ended, and stop.

Do not ask the user to choose Continue/End. Do not use a question card or numbered decision prompt. Provider failure is a recoverable checkpoint, not an automatic negative scientific judgment.

## Output rules

- All literature is limited to the system-date rolling two-year window.
- Count research works only; exclude reviews and commentary.
- Retrieval counts are not semantic inclusion counts.
- Nature Index is contextual, not an automatic quality gate.
- Missing values remain missing.
- Do not start Module 02 before a persisted Agent `recommended` decision.
