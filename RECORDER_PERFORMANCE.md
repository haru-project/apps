# Recorder performance evaluation

Use `demo/jiyugaoka_deployment`, starting at `9380d9f`. Compose defaults to
`ghcr.io/haru-project/haru-recorder:latest`; pull once before measuring and retain
its digest and image revision. Keep every other service image unchanged across
comparisons. Run without a robot or simulator, people in view, or intentional
speech. Empty-room capture still exercises image encoding, audio capture, DDS,
and disk writing; it cannot establish person detection or speech inference capacity.

## Profiles and domains

Compare the recorder's built-in `default` (application domain, no perception
images) and `full_perception` (application plus compressed perception streams
and processed outputs). Keep both domains, application `0` and perception `200`,
configured throughout. The domain bridge remains the demo's normal allowlist;
do not bridge raw images. Inspect the resolved plan and actual bag inventory,
because an empty or partially covered recording is not a successful benchmark.

## Cumulative tiers

| Tier | Add to the previous tier |
|---|---|
| 0 | Empty host; then recorder idle, with workers in both domains |
| 1 | Domain bridge, live Kinect, and microphone capture |
| 2 | Skeletons, faces, and belief fusion |
| 3 | Speech recognition, verification, and localization |
| 4 | LLM infrastructure, reasoner/context manager/BT forest, TTS, timeline player, projector/iPad services supported locally |
| 5 | HaruViz with its embedded recorder disabled; no connected visualization browser |

Stop the existing Swarm and test containers first. Save names and replica counts,
stop managers that automatically restart applications, and verify no application
processes remain. Keep configuration, camera scene, audio devices, QoS, caches,
image digests, and measurement probes constant. Do not clear warmed caches between
paired windows. Do not launch robot hardware or the simulator.

For each tier: wait for healthy services and stable live sensor rates; warm up
for at least 30 seconds (longer for models); collect 60-second pilot windows with
recorder **off**, **idle**, recording **default**, and recording **full_perception**.
Stop/finalize recordings and measure finalization separately. Repeat the off
window afterward to detect drift. If the pilot works, repeat three 180-second
windows per condition, alternate profile order, and check for growing memory or
backlog. Re-discover after each tier so newly started topics enter the plan.

Measure host and container CPU/RSS, GPU utilization/VRAM, memory/IO pressure,
swap-in/out, device writes and latency, free disk, topic arrival Hz and gaps,
serialized ROS bytes/s, bag bytes/s, per-domain coverage gaps and recorded message
counts. ROS serialized throughput is payload throughput, not physical network
bandwidth; host networking makes Docker network counters unsuitable. Use device
counters or a packet trace separately when wire bandwidth is required.

Treat a reproducible 10% topic-rate reduction or 20% rise in p95 delivery gap
against the same-tier off baseline as a slowdown candidate. Use absolute gaps,
expected rates, coverage, and repeated off windows to distinguish sparse output
from dropped messages. These are screening thresholds, not a universal user
experience definition. Arrival gaps do not establish end-to-end processing latency.

## Commands

```bash
bash scripts/compose.sh recorder pull
bash scripts/compose.sh recorder up -d
# Standalone recorder: do not also launch the embedded HaruViz recorder.
HARU_VIZ_LAUNCH_RECORDER=false bash scripts/compose.sh perception up -d viz
# Optional all-in-one service:
HARU_VIZ_LAUNCH_RECORDER=false bash scripts/compose.sh all --profile recorder up -d
```

`scripts/measure_recorder.py` runs inside the recorder image with the ROS overlay
sourced. Mount this checkout read-only and a dedicated output directory writable.
For `off`, run just the observer in a temporary image container with no recorder
runtime; for the other conditions, exec it in the recorder container:

```bash
python3 /repo/scripts/measure_recorder.py --profile full_perception \
  --domains 0 200 --control-domain 0 --seconds 60 --output /evidence/tier2-full
```

The script retains graphs, resolved plans, host snapshots, topic throughput and
gaps, and the finalized recording summary. Use `vmstat`, `iostat`, `docker stats`,
and `nvidia-smi` alongside it for time series. Observer subscriptions are identical
across conditions, but add load and can activate lazy sensor encoders. Topic
discovery happens before the window: validate the saved graph for each tier.

Save dated evidence under `.codex-artifacts/`, not as deployment configuration.
On this host, stop a recording if free disk falls below 10 GiB, GPU memory is
exhausted, services fail, or swapping/IO backlog grows continuously. Preserve bags;
do not prune images or delete unrelated recordings. Stop test stacks and restore
the saved service state after evaluation.

On this machine, `container-manager.service` automatically recreates the manager
container and scales application services back up. Stop the host unit with
`sudo systemctl stop container-manager.service` before scaling Swarm replicas to
zero; stopping its Docker container alone cannot establish an empty baseline.
Restore saved replicas/containers and restart the unit after testing. The two
user-level recorder inspector services should also be stopped/restored for tier 0.
