---
name: review-outline-export
description: Export the explicitly approved Module 03 outline to a final Markdown file and end the Review Harness MVP.
whenToUse: Use automatically after the user selects “满意，冻结大纲” in Module 03.
metadata:
  version: "0.8"
user-invocable: true
---

# Module 04: Frozen Outline Markdown Export

## Purpose

Module 04 is the deterministic final step of the current MVP. It saves the user-approved outline as a final `.md` file, records its SHA-256 and path in SQLite, reports completion, and stops.

## Entry gate

Module 04 requires:

- a persisted Module 03 run;
- status `outline_approved`;
- at least one immutable outline version;
- explicit user choice `1. 满意，冻结大纲`.

A draft or revision-requested outline cannot be exported as final.

## Execution

The normal path is automatic: `save-outline-feedback --decision approved` calls Module 04 and returns the final artifact.

Recovery or idempotent rerun:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m review_harness run-module04 --module03-run-id <id>
```

Module 04:

1. loads the latest approved outline version;
2. resolves internal evidence ids to user-facing titles and concrete evidence content;
3. omits the Module 03 feedback prompt;
4. adds the frozen version, approval time, and MVP completion status;
5. writes `outputs/final/<module03_run_id>-approved-outline-vNN.md` atomically;
6. records output path and content SHA-256 in `module04_exports`;
7. returns `MVP任务完成` and performs no further work.

Repeated execution is idempotent for the same approved version.

## Boundary

Module 04 does not write review prose, add references, create figures, or export Word/LaTeX. No Module 05 exists in the current MVP.
