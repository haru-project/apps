#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"
source "${ROOT_DIR}/scripts/demo_language.sh"

bash scripts/compose.sh reasoner up reasoner context-manager -d
bash scripts/compose.sh reasoner --profile scenario up execute-task-scenario
