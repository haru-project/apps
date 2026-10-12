# Single-speaker demo preparation

Branch: `feature/demo-single-speaker-ready`, based on `demo/jiyugaoka_deployment`.

Robot-facing services use ROS domain 19; perception stays on domain 200.
In Haru Viz, select **All Topics**, attach domain **19**, then open **Speech**.
Viz remembers attached domains in that browser's local storage. The Conversation
panel reads the TTS playback text from the attached robot domain.

The sensor and inference images are pinned to released digests in `envs/perception.env`.
Faces uses the released image, not the unmerged performance candidate. Speech,
reasoner, LLM agents and timeline player use the deployment image tags.

Viz currently uses the locally built `haru-demo-viz:conversation-dedup` image,
based on the released Viz digest with the UI from `haru-viz` commit `9373d24`
(`hotfix/conversation-mirrored-asr`). It displays ASR mirrored from domain 200
into 19 once while retaining robot replies. Refresh existing Viz tabs to load
the updated UI. This hotfix is not yet published; another host must build it
before using this deployment's local image reference.

`haru:canonical` routes to Amazon Bedrock Mantle Gemma in `eu-central-1`.
Credentials belong in the ignored `envs/llm.secrets.env`; no credentials are
committed. The local proxy listens on port 4050.

The Kinect uses its shipped `haru-kinect-entrypoint`, which starts a virtual
display. It needs no host X11 socket or Xauthority mount. Its ROS command is
explicit because overriding an entrypoint clears the image's default command.

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
in its image and may recur after a reboot.

The prepared local memory configuration uses provider `openai`, server URL
`http://127.0.0.1:4050` and model `haru:canonical`. Downloaded configurations live
in ignored `data/`; downloading them again resets local adjustments. Keep the
Amazon route when reprovisioning memory.

Preparation starts services with `scripts/compose.sh`; it does not run `run.sh`
or either `execute-task-*` service. The configured scenario is
`episodes/demo_food_tv.json` and has not been launched.

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
