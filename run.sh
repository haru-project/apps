#!/usr/bin/env bash
set -euo pipefail

bash scripts/compose.sh reasoner up reasoner context-manager --force-recreate -d
bash scripts/compose.sh reasoner up execute-task-scenario --force-recreate
