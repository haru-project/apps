#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/speech
MODELS_FOLDER="${HARU_SPEECH_MODELS_HOST_DIR:-${HOME}/haru-speech-cache/models}"
VERIFICATION_IMAGE="${HARU_SPEECH_VERIFICATION_IMAGE:-ghcr.io/haru-project/haru-speech-verification:feature-asr-improve}"

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# Speech data
copy_with_tar "${HARU_SPEECH_BASE_IMAGE:-ghcr.io/haru-project/haru-speech-base:feature-asr-improve}" \
  /opt/ros/jazzy/workspace/install/share/haru_speech/configs \
  "$DATA_FOLDER/configs"

# The released base image can lag behind this deployment's microphone policy.
# Keep the generated, host-editable config aligned with the working live setup:
# Zoom H8 only, with its active inputs selected at runtime. Update named YAML
# sections instead of matching old values because newer images may already carry
# some or all of this policy.
python3 "${DIR}/configure_speech_data.py" \
  "$DATA_FOLDER/configs/haru_speech.yaml"

# Fetch ReDimNet before the verification node starts.  The node uses this same
# persistent TORCH_HOME mount, so startup never needs to reach GitHub's
# releases/latest endpoint (which can intermittently return HTTP 504).
mkdir -p "$MODELS_FOLDER"
for attempt in 1 2 3 4; do
  if docker run --rm \
    --entrypoint /opt/ros/jazzy/workspace/package_venv/bin/python3 \
    -e TORCH_HOME=/shared/models/torch \
    -v "$MODELS_FOLDER:/shared/models:rw" \
    "$VERIFICATION_IMAGE" \
    -c 'from haru_speech.models.sv import ReDimNetSv; ReDimNetSv.download()'; then
    break
  fi

  if [ "$attempt" -eq 4 ]; then
    echo "Unable to provision the ReDimNet speaker-verification model after 4 attempts." >&2
    exit 1
  fi

  retry_delay=$((2 ** (attempt - 1)))
  echo "ReDimNet provisioning failed; retrying in ${retry_delay}s." >&2
  sleep "$retry_delay"
done

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
# The provisioning container runs as root, so repair permissions from inside a
# container as well. A host-side chmod cannot modify the resulting root-owned
# cache files on a fresh installation.
docker run --rm \
  --entrypoint chmod \
  -v "$MODELS_FOLDER:/shared/models:rw" \
  "$VERIFICATION_IMAGE" \
  -R a+rwX /shared/models
