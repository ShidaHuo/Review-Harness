---
name: review-outline-design
description: Design and iteratively refine an evidence-mapped hierarchical review outline for one selected Module 02 perspective.
whenToUse: Use only after the user selects a persisted Module 02 perspective.
metadata:
  version: "0.8"
user-invocable: true
---

# Module 03: Review Outline Design and Iteration

## Purpose and boundary

Module 03 produces a hierarchical writing outline, explains how every section should be written, and explains why every section belongs in the structure. It iterates with the user until the user approves and freezes one version.

Module 03 does not draft an abstract, introduction, section prose, complete review, reference manuscript, figure, Word file, or LaTeX file. Outline bullets must remain planning instructions rather than manuscript paragraphs.

Read `outline-rules.md` and `report-template.md`. Run `python runtime_adapter.py` and use its interaction policy.

## Entry gate

Module 03 requires:

- a Module 02 run at `perspectives_ready`;
- a perspective branch at `selected_for_module03`;
- the selected perspective rank;
- the persisted Module 02 reviews, TrendClaims, research classifications, and perspective JSON.

Start with:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m review_harness start-module03 --module02-run-id <id> --rank <1..5>
python -m review_harness module03-next --module03-run-id <id>
```

The Module 02 Parent remains a selection hub. Each perspective has an independent Module 03 outline run and version history. Returning to the Parent and selecting another perspective must not overwrite an existing outline run.

## Outline construction

When `module03-next` returns `create_outline` or `revise_outline`:

1. read the selected perspective and the complete Module 02 evidence already persisted;
2. do not launch a new literature search unless a later module explicitly authorizes it;
3. create a candidate review title and explain why it fits the selected perspective;
4. state the target audience, scope boundary, and global organizing principle;
5. create 3–10 consecutive top-level sections, with subsections down to at most four numbering levels;
6. include a top-level Introduction and a top-level Future Perspective/Outlook section;
7. for every section and subsection provide purpose, ordered writing logic, key questions, structural rationale, internal evidence ids, expected takeaway, and transition;
8. map only persisted Module 02 review, paper, or TrendClaim ids; never invent evidence ids. When displaying the outline, resolve every internal id into the source title and its specific review motivation/trend, research finding/rationale, or TrendClaim description. Never expose a bare identifier as evidence content;
9. save one complete JSON document matching `schemas/review-outline.schema.json` with `import-outline`;
10. render the latest version with `render-outline` and display the complete outline in chat.

A revision reads the latest frozen version plus the latest user feedback. Preserve accepted parts, change only what the feedback or consistency requires, and save a new immutable version.

## User iteration

After displaying each outline version, every runtime presents the same numbered plain-text prompt:

1. 满意，冻结大纲
2. 继续修改

- For `满意，冻结大纲`, call `save-outline-feedback --decision approved`. This automatically starts Module 04, exports the final Markdown file, reports `MVP任务完成`, and stops.
- For `继续修改`, ask the user for concrete free-text changes. Do not infer approval. After feedback arrives, call `save-outline-feedback --decision revise --feedback "<feedback>"`, then follow `module03-next` and produce the next version.
- Silence, timeout, or skipped interaction leaves the run at `awaiting_outline_feedback`.

The loop may repeat without a fixed iteration limit. Never overwrite an earlier outline version.

## Completion

`module03-next` returns `run_module04` after explicit user approval unless the final export already exists. Module 04 freezes and saves the latest outline as Markdown. Module 03 itself remains outline-only, and no prose-writing module is authorized.
