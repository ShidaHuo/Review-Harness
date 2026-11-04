---
name: review-manuscript-writing
extension: .md
version: "0.11"
description: Write one coherent approximately 15,000-Chinese-character review directly from the frozen Module 03 outline and save it as Markdown.
whenToUse: Use automatically after the user selects “满意，冻结大纲” in Module 03.
metadata:
  version: "0.11"
user-invocable: true
---

# Module 04: Direct Review Manuscript Writing

## Purpose

Module 04 replaces section-by-section generation and the former Module 05 self-review. The active root Agent uses one continuous conversation context to write the complete Chinese review directly from the frozen Module 03 outline, mark figure/table positions, and save the final `.md` manuscript.

## Entry gate

Module 04 requires a Module 03 run at `outline_approved`, the latest frozen outline, the selected perspective, and persisted Module 02 evidence. Do not write before explicit outline approval.

## Direct writing action

After approval:

```powershell
python -m review_harness run-module04 --module03-run-id <id> --target-characters 15000
python -m review_harness module04-next --module04-run-id <id>
```

`module04-next` returns `write_complete_manuscript`. In one root-agent writing pass:

1. read the entire frozen outline and selected perspective;
2. read the complete in-scope Module 02 evidence corpus;
3. write the full manuscript rather than stopping at internal chapter boundaries;
4. preserve every frozen numbered heading and its hierarchy;
5. maintain one global thesis, terminology, voice, transitions, and conclusion;
6. synthesize papers comparatively instead of expanding generic caution language;
7. distinguish direct findings, cross-study interpretation, uncertainty, and proposed research directions;
8. include an abstract, keywords, and references;
9. mark at least one figure and one table position with titles and concrete content suggestions;
10. never expose internal OpenAlex, review, or TrendClaim ids in user-facing prose.

Module 04 may use any relevant evidence already included by Module 02 when it improves completeness, even if a particular evidence id was not attached to an individual outline node. It must remain within the frozen perspective and scope. It performs no new literature retrieval and invents no bibliographic or experimental facts.

## Granularity contract

The Module 03 outline gate guarantees:

- every top-level section except Introduction and Conclusion has at least two direct second-level sections;
- method, mechanism, theory, principle, or algorithm sections contain third-level structure.

Module 04 must render every frozen section number in Markdown. Python rejects missing headings.

## Length and visual markers

- target body: 15,000 Chinese characters;
- accepted range: 13,500–16,500;
- body count excludes references and marked figure/table position lines;
- at least one figure position and one table position are required.

## Persistence and final export

Submit one document matching `schemas/manuscript.schema.json`:

```powershell
python -m review_harness import-manuscript --module04-run-id <id> --input <json>
python -m review_harness export-module04 --module04-run-id <id>
```

The JSON contains the complete Markdown plus the internal list of Module 02 evidence ids used for audit. IDs remain outside the Markdown. Python validates length, frozen heading coverage, evidence membership, and figure/table markers.

The final file is:

```text
outputs/final/<module04_run_id>-review.md
```

Module 04 records its SHA-256 and counts, reports `MVP任务完成`, and stops. No Module 05 exists in this simplified workflow.

## Runtime behavior

- In Codex, the root Codex conversation writes the full manuscript directly.
- In DeepSeek Harness, the root Agent writes it directly; do not split sections into independent subagents.
- In Kiro Crew, the current root Agent writes it directly; do not fan out sections.

The goal is global manuscript coherence comparable to a direct conversation, while preserving Python gates and auditable evidence provenance.
