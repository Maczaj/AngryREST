#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SONAR_HOST_URL="${SONAR_HOST_URL:-http://localhost:9000}"
SONAR_TOKEN="${SONAR_TOKEN:-}"

if [[ -z "$SONAR_TOKEN" && -f "$HOME/personal_infra/sonar/.env" ]]; then
  SONAR_TOKEN="$(grep -E '^SONARQUBE_TOKEN=' "$HOME/personal_infra/sonar/.env" | cut -d= -f2-)"
fi
if [[ -z "$SONAR_TOKEN" ]]; then
  echo "ERROR: SONAR_TOKEN not set and not found in ~/personal_infra/sonar/.env"
  exit 1
fi

if ! command -v sonar-scanner &>/dev/null; then
  SCANNER_BIN="$(ls -d "$HOME"/opt/sonar-scanner-*/bin 2>/dev/null | sort -V | tail -1)"
  if [[ -n "$SCANNER_BIN" ]]; then
    export PATH="$SCANNER_BIN:$PATH"
  else
    echo "ERROR: sonar-scanner not found in PATH or ~/opt/sonar-scanner-*/bin"
    exit 1
  fi
fi

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python"
fi

echo "=== Generating Python coverage ==="
(cd "$SCRIPT_DIR" && "$PYTHON_BIN" -m pytest tests/ \
  --cov=angryrest --cov-report=xml:coverage.xml >/dev/null || true)

echo "=== Scanning ==="
(cd "$SCRIPT_DIR" && sonar-scanner \
  -Dsonar.host.url="$SONAR_HOST_URL" \
  -Dsonar.token="$SONAR_TOKEN")

echo ""
echo "=== Done ==="
echo "  Dashboard: $SONAR_HOST_URL/dashboard?id=angryrest"
