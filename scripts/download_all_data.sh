#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DOWNLOAD_SCRIPTS=(
    download_speech_data.sh
    download_llm_data.sh
    download_reasoner_data.sh
    download_simulator_data.sh
    download_tts_data.sh
    download_memory_data.sh
)

echo "Refreshing all data bundles (this will overwrite existing data/ directories)."

for script in "${DOWNLOAD_SCRIPTS[@]}"; do
    echo
    echo "=== Running ${script} ==="
    bash "${SCRIPT_DIR}/${script}"
done

echo
echo "All downloads finished; data/ directories have been reset and permissions refreshed."
