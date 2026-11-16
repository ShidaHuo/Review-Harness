#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
RUNTIME=${1:-auto}

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else "Python 3.12 or newer is required")'
"$PYTHON_BIN" -m pip install -e "$PROJECT_ROOT"

if [ "$RUNTIME" = "auto" ]; then
  "$PYTHON_BIN" "$PROJECT_ROOT/runtime_adapter.py" --compact
else
  "$PYTHON_BIN" "$PROJECT_ROOT/runtime_adapter.py" --runtime "$RUNTIME" --compact
fi

if [ "$RUNTIME" = "codex" ]; then
  CODEX_HOME_DIR=${CODEX_HOME:-"$HOME/.codex"}
  CODEX_SKILL_SOURCE="$PROJECT_ROOT/codex-skill/review-harness"
  CODEX_SKILL_DESTINATION="$CODEX_HOME_DIR/skills/review-harness"
  MANAGED_MARKER="$CODEX_SKILL_DESTINATION/.review-harness-managed"

  if [ ! -d "$CODEX_SKILL_SOURCE" ]; then
    printf '%s\n' "Bundled Codex Skill was not found: $CODEX_SKILL_SOURCE" >&2
    exit 1
  fi
  if [ -d "$CODEX_SKILL_DESTINATION" ] && [ ! -f "$MANAGED_MARKER" ]; then
    if [ ! -f "$CODEX_SKILL_DESTINATION/project-root.txt" ] ||
       [ "$(cat "$CODEX_SKILL_DESTINATION/project-root.txt")" != "$PROJECT_ROOT" ] ||
       ! cmp -s "$CODEX_SKILL_SOURCE/SKILL.md" "$CODEX_SKILL_DESTINATION/SKILL.md" ||
       ! cmp -s "$CODEX_SKILL_SOURCE/scripts/locate_review_harness.py" "$CODEX_SKILL_DESTINATION/scripts/locate_review_harness.py" ||
       ! cmp -s "$CODEX_SKILL_SOURCE/scripts/run_review_harness.py" "$CODEX_SKILL_DESTINATION/scripts/run_review_harness.py"; then
      printf '%s\n' "Refusing to overwrite an unmanaged Codex Skill: $CODEX_SKILL_DESTINATION" >&2
      exit 1
    fi
  fi

  mkdir -p "$CODEX_SKILL_DESTINATION"
  cp -R "$CODEX_SKILL_SOURCE/." "$CODEX_SKILL_DESTINATION/"
  printf '%s\n' "$PROJECT_ROOT" > "$CODEX_SKILL_DESTINATION/project-root.txt"
  printf '%s\n' 'managed-by: Review Harness installer' > "$MANAGED_MARKER"
  printf '%s\n' "Installed global Codex Skill: $CODEX_SKILL_DESTINATION"
fi

if [ "${INSTALL_DSH_PLUGIN:-0}" = "1" ]; then
  DSH_BIN=${DSH_BIN:-dsh}
  DSH_PROFILE=${DSH_PROFILE:-desktop}
  if ! command -v "$DSH_BIN" >/dev/null 2>&1; then
    printf '%s\n' "DeepSeek Harness CLI not found. Set DSH_BIN to its executable path." >&2
    exit 1
  fi
  "$DSH_BIN" plugin --profile "$DSH_PROFILE" add "file:$PROJECT_ROOT/plugin/perspective-branches"
fi

if [ -n "${OPENALEX_API_KEY:-}" ] || [ -f "$PROJECT_ROOT/OPENALEX_API_KEY.txt" ]; then
  printf '%s\n' "OpenAlex credential status: configured"
else
  printf '%s\n' "OpenAlex credential status: not configured"
  printf '%s\n' "Create OPENALEX_API_KEY.txt with your own one-line key, or set OPENALEX_API_KEY."
fi

if [ "$RUNTIME" = "codex" ]; then
  printf '%s\n' 'Installation complete. Restart Codex, then invoke $review-harness from any workspace.'
else
  printf '%s\n' "Installation complete. Open this repository as the workspace in your supported agent host."
fi
