#!/usr/bin/env bash
# Sourced by Compose and setup; do not execute the env file as shell code.
language="${HARU_DEMO_LANGUAGE:-}"
if [[ -z "$language" ]]; then
    while IFS='=' read -r key value || [[ -n "${key:-}" ]]; do
        if [[ "$key" == HARU_DEMO_LANGUAGE ]]; then language="$value"; break; fi
    done < "${ROOT_DIR}/envs/all.env"
fi
case "${language:-en-US}" in
    en|en-US|en-us|en_US) export HARU_DEMO_LANGUAGE=en-US ;;
    es|es-ES|es-es|es_ES) export HARU_DEMO_LANGUAGE=es-ES ;;
    ja|ja-JP|ja-jp|ja_JP) export HARU_DEMO_LANGUAGE=ja-JP ;;
    uk|uk-UA|uk-ua|uk_UA) export HARU_DEMO_LANGUAGE=uk-UA ;;
    *) echo "Unsupported HARU_DEMO_LANGUAGE: ${language}. Use en-US, es-ES, ja-JP or uk-UA." >&2; return 1 ;;
esac
# The CereVoice server loads one voice for the selected demo language.
export HARU_CEREVOICE_LANGUAGE=en-US
if [[ "$HARU_DEMO_LANGUAGE" == es-ES ]]; then export HARU_CEREVOICE_LANGUAGE=es-ES; fi
