#!/usr/bin/env bash
set -euo pipefail

# Enable every profile while tearing down so explicitly started optional
# services (for example the LLM dashboard or speech localization) are included.
bash scripts/compose.sh llm up action-args dashboard --force-recreate -d
bash scripts/compose.sh reasoner up reasoner context-manager --force-recreate -d
bash scripts/compose.sh reasoner up execute-task-scenario --force-recreate