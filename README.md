# Review Harness MVP

A local-first, auditable workflow for evaluating a scientific review topic, mapping existing reviews and recent research, iterating a structured writing outline, and writing an approximately 15,000-Chinese-character Markdown review after outline approval.

The MVP supports **DeepSeek Harness**, **Kiro Crew**, and **Codex** through one Python core and runtime-specific orchestration rules.

## MVP workflow

```text
Scientific topic
→ Module 01: two-year topic feasibility assessment
→ User chooses Continue or End
→ Module 02: review landscape and post-review research analysis
→ User selects a differentiated review perspective
→ Module 03: iterative hierarchical outline design
→ User approves and freezes the outline
→ Module 04: approximately 15,000-character review writing, figure/table position markers, and Markdown export
→ Module 05: content evaluation, concrete revision, and final DOCX export
→ MVP complete
```

Modules 01 and 02 never draft review prose. Module 03 designs an outline only. After explicit approval, Module 04 writes the review manuscript within the frozen outline and persisted evidence. Module 05 evaluates perspective, differentiation, logic, and completeness, applies concrete revisions, and exports the final DOCX.

## Features

- Python-frozen OpenAlex query plans shared across supported agent hosts.
- Rolling two-year original-research retrieval with bounded query budgets.
- Title/abstract semantic screening and deterministic deduplication.
- A bundled Nature Index venue snapshot with source date and SHA-256 provenance.
- Exact-topic review preference with a top-five adjacent-review fallback.
- Legal open-access PDF checks and a safe institutional-access decision path.
- TrendClaim normalization and post-review research classification.
- Three to five differentiated review perspectives.
- Persistent perspective branches and optional real DeepSeek Session forks.
- Versioned Module 03 outlines with section-level writing logic and rationale.
- Section-batched Module 04 manuscript writing with a 15,000-character target, validated citations, figure/table position markers, and Markdown SHA-256. The conductor returns all remaining sections and `must_continue=true` to prevent Codex from stopping at internal section boundaries.
- Module 05 content evaluation across perspective, differentiation, logic, and completeness, followed by concrete revision and final DOCX export.
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
4. Open the `Review-Harness` folder in Codex and enter a scientific review request.

The one-click installer never asks for the key in Codex chat and never overwrites an existing key file.

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

Open the cloned repository as the workspace in your agent host. In a new chat, request a review normally:

```text
围绕反双极性场效应晶体管写一篇综述
```

`AGENTS.md` requires the agent to detect its runtime and begin at Module 01. During validation, you can explicitly request detection:

```text
请读取AGENTS.md，运行python runtime_adapter.py，并严格按照返回策略启动Review Harness。
```

All user choices are numbered plain text. The workflow never requests an institution password, MFA code, cookie, or OpenAlex key in chat.

## Runtime behavior

| Host | Orchestration | Perspective branches | User choices |
|---|---|---|---|
| DeepSeek Harness | Native Skills, Workflow, bounded subagents | Optional real Session forks | Numbered plain text |
| Kiro Crew | Python core; bounded workflow/spawn only when useful | Logical branches unless persistent peer sessions exist | Numbered plain text |
| Codex | Python core and bounded local/root-agent batches | SQLite logical branches | Numbered plain text |

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
outputs/final/<module05_run_id>-final-review.md
outputs/final/<module05_run_id>-final-review.docx
```

The Module 04 Markdown contains the approximately 15,000-character draft, validated numbered citations, and marked figure/table positions. Module 05 evaluates and revises that content, then saves the final Markdown and DOCX. The DOCX still requires human scientific review before submission.

## Module 05 evaluation and final DOCX

After Module 04 completes, the workflow automatically evaluates only:

- whether the selected review perspective is explicit and sustained;
- substantive differentiation from prior exact-topic or adjacent reviews;
- manuscript argument and section logic;
- content completeness within the declared scope.

It deliberately ignores formatting, figure/table quality, and reference/citation accuracy. The evaluation names concrete manuscript locations, problems, changes, and success criteria. Every priority item must be applied before the final DOCX can be exported.

The final files are produced without Microsoft Word or an extra DOCX dependency.

## Project structure

```text
AGENTS.md                              Cross-runtime workflow contract
runtime_adapter.py                     Runtime detection and capability policy
src/review_harness/                    Python core and CLI
schemas/                               JSON contracts
.dsh/skills/                           Module 01–05 Skills
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
- The MVP produces a content-reviewed DOCX after Module 05, but the file still requires human scientific and editorial review before submission.

## Security

See `SECURITY.md`. Report vulnerabilities privately and rotate any key that may have been exposed.

## License

MIT License. See `LICENSE`.
