# Review Harness MVP

A local-first, auditable workflow for evaluating a scientific review topic, mapping existing reviews and recent research, automatically selecting a review perspective, self-iterating a structured writing outline, and writing an approximately 15,000-Chinese-character Markdown review after the outline quality gate passes.

The MVP supports **DeepSeek Harness**, **Kiro Crew**, and **Codex** through one Python core and runtime-specific orchestration rules.

## MVP workflow

```text
Scientific topic
→ Module 01: two-year topic feasibility assessment and Agent continue/stop decision
→ Module 02: review landscape and post-review research analysis
→ Agent scores 3–5 perspectives and selects the best one
→ Module 03: iterative hierarchical outline design and Agent self-review
→ Agent freezes the first outline that passes every quality gate
→ Module 04: one direct root-agent pass for an approximately 15,000-character review, figure/table position markers, and final Markdown
→ MVP complete
```

Modules 01 and 02 never draft review prose. Module 01 automatically stops weak topics or advances viable ones. Module 02 automatically selects the strongest perspective using differentiation, completeness, and maturity scores. Module 03 self-evaluates immutable outline versions and freezes the first passing version. The root Agent then writes the complete review directly in one coherent Module 04 context and exports Markdown. There is no Module 05 self-review stage.

## Features

- A globally discoverable Codex Skill that locates the editable installation without copying credentials or workflow state.
- Python-frozen OpenAlex query plans shared across supported agent hosts.
- Rolling two-year original-research retrieval with bounded query budgets.
- Title/abstract semantic screening and deterministic deduplication.
- A bundled Nature Index venue snapshot with source date and SHA-256 provenance.
- Exact-topic review preference with a top-five adjacent-review fallback.
- Legal open-access PDF checks and a safe institutional-access decision path.
- TrendClaim normalization and post-review research classification.
- Automatic recovery when research retrieval finds a review missed by review discovery, including baseline invalidation and re-screening.
- Three to five differentiated review perspectives with auditable differentiation, completeness, and maturity scores.
- Automatic weighted perspective selection with persisted rationale and logical branches.
- Versioned Module 03 outlines with section-level writing logic, rationale, and Agent self-review.
- Direct single-pass Module 04 writing with a 15,000-character target, complete frozen-heading validation, broader in-scope evidence use, figure/table position markers, and final Markdown SHA-256.
- SQLite checkpoints for interrupted-run recovery.

## Requirements

- Python 3.12 or newer.
- Git.
- Your own OpenAlex API key.
- One supported host: DeepSeek Harness, Kiro Crew, or Codex.

