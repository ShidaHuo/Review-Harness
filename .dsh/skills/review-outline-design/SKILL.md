---
name: review-outline-design
description: Design, self-evaluate, iteratively refine, and automatically freeze an evidence-mapped hierarchical review outline for the Agent-selected Module 02 perspective.
whenToUse: Use only after Module 02 automatically selects and persists its best perspective.
metadata:
  version: "0.12"
user-invocable: true
---

# Module 03: Review Outline Design and Iteration

## Purpose and boundary

Module 03 produces a hierarchical writing outline, explains how every section should be written, and explains why every section belongs in the structure. The root Agent evaluates each complete version, revises concrete weaknesses, and freezes the first version that passes all quality gates without asking the user.

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

The Module 02 run retains every candidate perspective as an audit record. Normal progression uses only the automatically selected branch; compatibility commands may reopen another branch only when the user explicitly requests a different run.

## Outline construction

When `module03-next` returns `create_outline` or `revise_outline`:

1. read the selected perspective and the complete Module 02 evidence already persisted;
2. do not launch a new literature search unless a later module explicitly authorizes it;
3. create a candidate review title and explain why it fits the selected perspective;
4. state the target audience, scope boundary, and global organizing principle;
5. create 3–10 consecutive top-level sections, with subsections down to at most four numbering levels. Except for Introduction and Conclusion, every top-level section must contain at least two direct second-level sections. Any method, mechanism, theory, principle, or algorithm top-level section must also contain at least one third-level section;
6. include a top-level Introduction and a top-level Future Perspective/Outlook section;
7. for every section and subsection provide purpose, ordered writing logic, key questions, structural rationale, internal evidence ids, expected takeaway, and transition;
8. map only persisted Module 02 review, paper, or TrendClaim ids; never invent evidence ids. When displaying the outline, resolve every internal id into the source title and its specific review motivation/trend, research finding/rationale, or TrendClaim description. Never expose a bare identifier as evidence content;
9. save one complete JSON document matching `schemas/review-outline.schema.json` with `import-outline`;
10. render the latest version with `render-outline` and display the complete outline in chat;
11. call `module03-next` immediately and execute its `evaluate_outline` action.

A revision reads the latest version plus the latest Agent evaluation. Preserve sound parts, change only what the evaluation or consistency requires, and save a new immutable version.

## Agent self-iteration

When `module03-next` returns `evaluate_outline`, evaluate the complete rendered version against all of these gates:

1. it fully expresses the selected perspective and stated scope;
2. its organizing logic is materially different from the included exact or adjacent reviews;
3. the hierarchy is complete and balanced, with no heading-only nodes or duplicated section roles;
4. every substantive section has adequate persisted evidence, while framework and transition sections are labeled honestly;
5. the sequence of questions, takeaways, and transitions forms one coherent review argument;
6. the outline is granular enough to support a 13,500–16,500 Chinese-character manuscript without inventing evidence.

If any gate fails, call `save-outline-evaluation --decision revise --rationale "<concrete defects and required changes>"`, follow `module03-next`, and save a new immutable version. If every gate passes, call `save-outline-evaluation --decision approved --rationale "<why all gates pass>"`. Approval freezes the latest version, creates or resumes Module 04, and returns `write_complete_manuscript`; continue immediately.

Do not ask the user to approve or modify the outline. Never overwrite an earlier version, and never approve merely to stop iteration. If a limitation cannot be repaired because persisted evidence is sparse, narrow the outline scope transparently and then evaluate the revised version.

## Completion

`module03-next` returns `run_module04` after Agent approval unless a manuscript run already exists. Module 04 writes the review from the frozen outline and persisted evidence. Module 03 itself remains outline-only.
