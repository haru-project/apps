# Multilingual demo deployment

Set `HARU_DEMO_LANGUAGE` in the existing `envs/all.env`, then use the ordinary
`./start.sh`, `./run.sh` and `./stop.sh` commands. English (`en-US`) is the default;
Spanish (`es-ES`), Japanese (`ja-JP`) and Ukrainian (`uk-UA`) are supported, along
with short `en`, `es`, `ja`, `uk` aliases. Shell overrides and the stack wrapper's
`--language` argument take precedence. Stop services before changing language.

## Images and preparation

Compose pins the tested feature images by GHCR digest. The images include all
required service changes, including the matching reasoner/behavior plugins.
There are no local Docker builds, sibling source checkouts, source-pin env files,
or machine-specific launch overrides required by this branch.

| Service | Registry package |
| --- | --- |
| ASR | `ghcr.io/haru-project/haru-speech-recognition` |
| LLM | `ghcr.io/haru-project/haru-llm` |
| Reasoner and behavior plugins | `ghcr.io/haru-project/haru-agent-reasoner` |
| Strawberry TTS and ROS bridge | `ghcr.io/haru-project/strawberry-tts` |
| Ukrainian StyleTTS2 | `ghcr.io/haru-project/strawberry-tts` |
| Episode builder | `ghcr.io/haru-project/haru-episode-builder` |

On a fresh installation, use the existing preparation scripts:

```bash
./scripts/download_all_images.sh domain-bridge perception speech llm reasoner tts user timeline-player memory
./scripts/download_all_data.sh
./start.sh
```

Data refresh replaces existing `data/` bundles, so preserve your site's hardware
configuration and saved tasks before refreshing an existing installation. The
normal data scripts extract configuration from the selected registry images.
Ukrainian TTS data preparation downloads its verified model/voice assets into
`${HOME}/haru-tts-cache/ukrainian`, and skips unused GPT-SoVITS weight downloads.
The cache location can be overridden with `HARU_UK_TTS_DATA_DIR`.

Use the site's usual ROS domain, microphone/camera configuration, NVIDIA runtime,
LLM endpoint/provider credentials and robot control stack. GHCR authentication
and access to the private packages are required. Initial model downloads require
network access. The actual speech synthesis runs on the demo PC.

## Scenario and language behavior

All four localized scenarios follow the English food/movie demo: introductions,
favorite food and follow-ups, chocolate-mint ice cream, favorite movies/TV and
follow-ups, Star Wars, then goodbye and the original sleep routines. The 14-action
graph and stage criteria/timeouts are preserved (up to 21 minutes). The demo does
not automatically stop after the first answer. Custom scripted speech still needs
translation; exported builder language metadata does not switch running services.

English ASR loads the existing model; other languages load multilingual large-v3.
Spanish TTS uses `haruchild_spanish.voice` through CereVoice. Ukrainian uses local
GPU StyleTTS2 with `Анастасія Павленко` by default. Explicit rate, pause and volume
controls are supported; unsupported emotional styles retain the natural voice.

Haru uses masculine grammatical forms regardless of the selected voice. Unknown
participant gender defaults to masculine; explicitly stated gender takes
precedence. Spanish wording uses a restrained Sevillian persona; Ukrainian wording
uses a Lviv persona. This changes word choices rather than the voice's accent.
Ukrainian generated speech must use Cyrillic, including names/brands/quotations;
protocol keys, identifiers and SSML attributes remain intact. The TTS fallback
speaks `Honda` as `Хонда` and spells unknown A–Z words using Ukrainian letter names.
URLs/email addresses require an explicit spoken form.

Ukrainian playback sends headerless PCM16 with text-derived mouth shapes distributed
across voiced audio and closed-mouth cues during pauses. Every streamed phrase
re-enables lip-sync. Timing is approximate, without word/phoneme alignment.

## Validation

Run `python3 -m pytest tests`, `python3 scripts/test_multilingual.py` and
`bash scripts/validate_compose.sh`. These check language precedence, registry image
routing, localized scenario contracts and startup without source builds.

Live Spanish conversation and Ukrainian multi-turn speech/ASR were tested on Haru.
Ukrainian richer mouth animation persisted through replies, clicks were absent,
and all 19 sampled generated phrases used Cyrillic, including `Хонда`. The full
21-minute scenario and Japanese live conversation have not been completed.

Related PRs: [apps #51](https://github.com/haru-project/apps/pull/51),
[ASR #55](https://github.com/haru-project/haru-speech/pull/55),
[TTS #9](https://github.com/haru-project/strawberry-tts/pull/9),
[LLM #96](https://github.com/haru-project/haru-llm/pull/96),
[reasoner #44](https://github.com/haru-project/agent_reasoner/pull/44),
[behavior #56](https://github.com/haru-project/behavior_tree_plugins/pull/56),
[builder #2](https://github.com/haru-project/simple-haru-episode-builder/pull/2).
