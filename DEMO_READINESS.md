# Single-speaker demo preparation

Branch: `feature/demo-single-speaker-ready`, based on `demo/jiyugaoka_deployment`.

The perception images are pinned to released digests in `envs/perception.env`.
Faces uses the released image, not the unmerged performance candidate. Speech,
reasoner, LLM agents and timeline player use the deployment image tags.

`haru:canonical` routes to Amazon Bedrock Mantle Gemma in `eu-central-1`.
Credentials belong in the ignored `envs/llm.secrets.env`; no credentials are
committed. The local proxy listens on port 4050.

The Kinect uses its shipped `haru-kinect-entrypoint`, which starts a virtual
display. It needs no host X11 socket or Xauthority mount. Its ROS command is
explicit because overriding an entrypoint clears the image's default command.

The prepared local speech configuration enables Zoom H8 capture, disables the
Kinect microphone, excludes H8 channels 10/11 and detects active input channels.
The ASR model loads successfully. Capture selections and Viz recordings use this
checkout's private data directories. Keep the H8 selected when powering it on.

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
