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
# Zoom H8 only, with its active inputs selected at runtime.
python3 - "$DATA_FOLDER/configs/haru_speech.yaml" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
replacements = (
    ("detect_active_channels: false", "detect_active_channels: true"),
    ("process_active_channels_only: false", "process_active_channels_only: true"),
    ("dynamic_capture_controlled: false", "dynamic_capture_controlled: true"),
    ("exclude_channels: [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11]", "exclude_channels: [10, 11]"),
    ("""        enabled: true
        capture_enabled: true
        speech_enabled: true""", """        enabled: false
        capture_enabled: false
        speech_enabled: false"""),
    ("localization_enabled: true", "localization_enabled: false"),
    ("""    capture_device: \"kinect/cam_1\"
    source_id: \"mic_1\"
    input_topic: \"/perception/sensor/audio/kinect/cam_1\"""", """    capture_device: \"zoom_h8\"
    source_id: \"mic_0\"
    input_topic: \"/perception/sensor/audio/zoom_h8\""""),
    ("""    detect_active_channels: false
    active_channel_rms_threshold: 0.010
    active_channel_warmup_secs: 1.0""", """    detect_active_channels: true
    active_channel_rms_threshold: 0.003
    active_channel_warmup_secs: 2.0"""),
)
for old, new in replacements:
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit(f"Speech config does not contain expected setting: {old!r}")
path.write_text(text, encoding="utf-8")
PY

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
