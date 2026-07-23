#!/usr/bin/env bash
set -euo pipefail

bash scripts/compose.sh perception down
bash scripts/compose.sh speech down audio recognition verification localization
bash scripts/compose.sh llm down
bash scripts/compose.sh reasoner down
# TTS services run under the "tts" profile in docker-compose-tts.yaml
bash scripts/compose.sh tts --profile all down
bash scripts/compose.sh ipad down
bash scripts/compose.sh simulator down
bash scripts/compose.sh timeline-player down
bash scripts/compose.sh memory down
bash scripts/compose.sh nlp down


docker system prune -f
