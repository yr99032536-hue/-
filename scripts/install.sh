#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT="$(pwd)"
INSTALL_JAVA=0

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/install.sh [--vault /path/to/ObsidianVault] [--install-java]

What it does:
  - installs Python dependencies from requirements.txt
  - checks Java availability
  - optionally installs Java on apt-based Linux with --install-java
  - creates thesis/pdf, thesis/fin, thesis/trn
  - prints environment check results
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

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[paper-translate] plugin: $PLUGIN_DIR"
echo "[paper-translate] vault:  $VAULT"

"$PYTHON_BIN" -m pip install -r "$PLUGIN_DIR/requirements.txt"

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

"$PYTHON_BIN" "$PLUGIN_DIR/scripts/setup_thesis_workspace.py" --vault "$VAULT"
"$PYTHON_BIN" "$PLUGIN_DIR/scripts/check_environment.py" --vault "$VAULT"

echo "[paper-translate] install complete"
