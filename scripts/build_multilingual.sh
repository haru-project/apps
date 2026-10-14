#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/scripts/demo_language.sh"
source "${ROOT_DIR}/docker/multilingual/sources.env"
BUILD_DIR="${ROOT_DIR}/.runtime/multilingual"
mkdir -p "${BUILD_DIR}"

checkout_source() {
    local repo="$1" revision="$2" dest="$3"
    local git_dir="${BUILD_DIR}/git/${repo}"
    if [[ ! -d "${git_dir}" ]]; then
        git init -q "${git_dir}"
        git -C "${git_dir}" remote add origin "git@github.com:haru-project/${repo}.git"
    fi
    if ! git -C "${git_dir}" cat-file -e "${revision}^{commit}" 2>/dev/null; then
        git -C "${git_dir}" fetch --depth 1 origin "${revision}"
    fi
    rm -rf "${dest}"
    mkdir -p "${dest}"
    git -C "${git_dir}" archive "${revision}" | tar xf - -C "${dest}"
}

build_image() {
    local image="$1" revision="$2" dockerfile="$3" context="$4"
    revision="${revision}:$(sha256sum "$dockerfile" | cut -d " " -f 1)"
    if [[ "$(docker image inspect --format '{{index .Config.Labels "org.haru.multilingual.source"}}' "$image" 2>/dev/null || true)" != "$revision" ]]; then
        docker build --label "org.haru.multilingual.source=${revision}" -f "$dockerfile" -t "$image" "$context"
    fi
}

checkout_source haru-llm "$LLM_REVISION" "${BUILD_DIR}/llm"
checkout_source haru-speech "$ASR_REVISION" "${BUILD_DIR}/asr"
checkout_source strawberry-tts "$TTS_REVISION" "${BUILD_DIR}/tts"
checkout_source agent_reasoner "$REASONER_REVISION" "${BUILD_DIR}/reasoner/reasoner"
checkout_source behavior_tree_plugins "$BEHAVIOR_REVISION" "${BUILD_DIR}/reasoner/behavior"
checkout_source simple-haru-episode-builder "$BUILDER_REVISION" "${BUILD_DIR}/builder"
build_image haru-llm:multilingual "$LLM_REVISION" "${ROOT_DIR}/docker/multilingual/llm.Dockerfile" "${BUILD_DIR}/llm"
build_image haru-asr:multilingual "$ASR_REVISION" "${ROOT_DIR}/docker/multilingual/asr.Dockerfile" "${BUILD_DIR}/asr"
build_image haru-reasoner:multilingual "${REASONER_REVISION}:${BEHAVIOR_REVISION}" "${ROOT_DIR}/docker/multilingual/reasoner.Dockerfile" "${BUILD_DIR}/reasoner"
build_image haru-episode-builder:multilingual "$BUILDER_REVISION" "${BUILD_DIR}/builder/Dockerfile" "${BUILD_DIR}/builder"
build_image haru-tts:multilingual "$TTS_REVISION" "${BUILD_DIR}/tts/docker/Dockerfile.multilingual" "${BUILD_DIR}/tts"
if [[ "$HARU_DEMO_LANGUAGE" == uk-UA ]]; then
    build_image haru-tts:ukrainian-multilingual "$TTS_REVISION" "${BUILD_DIR}/tts/docker/Dockerfile.ukrainian" "${BUILD_DIR}/tts"
fi
