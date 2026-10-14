# Multilingual integration

Supported settings: `en-US` (default), `es-ES`, `ja-JP`, `uk-UA`, or short `en`,
`es`, `ja`, `uk`. Set one startup locale across services; changing it requires a
service restart to load the correct ASR/TTS model. No develop merges are included.

| Repository | Feature branch | Change |
| --- | --- | --- |
| apps | [feature/multilingual](https://github.com/haru-project/apps/pull/51) | Shared Compose setting, Ukrainian overlay, image overrides |
| haru-speech | [feature/multilingual](https://github.com/haru-project/haru-speech/pull/55) | Existing English model; large-v3 for other locales |
| strawberry-tts | [feature/multilingual](https://github.com/haru-project/strawberry-tts/pull/9) | Locale fallback and local Ukrainian StyleTTS2 |
| haru-llm | [feature/multilingual](https://github.com/haru-project/haru-llm/pull/96) | Native-language prompt policy, Ukrainian speech metadata, NLP fallback |
| agent_reasoner | [feature/multilingual](https://github.com/haru-project/agent_reasoner/pull/44) | Startup parameter and dialog blackboard language |
| behavior_tree_plugins | [feature/multilingual](https://github.com/haru-project/behavior_tree_plugins/pull/56) | Empty request ports inherit environment; explicit languages preserved |
| simple-haru-episode-builder | [feature/multilingual](https://github.com/haru-project/simple-haru-episode-builder/pull/2) | Sidebar selector, language-aware exports, four localized templates |

The bases match the images configured in `/home/levko/demo_ws/src/apps-demo-prep`:
apps starts from `hotfix/demo-runtime-readiness` (`29a9d38`), LLM from
`hotfix/action-args-preemption`, reasoner from `hotfix/demo-empty-content-feedback`,
speech and builder from `master`, and behavior plugins from `hotfix/demo-issues`
(`c2229f55`, the revision pinned by the reasoner image).

TTS uses the `hotfix/demo-issues` source embedded in the deployed image
(`e1218736`). The base branch was restored on origin with `install/.secrets` excluded from
its entire history; all other baseline files match the deployed checkout.
The reasoner dependency manifests select `feature/multilingual` behavior plugins.

## One setting, one startup command

In this `apps` branch, edit `envs/demo.env`:

```dotenv
HARU_DEMO_LANGUAGE=es-ES
```

Then run `./start.sh`. It builds the pinned feature images if needed, initializes
missing language-service data without replacing existing hardware settings or
saved tasks, starts the usual demo pipeline and builder, and submits
`config/demo/MultilingualDemo_es-ES.json` automatically. `en-US` is the default;
`es-ES`, `ja-JP`, `uk-UA` and short ISO aliases are supported. All stack wrappers
read this same file. A shell `HARU_DEMO_LANGUAGE` override or wrapper `--language`
argument takes precedence. There are no per-stack language files to edit.

Before switching a running demo, run `./stop.sh`, change the setting, then run
`./start.sh` again. ASR/TTS models are startup settings, not live switches.
`./run.sh` submits the matching scenario again without rebuilding the pipeline.

This assumes the existing demo hardware, data bundles and provider credentials
are configured and Haru's control stack is running on the normal ROS domain.
Setup preserves `envs/llm.secrets.env`, creates a matching private proxy/client
key pair if needed, and uses its existing `BEDROCK_MANTLE_API_KEY`. A fresh
hardware deployment still needs the ordinary perception/memory data setup in
README. First use requires GitHub access for pinned sources and model downloads;
subsequent builds reuse cached sources, layers and model assets.

`./scripts/setup_multilingual.sh` prepares the language services without starting
robot actions. `./scripts/build_multilingual.sh` builds only the feature images.
Sources are locked in `docker/multilingual/sources.env`; the reasoner image includes
the matching behavior plugins. Default Compose images now select these local
builds, so manual image overrides are unnecessary. Existing image overrides remain
available for deployment tooling. English/Spanish/Japanese use Strawberry;
Ukrainian automatically selects local GPU StyleTTS2 and provisions its assets.

Generated speech uses the configured locale. Automatic per-word TTS language
switching is disabled for this demo, and unsupported voice genres retain the same
language's default voice. The ASR uses the current distilled English model or
larger multilingual large-v3 for the other locales.

The builder defaults its sidebar to the same setting and attaches native language
instructions through the existing `HARU_CONVERSATE` goal field. Exported
`demo_language` metadata does not switch running models. The four checked-in demo
scenarios are localized; existing custom literal scripts still need translation.

## Repositories requiring no source changes

- NLP server already detects arbitrary languages. Its emotion endpoints cover
  English/Spanish/German only: Japanese/Ukrainian now use LLM TTS tagging instead.
- Core PCM playback, skills, iPad forwarding and web projection pass audio/text
  or request language through without an English-only routing default.
- VAD and the local Smart Turn audio model take waveforms, not a configured text
  language. No routing changes are needed; turn-taking accuracy for each language
  still needs native-speaker evaluation.

## Validation and limits

- Single-file language propagation, aliases/defaults/precedence and matching
  scenario selection checked for English, Spanish, Japanese and Ukrainian.
- Startup tested with command stubs to check locale consistency and automatic
  backend dependencies; Compose validates for physical and simulator profiles.
- Feature images built from pinned sources. Spanish ASR and LLM activate with
  `es-ES`; the configured LLM provider generated a Spanish greeting.
- Spanish TTS generated PCM audio through the local GPU backend with the selected
  Spanish checkpoints. A large-v3 round trip recognized Spanish but had word
  errors, so native listening review is still required.
- Builder HTTP health passed with the Spanish setting; proxy key setup is checked
  for preservation of provider credentials, idempotence and private permissions.
- Earlier LLM/regression and reasoner tests still apply. The legacy LLM NLP test
  file's 12 failures are present on the unchanged base; it is excluded there.

With the rebuilt feature images and the working English deployment's microphone
and provider configuration, independent Spanish component checks passed: H8 input 6
produced a Spanish transcript, the LLM returned a Spanish reply, and Haru completed
playback of a generated greeting that the listener confirmed was clear Spanish.
ASR misheard "Haru" as "Jaro" and "dibujar" as "llorar" in the test phrase.
A subsequent live Spanish scenario passed one complete dialog round trip: the
listener heard the greeting/question, ASR captured "Me gusta escuchar música."
exactly on H8 input 6, context attributed it to Levko, and the listener heard the
Spanish reply and thank-you. This used the English deployment's microphone,
provider, agent and postprocessor settings with the feature images.

Replay limitation: resetting conversation history alone can leave the scheduler's
cached content indices for the same task/action IDs. For the video replay, restarting
`action-args` and `reasoner` as well as resetting conversation produced a fresh
successful greeting/question. Longer conversations, automatic completion,
native pronunciation review and per-language turn-taking calibration remain unverified. Ukrainian delivery,
number inflection and mouth timing retain the TTS feature's documented limits.

## TTS timing and mouth cues

The GPT-SoVITS call previously swapped positional sampling arguments: `top_k=5`
was passed as `temperature=5`. Synthesis now passes these arguments by name in
both normal and fallback paths. Non-English mouth cues now retain valid complete
phoneme tokens and deterministic nested structure, rather than splitting randomly
selected tokens into unsupported characters. These are approximate mouth cues,
not language-specific forced phoneme alignment.

A paired local Spanish check of three short phrases measured median generation
latency of 1.82s before and 1.04s after, and median audio duration of 9.37s before
and 3.51s after. All three updated responses contained valid mouth cue names.
These are small-sample warm-backend measurements; whole-dialog latency includes
ASR, LLM tagging and playback scheduling. Physical LED behavior still needs a
visual robot check.

## Spanish CereVoice default

Selecting `HARU_DEMO_LANGUAGE=es-ES` now loads `haruchild_spanish.voice`
(`HaruSpanish`, 24 kHz) and its matching license in the local PC CereVoice
server. Spanish utterances use CereVoice directly, bypassing Nacho generation
and neural MOS retries. Audio is resampled to the existing 32 kHz playback
format, with the same genre tags, prerecorded gestures, and approximate mouth
cues. The earlier live Spanish results above used Nacho.

The voice and license are already included in the pinned base TTS image.
GPT-SoVITS still starts with the shared service stack; it remains available
for other languages. The CereVoice server loads one voice at startup, so its
supported fallback language is derived from the selected demo language.

An offline PC check loaded `HaruSpanish` and generated three phrases in
0.35–0.69 seconds (2.8–5.4 seconds of speech). Robot playback and visual mouth
synchronization have not yet been checked with this voice.
