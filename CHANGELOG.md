# Changelog

## 0.10.1 - 2026-11-04

- Fixed Codex stopping after the first Module 04 manuscript section batch.
- Module 04 now returns all remaining sections in one action and sets `must_continue=true` on every nonterminal action.
- Module 05 evaluation, revision, and DOCX actions now carry the same explicit continuation contract.

## 0.10.0 - 2026-11-04

- Added Module 05 evaluation of review perspective, differentiation, logic, and completeness.
- Added concrete priority revision plans with manuscript locations and success criteria.
- Added full-manuscript revision coverage checks and change logs.
- Added dependency-free final DOCX generation using standard OOXML packaging.
- Moved the MVP terminal state from Module 04 to Module 05.

## 0.9.0 - 2026-11-04

- Redefined Module 04 as section-batched Chinese review-manuscript writing after outline approval.
- Added a 15,000-character target with a 13,500–16,500 validation gate.
- Added validated internal citation markers and deterministic numbered references.
- Added structured figure and table position markers with evidence provenance.
- Added final manuscript assembly at `outputs/final/<module04_run_id>-review.md`.

## 0.8.1 - 2026-11-03

- Added `setup-codex.cmd` for double-click Codex installation on Windows.
- Added a masked local OpenAlex key prompt that never sends the key to agent chat.
- Preserved existing key files without reading or overwriting them.

## 0.8.0 - 2026-11-03

Initial public MVP candidate.

- Added deterministic Module 01 query plans, semantic-screening gates, and run continuation.
- Added Module 02 review landscape, adjacent-review fallback, institutional-access choice, TrendClaims, recent-research comparison, and perspective selection.
- Added iterative, versioned Module 03 outline design with concrete evidence rendering.
- Added Module 04 final Markdown export and MVP completion state.
- Added DeepSeek Harness, Kiro Crew, and Codex runtime adaptation.
- Added optional persistent DeepSeek perspective Session forks.
- Added bundled Nature Index venue snapshot provenance and OpenAlex credential safety.
