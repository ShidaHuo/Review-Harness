---
name: review-manuscript-evaluation
version: "0.10.1"
description: Evaluate the Module 04 review for perspective, differentiation, logic, and completeness; revise it concretely; and export the final DOCX.
whenToUse: Use automatically after Module 04 completes its Markdown manuscript.
metadata:
  version: "0.10.1"
user-invocable: true
---

# Module 05: Manuscript Evaluation, Revision, and DOCX Export

## Purpose

Module 05 evaluates the completed Module 04 review, turns every substantive weakness into a concrete revision instruction, revises the manuscript accordingly, and exports the final version as `.docx`.

Module 05 is driven by `module05-next`. Every nonterminal action returns `must_continue=true`; execute evaluation, revision, and DOCX export without sending an intermediate user-visible message. Stop only after `mvp_complete`.

## Evaluation scope

Evaluate only:

1. **Review perspective**: whether the selected perspective is explicit, sustained, useful, and reflected throughout the manuscript.
2. **Differentiation**: how the manuscript differs substantively from previously published exact-topic or adjacent reviews analyzed in Module 02.
3. **Logic**: whether sections build a coherent argument, transitions work, concepts precede applications, comparisons support conclusions, and the future section follows from prior analysis.
4. **Completeness**: whether the manuscript covers the necessary concepts, evidence clusters, counterevidence, limitations, applications, and unresolved questions within its declared scope.

Do not evaluate or criticize:

- formatting or typography;
- figure/table visual quality or placement;
- reference formatting;
- citation or bibliographic accuracy.

These exclusions must not appear as weaknesses or revision tasks.

## Specific evaluation

Call `module05-next`. For `evaluate_manuscript`, read the Module 04 Markdown, the selected perspective, frozen outline, and Module 02 prior-review analyses. Return `schemas/manuscript-evaluation.schema.json`.

Every dimension must include:

- a 1–5 score;
- manuscript-specific strengths;
- manuscript-specific weaknesses;
- concrete evidence naming sections, claims, transitions, or omissions;
- required content changes.

Every priority revision must include:

- unique id `R1`, `R2`, ...;
- priority;
- exact manuscript location;
- current problem;
- concrete change instruction;
- observable success criterion.

Avoid generic comments such as “improve logic” or “add detail”. State what to move, add, remove, synthesize, compare, or qualify.

## Revision

After importing the evaluation, `module05-next` returns `revise_manuscript`. Apply every priority revision to the actual text. Preserve supported claims that are outside the requested changes. Do not introduce new literature or fabricate evidence.

Return `schemas/manuscript-revision.schema.json` with:

- complete revised Markdown;
- every addressed revision id;
- one change-log entry per revision id naming the location and actual change.

Python refuses a revision that omits an evaluation item, loses most of the source manuscript, expands far beyond scope, drops the section hierarchy, or contains unresolved internal evidence ids.

## Final DOCX

When `module05-next` returns `export_final_docx`, run:

```powershell
python -m review_harness export-final-docx --module05-run-id <id>
```

The Python standard-library exporter writes:

- `outputs/final/<module05_run_id>-final-review.md`;
- `outputs/final/<module05_run_id>-final-review.docx`.

It records the DOCX SHA-256 and returns `Module 05完成，最终DOCX已生成`.

## Endpoint

Module 05 is the final workflow stage. No Module 06 exists. The DOCX remains a research draft requiring human scientific review before submission.
