#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_VAULT="$(cd "$PLUGIN_DIR/../.." && pwd)"
VAULT="$DEFAULT_VAULT"
INSTALL_JAVA=0
USER_TAG="${USER:-codex}"
VENV_DIR="${PAPER_TRANSLATE_VENV:-/tmp/paper-translate-venv-$USER_TAG}"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/install.sh [--vault /path/to/ObsidianVault] [--install-java]

What it does:
  - creates or reuses a local Python virtual environment in /tmp
  - installs Python dependencies from requirements.txt
  - checks Java availability
  - optionally installs Java on apt-based Linux with --install-java
  - migrates legacy thesis/ to 논문/ if needed
  - creates 논문/pdf, 논문/fin, 논문/trn
  - prints environment check results

Defaults:
  - if --vault is omitted, the installer assumes this plugin lives in <vault>/plugins/paper-translate
  - override the runtime virtualenv path with PAPER_TRANSLATE_VENV=/custom/path
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault)
      VAULT="$2"
      shift 2
      ;;
    --install-java)
      INSTALL_JAVA=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

PYTHON_BOOTSTRAP="${PYTHON_BIN:-python3}"

echo "[paper-translate] plugin: $PLUGIN_DIR"
echo "[paper-translate] vault:  $VAULT"

if ! command -v "$PYTHON_BOOTSTRAP" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BOOTSTRAP" >&2
  echo "Set PYTHON_BIN=/path/to/python3 and rerun the installer." >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]] || ! grep -q "include-system-site-packages = true" "$VENV_DIR/pyvenv.cfg" 2>/dev/null; then
  echo "[paper-translate] creating virtual environment: $VENV_DIR"
  "$PYTHON_BOOTSTRAP" -m venv --clear --copies --system-site-packages "$VENV_DIR"
fi

PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

echo "[paper-translate] python: $PYTHON_BIN"

if ! "$PIP_BIN" install -r "$PLUGIN_DIR/requirements.txt"; then
  echo "Python dependency installation failed." >&2
  echo "If this machine is offline, install once on a networked machine or use a Python environment that already has opendataloader-pdf and PyMuPDF." >&2
  exit 1
fi

if ! command -v java >/dev/null 2>&1; then
  if [[ "$INSTALL_JAVA" -eq 1 ]]; then
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y openjdk-21-jdk
    else
      echo "Java is missing and this system does not have apt-get." >&2
      echo "Install Java 11+ manually, then rerun this installer." >&2
      exit 1
    fi
  else
    echo "Java is missing." >&2
    echo "Rerun with --install-java on apt-based Linux, or install Java 11+ manually." >&2
    exit 1
  fi
fi

"$PYTHON_BIN" "$PLUGIN_DIR/scripts/setup_workspace.py" --vault "$VAULT"
"$PYTHON_BIN" "$PLUGIN_DIR/scripts/check_environment.py" --vault "$VAULT"

echo "[paper-translate] install complete"
echo "[paper-translate] next:"
echo "  1. Put PDFs in: $VAULT/논문/pdf"
echo "  2. Run /trans in Codex"
echo "  3. Translated notes will appear in: $VAULT/논문/trn"
