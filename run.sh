#!/usr/bin/env bash
set -euo pipefail

<<<<<<< Updated upstream
bash scripts/compose.sh llm up server --force-recreate -d
bash scripts/compose.sh reasoner up reasoner context-manager --force-recreate -d
=======
bash scripts/compose.sh reasoner up reasoner context-manager -d --force-recreate
>>>>>>> Stashed changes
bash scripts/compose.sh reasoner up execute-task-scenario --force-recreate
