# Standalone recording integration

Based on the current experiment/icra_hri_2027 demo domain wiring. The recorder is
an optional service, not started by every demo launch. Start the normal perception
and speech stacks using scripts/compose.sh; their existing domain bridge forwards
only config/domain_bridge.yaml's allowlist into the default/robot domain. Do not
start a second bridge for the same routes.

Start recording services (this does not start capture):

```sh
HARU_ROBOT_ROS_DOMAIN_ID=0 HARU_PERCEPTION_ROS_DOMAIN_ID=200 scripts/compose.sh recorder up -d
```

The coordinator defaults to the perception domain, matching HaruViz. Recording
Default domain captures the configured robot/default domain; Full perception adds
the perception domain, keeping the default domain even while quiet. Camera/raw
audio must not be added to the default-domain bridge to make previews work.

Use the haru-domain-bridge feature/standalone-recording build for live routing
contracts. Recorder uses the advertised publisher GIDs to suppress bridge copies,
not a guessed namespace or topic-name duplicate rule. The matching HaruViz branch
supplies the footer client. All feature images must be built and verified before
use: the default recorder feature tag is a candidate, not a published release.
Pin approved image digests for a real deployment.

Set HARU_RECORDER_IMAGE to the tested recorder image and
HARU_RECORDER_HOST_RECORDINGS_DIR to the host storage directory. The image bundles
its message dependencies and does not require HaruViz. Cloud inputs may be passed
through a private Compose env_file override on the recorder service; retain all
HARU_RECORDER_S3_*, AWS_*, and HARU_RECORDER_DROPBOX_* settings needed by the chosen
provider without adding secrets to this repository. S3 qualification requires
credentials; missing cloud credentials must not prevent local recording.

Live integration evidence and linked draft PRs are maintained in haru-recorder's
release qualification notes. Do not treat a feature image or local test pass as
approval for a robot/school rollout.