Apply for and manage a key through the [OpenAlex authentication documentation](https://help.openalex.org/api/authentication/). Never post your key in chat, issues, screenshots, or logs.

## Installation

Clone the repository:

```bash
git clone https://github.com/ShidaHuo/Review-Harness.git
cd Review-Harness
```

### Windows: one-click Codex setup

1. Download or clone this repository.
2. Double-click `setup-codex.cmd`.
3. If no key is configured, paste your own OpenAlex key into the masked local terminal prompt.
4. Restart Codex so it discovers the global `$review-harness` Skill.
5. Invoke `$review-harness` from any workspace and enter a scientific review topic.

The one-click installer installs the Skill under `$CODEX_HOME/skills/review-harness` (or `~/.codex/skills/review-harness` when `CODEX_HOME` is unset) and writes a non-secret `project-root.txt` pointer so Codex can locate the editable installation even when it uses a different Python environment. The bundled runner forces every conductor command to use that project root, preventing SQLite state and outputs from being written to the caller's workspace. It never copies the OpenAlex key or runtime data into the Skill and never overwrites an unrelated Skill with the same name.

Manual runtime installation remains available:

```powershell
.\install.ps1 -Runtime codex
```

Use `deepseek-harness`, `kiro-crew`, `codex`, or `auto` as the runtime value.

To install the optional DeepSeek persistent Session-fork plugin when `dsh` is on PATH:

```powershell
.\install.ps1 -Runtime deepseek-harness -InstallDeepSeekPlugin
```

If `dsh` is not on PATH, provide its executable:

```powershell
.\install.ps1 -Runtime deepseek-harness -InstallDeepSeekPlugin `
  -DshCliPath "C:\path\to\dsh.cmd"
```

### Linux and macOS

```bash
chmod +x install.sh
./install.sh codex
```

Optional DeepSeek plugin installation:

```bash
INSTALL_DSH_PLUGIN=1 DSH_PROFILE=desktop ./install.sh deepseek-harness
```

Manual installation is also supported:

```bash
python -m pip install -e .
python runtime_adapter.py --runtime codex
```

## Configure your OpenAlex key

Choose one method. Do not commit the key.

### Project key file

Create `OPENALEX_API_KEY.txt` in the repository root. The file must contain exactly one non-empty line with the raw key:

```text
your_own_openalex_key
```

Do not add quotes or an `OPENALEX_API_KEY=` prefix.

### Environment variable

PowerShell:

```powershell
$env:OPENALEX_API_KEY = "your-own-key"
```

Bash/zsh:

```bash
export OPENALEX_API_KEY="your-own-key"
```

Credential resolution order is explicit Python argument, `OPENALEX_API_KEY`, `OPENALEX_API_KEY_FILE`, then project-root `OPENALEX_API_KEY.txt`. The client sends the key in an Authorization header, never in a logged URL.

## Start a review

After Codex setup, restart Codex and invoke the global Skill from any workspace:

```text
$review-harness 围绕反双极性场效应晶体管写一篇综述
```

The Skill resolves the editable Review Harness installation, switches workflow operations to that project root, reads `AGENTS.md`, and starts Module 01. Runtime state and generated outputs remain in the Review Harness installation rather than the caller's workspace.

Without the global Skill, you can still open the cloned repository as the workspace and request a review normally:

```text
围绕反双极性场效应晶体管写一篇综述
```

During validation, you can explicitly request detection:

```text
请读取AGENTS.md，运行python runtime_adapter.py，并严格按照返回策略启动Review Harness。
```

Topic continuation, perspective selection, and outline approval are Agent-autonomous. User input is requested only for human-only access steps such as institutional login or an explicit request to override the normal workflow. The workflow never requests an institution password, MFA code, cookie, or OpenAlex key in chat.

## Runtime behavior

| Host | Orchestration | Perspective state | Automatic progression |
|---|---|---|---|
| DeepSeek Harness | Native Skills, Workflow, bounded subagents | SQLite logical branches; optional Session metadata | Module 01–04 Agent gates |
| Kiro Crew | Python core; bounded workflow/spawn only when useful | SQLite logical branches | Module 01–04 Agent gates |
| Codex | Python core and bounded local/root-agent batches | SQLite logical branches | Module 01–04 Agent gates |

All hosts share the same SQLite schema, query plan, evidence rules, completion gates, and output contracts.

## Institutional full-text access

The workflow checks legal open-access PDFs first. If none is available, it asks:

```text
1. I will sign in on the official institution page and download the PDF
2. The institution has no subscription; skip full text
3. Do not use institutional access; continue from the abstract
```

Credentials are entered only on the official institution page. Hosts without an authenticated browser instruct the user to download an entitled PDF in their normal browser and place it under `runtime/institutional-pdfs/`. Publisher and institution terms still apply.

## Outputs

Runtime data and generated outputs are local and ignored by Git:

```text
runtime/research.sqlite3
runtime/raw/
runtime/institutional-pdfs/
outputs/
outputs/final/<module04_run_id>-review.md
```

The final Module 04 Markdown contains the complete approximately 15,000-character review, all frozen headings, in-scope evidence, marked figure/table positions, references, and a content SHA-256. It still requires human scientific review before submission.

## Project structure

```text
AGENTS.md                              Cross-runtime workflow contract
runtime_adapter.py                     Runtime detection and capability policy
codex-skill/review-harness/            Global Codex launcher Skill
src/review_harness/                    Python core and CLI
schemas/                               JSON contracts
.dsh/skills/                           Module 01–04 Skills
workflows/module02-review-landscape/   DeepSeek batch workflows
plugin/perspective-branches/           Optional DeepSeek Session-fork plugin
prompts/                               Structured analysis prompts
docs/                                  Module documentation
tests/                                 Offline unit tests
```

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests
node --check plugin/perspective-branches/index.js
```

Do not commit `runtime/`, `outputs/`, PDFs, `.env`, or `OPENALEX_API_KEY.txt`.

## Current limitations

- The bundled Nature Index list is a dated local snapshot and must not be described as a live directory.
- OpenAlex counts may be lower bounds when a query reaches its configured page cap.
- Semantic screening still depends on the active model, while query execution and state gates are deterministic.
- Institutional access does not override publisher licenses or permit bulk downloading.
- The MVP produces a coherent Markdown review in Module 04; it does not include a separate self-review stage or DOCX export.

## Security

See `SECURITY.md`. Report vulnerabilities privately and rotate any key that may have been exposed.

## License

MIT License. See `LICENSE`.
