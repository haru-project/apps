#!/usr/bin/env bash
set -euo pipefail

# Enable every profile while tearing down so explicitly started optional
# services (for example the LLM dashboard or speech localization) are included.
bash scripts/compose.sh perception --profile "*" down
bash scripts/compose.sh speech --profile "*" down
#bash scripts/compose.sh llm --profile "*" down
bash scripts/compose.sh reasoner --profile "*" down
bash scripts/compose.sh tts --profile "*" down
bash scripts/compose.sh ipad --profile "*" down
bash scripts/compose.sh simulator --profile "*" down
bash scripts/compose.sh timeline-player --profile "*" down
bash scripts/compose.sh memory --profile "*" down
bash scripts/compose.sh nlp --profile "*" down
bash scripts/compose.sh domain-bridge --profile "*" down
