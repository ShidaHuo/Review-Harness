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

printf '%s\n' "Installation complete. Open this repository as the workspace in your supported agent host."
