# Single-speaker demo preparation

Branch: `hotfix/demo-runtime-readiness`, based on `demo/jiyugaoka_deployment`.

Robot-facing services use ROS domain 19; perception stays on domain 200.
In Haru Viz, select **All Topics**, attach domain **19**, then open **Speech**.
Viz remembers attached domains in that browser's local storage. The Conversation
panel reads the TTS playback text from the attached robot domain.

The sensor and inference images are pinned to released digests in `envs/perception.env`.
Faces uses the released image, not the unmerged performance candidate. Speech,
reasoner, LLM agents and timeline player use the deployment image tags.

Viz uses the released image pinned to digest
`sha256:90cc51728a30988a743e195e92269d21ce0a5ab497c14a4bafc7660ff53b685d`.
It contains the Conversation fix for ASR mirrored across domains. Refresh existing
Viz tabs to load the updated UI.

`haru:canonical` routes to Amazon Bedrock Mantle Gemma in `eu-central-1`.
Credentials belong in the ignored `envs/llm.secrets.env`; no credentials are
committed. The local proxy listens on port 4050.

The Kinect uses the released image pinned to digest
`sha256:ded31ee78fb4d40eaf45e98a848a62bc816570946b97c43dad298c598fc120b4`.
Its default `haru-kinect-entrypoint` starts a virtual display and delegates to
`haru-entrypoint`. No Compose entrypoint or command override is needed. It uses
no host X11 socket or Xauthority mount.
Both released containers were recreated successfully. Kinect initially entered
USB/capture recovery after recreation; a clean stop/start restored RGB and
aligned depth at 30 FPS in a 20-second probe. Viz returned HTTP 200 and loaded
without browser errors. All 24 deployment tests passed.

The prepared local speech configuration enables Zoom H8 capture, disables the
Kinect microphone and selects H8 input 6 for the single speaker. Automatic input
selection is disabled so pauses do not close the ASR input gate. The ASR model
loads successfully. Capture selections and Viz recordings use this
checkout's private data directories. Keep the H8 selected when powering it on.
Use the standalone `audio` service; the optional `audio-capture-manager` service
is for a deployment with separate workers and must remain stopped here.

The released TTS ROS client runs with remaps for `/haru2/action_tts` and
`/haru2/tts_status`. The action's five internal endpoints are remapped explicitly;
the shipped ROS runtime does not implement wildcard remapping. No TTS source
patch or custom image is required.

Verified on the preparation host: a spoken H8 test phrase produced an ASR result;
the robot played the TTS test clearly; a second TTS goal returned `SUCCEEDED` and
`played: true`, and its text appeared as **Haru** in the Conversation panel.
After refreshing Viz, the operator confirmed that a spoken phrase appeared once
with both domains attached.

Robot gaze was verified on `haru-19.local`, domain 19. Initially the look-at and
motor nodes were reachable only inside the robot container. They started before
Wi-Fi finished acquiring its address; restarting `haru_container` after operator
clearance restored remote discovery and completed motor calibration. A local
eyes-only test moved both displayed pupils and returned them to their starting
coordinates. Remote look-at commands moved the base about 2.4 degrees and the
neck about 2.3 degrees, confirmed by position feedback. The base returned near
neutral and the neck was restored to its original zero position. No new motor
errors appeared during these tests.

Restarting the demo BT forest after robot recovery loaded both controllers
without the earlier timeouts or look-at discovery errors. The controllers
default to disabled until requested, so their idle `FAILURE` status alone is not
a readiness test. The suspected robot network startup race has not been fixed
in its image. The persistent host-launcher fix is tracked in
https://github.com/haru-project/haru_setup/pull/44; cold-boot validation is pending.

The prepared local memory configuration uses provider `openai`, server URL
`http://127.0.0.1:4050` and model `haru:canonical`. Downloaded configurations live
in ignored `data/`; the provisioning script now applies the same LLM route
after copying image defaults, so downloading memory data preserves the Amazon route.

Preparation starts services with `scripts/compose.sh`; it does not run `run.sh`
or either `execute-task-*` service. The configured scenario is
`episodes/demo_food_tv.json`. It completed with action status `SUCCEEDED` and launcher exit code 0.
All 14 scenario actions reached `SUCCESS`. The operator confirmed audible
speech and Conversation messages. Empty-content parsing errors occurred during
some generated updates; successful completion does not establish an error-free
run. Those errors and identity-based gaze reacquisition remain unresolved.

After powering on the H8 and robot, verify the H8 capture channels, a real ASR
transcript, robot action servers and audible TTS. Recheck context-manager's
perception postprocessor after memory becomes available; container health alone
does not establish that all child processes are ready. Restart context-manager
if that child exited during dependency startup:

```sh
HARU_COMPOSE_AUTO_DOMAIN_BRIDGE=false bash scripts/compose.sh reasoner restart context-manager
```

Local verification artifacts and the running image inventory are stored in
`../apps/.codex-artifacts/demo-single-speaker-prep/` on the preparation host.

Demo launch uncovered an LLM request-preemption race. The local image
`haru-demo-llm:preemption-fix` applies the one-line fix from `haru-llm` branch
`hotfix/action-args-preemption`, commit `33d1c02b`; its regression test fails
against the original implementation and passes with the fix. It is not published. Its source fix is PR
https://github.com/haru-project/haru-llm/pull/95 into `demo/jiyugaoka_deployment`.
This branch keeps the deployment image tag; merge that PR and rebuild its image
before relying on the preemption fix on another host.

The robot was missing routine 8000 and other current demo routines. Missing
entries and their required assets were added from the local updated resource
library, preserving existing definitions. The original routine file is backed
up at `/home/haru/test_routines.before-demo-update.routine` on the robot. Two
unrelated routines with missing source assets (5000, 5001) were not added. The
crashed routine controller was restored with its original launch parameters;
normal robot startup will load the updated persistent resource file.

The routine assets are distributed through the existing Dropbox bundle, not a
Git repository. Provision them with the robot's standard
`haru_setup/scripts/download_resources.sh` before using the updated demo. The
robot-source protection in https://github.com/haru-project/haru2_skills/pull/16
keeps invalid service requests from killing the controller; it does not supply
missing assets. The robot image used package version 2.0.31, so rebuilding or
updating that package is required to pick up source protections.

The status-only feedback logging fix is
https://github.com/haru-project/agent_reasoner/pull/43, targeting
`demo/jiyugaoka_deployment`. The LLM PR targets the same branch. Kinect and Viz
use released images whose entrypoint and Conversation fixes are already merged
into master. Manual gaze tests used detection IDs; they are not deployment
configuration and are not persisted by this branch. Identity-based automatic
reacquisition remains a separate unimplemented improvement.
