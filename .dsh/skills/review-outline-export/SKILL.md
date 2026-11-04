---
name: review-manuscript-writing
extension: .md
version: "0.10.1"
description: Write an approximately 15,000-Chinese-character review from the frozen Module 03 outline, mark figure/table positions, and save the final Markdown manuscript.
whenToUse: Use automatically after the user selects “满意，冻结大纲” in Module 03.
metadata:
  version: "0.10.1"
user-invocable: true
---

# Module 04: Review Manuscript Writing and Markdown Export

## Purpose

Module 04 writes a complete Chinese review manuscript from the explicitly approved Module 03 outline. The target is approximately 15,000 Chinese characters under the Python counting rule, with an accepted range of 13,500–16,500. It marks recommended figure and table positions and saves the assembled manuscript as `.md`. Completion ends the current MVP.

## Entry gate

Module 04 requires:

- a persisted Module 03 run at `outline_approved`;
- the latest frozen outline version;
- the selected Module 02 perspective and evidence;
- explicit user choice `1. 满意，冻结大纲`.

Do not draft before outline approval.

## Evidence boundary

Use only evidence persisted by Module 02 and mapped by the frozen outline. Do not launch new literature retrieval in Module 04. Do not invent authors, dates, DOI metadata, experimental values, claims, or references.

Internal citations use `[@evidence_id]` while drafting. Python validates every id, replaces it with numbered citations in the final file, and creates a reference list from stored metadata. User-facing output must never expose raw OpenAlex or internal ids.

## Section-batched writing

The normal approval command automatically creates or resumes a Module 04 manuscript run. Every returned action includes `must_continue`. When it is true, complete the action, call `module04-next` again, and do not send a user-visible progress message.

```powershell
python -m review_harness module04-next --module04-run-id <id>
```

When the action is `draft_manuscript_sections`, write every returned section before replying. The Python core allocates character targets from the frozen outline and returns all remaining sections in the current action so Codex and other hosts do not treat an internal batch boundary as a user-visible stopping point. Each draft must:

- follow the frozen hierarchy and section logic;
- synthesize evidence rather than list papers;
- distinguish established findings, extensions, new directions, and limitations;
- preserve negative or uncertain evidence;
- use only validated internal citation markers;
- avoid repeating the same background in multiple sections;
- provide transitions consistent with the outline;
- remain scholarly review prose rather than an outline.

Save each section as `schemas/manuscript-section.schema.json` through `import-manuscript-section`.

## Figures and tables

The completed manuscript must contain at least one evidence-grounded figure position and one evidence-grounded table position. Do not generate image binaries in this MVP. For every useful figure or table, provide a structured placeholder with:

- title;
- purpose in the argument;
- concrete content specification;
- source evidence ids.

The final Markdown renderer inserts visible markers such as:

```text
[图 2 置于此处：器件架构与传输机制分类]
[表 1 置于此处：代表性器件性能对比]
```

Each marker includes its intended content and numbered evidence sources.

## Length gate

Python counts manuscript characters after removing whitespace, Markdown symbols, and internal citation markers. References and figure/table placeholder descriptions are excluded from the 15,000-character body target.

- target: 15,000;
- minimum: 13,500;
- maximum: 16,500.

If `module04-next` returns `revise_manuscript_length`, revise the named sections toward their allocated targets and re-import them. Do not assemble outside the accepted range.

## Final assembly

When `module04-next` returns `assemble_manuscript`, run:

```powershell
python -m review_harness assemble-module04 --module04-run-id <id>
```

The assembler:

1. orders the abstract and frozen top-level sections;
2. replaces internal evidence markers with numbered citations;
3. inserts figure/table position markers;
4. creates the reference list from persisted metadata;
5. verifies the accepted body length;
6. writes `outputs/final/<module04_run_id>-review.md` atomically;
7. records path, SHA-256, character count, and completion state;
8. starts Module 05 for content evaluation and revision.

## Cross-runtime execution

- DeepSeek Harness may use bounded Workflow/subagents for independent top-level sections.
- Kiro Crew may use bounded `workflow_run` or `spawn_run` only when sections are independent.
- Codex writes the same bounded section batches with its root agent.

Every runtime follows the same Python section plans, evidence validation, length gate, assembly, and final output.

## Current stage endpoint

Module 04 completion must immediately start Module 05; it is not the final workflow state. The generated Markdown remains the input draft for content evaluation and concrete revision.
