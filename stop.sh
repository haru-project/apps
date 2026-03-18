#!/usr/bin/env bash
set -euo pipefail

bash scripts/compose.sh perception down
bash scripts/compose.sh speech down
bash scripts/compose.sh llm down
bash scripts/compose.sh reasoner down
# TTS services run under the "tts" profile in docker-compose-tts.yaml
bash scripts/compose.sh tts --profile tts down
bash scripts/compose.sh ipad down
bash scripts/compose.sh simulator down


docker system prune -f
