# Haru System

This guide is intended for **non-developers** and walks you through installing, setting up, and running the Haru system.

## Experiment start guide
1. Configure the task to use in ```envs/reasoner.env```
2. Start the main stacks
```
bash start.sh
```

3. Then go to http://localhost:5173/ and register the participants
4. Start the profiling recording 

```
bash profiling/record_session.sh session_id
```

5. Run the demo

```
bash run.sh
```

6. For subsequent runs, configure the task, register the participants, start the profiling record, and then run

```
bash restart_demo.sh
```

## Prerequisites

Before you begin, make sure you're installing the system on a machine running either Ubuntu 20.04 or 24.04.

Please note that the Haru system has not been tested on macOS or Windows, and we cannot guarantee compatibility with those platforms.

The Haru system and its applications are packaged using [Docker](https://www.docker.com/) and distributed via the GitHub Container Registry (GHCR).

Most applications require access to GPU resources, so ensure that your system has an NVIDIA GPU and the appropriate drivers installed.

1. Install Docker engine

    To install Docker on Ubuntu, follow the official guides here:
    - [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
    - [Post-installation steps for Linux](https://docs.docker.com/engine/install/linux-postinstall/)

    We strongly recommend following the official documentation, as it is regularly updated.

    If you're short on time, you can also install Docker by copying and pasting the following commands into your terminal:

    ```bash
    # Add Docker's official GPG key:
    sudo apt-get update
    sudo apt-get install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update

    # Install the Docker packages
    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Create the docker group
    sudo groupadd docker

    # Add your user to the docker group
    sudo usermod -aG docker $USER
    newgrp docker

    # Configure Docker to start on boot with systemd
    sudo systemctl enable docker.service
    sudo systemctl enable containerd.service

    # Run hello-world
    docker run hello-world
    ```

2. Install the NVIDIA Container toolkit

    To enable GPU support in Docker containers, you’ll need to install the NVIDIA Container Toolkit.
    
    Follow the official guide here:
    - [Install the NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#installing-the-nvidia-container-toolkit)

    We highly recommend using the official documentation, as it is regularly updated and includes troubleshooting steps.

    If you prefer a quicker setup, you can also run the following commands in your terminal:

    ```bash
    # Configure the production repository
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
    && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    # Update the packages list from the repository
    sudo apt-get update

    # Install the NVIDIA Container Toolkit packages
    export NVIDIA_CONTAINER_TOOLKIT_VERSION=1.17.8-1
    sudo apt-get install -y \
    nvidia-container-toolkit=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
    nvidia-container-toolkit-base=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
    libnvidia-container-tools=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
    libnvidia-container1=${NVIDIA_CONTAINER_TOOLKIT_VERSION}

    # Configure the container runtime by using the nvidia-ctk command
    sudo nvidia-ctk runtime configure --runtime=docker

    # Restart the Docker daemon
    sudo systemctl restart docker
    ```

3. Verify the installation

    ```bash
    docker ps
    ```

    You should see an empty list, indicating that no containers are currently running.

## Setup

With Docker and the NVIDIA Container Toolkit installed, you're ready to start downloading and running Haru applications.

1. Authenticate with the Private Registry

    Haru applications are hosted in a private registry on GitHub. To authorize your machine to access it, run the following in your terminal:

    ```bash
    export PAT=<your-pat>
    echo $PAT | docker login ghcr.io -u <your-github-username> --password-stdin
    ```

2. Download the Base Image

    Pull the base image used by all Haru applications:

    ```bash
    docker pull ghcr.io/haru-project/haru-os:latest
    ```

3. Confirm the Image Download

    Verify that the `haru-os` image is available locally:

    ```bash
    docker images
    ```

You should see `ghcr.io/haru-project/haru-os` listed in the output.

## Install Applications

As mentioned earlier, each Haru application is packaged as a Docker image.
To install an application, simply pull its corresponding image from the registry.

Most application images follow this format `ghcr.io/haru-project/<application-name>:<tag>`.
Where:
- `<application-name>` is the application name
- `<tag>` is the application version (e.g., latest)

### Haru Simulator (HS)

The Haru Simulator runs a **virtual Haru**.
It’s perfect for testing and development when you don’t have the physical robot.

To install the simulator, run:
```bash
docker pull ghcr.io/haru-project/hve-simulator@sha256:fb89b358b9c69ea34fedda4781d42158ef392af2ca96debb12d4344a8b81031d
```

### Haru Communication App (HCA)

The Haru Communication App is Haru’s **main application**.
It’s made up of several Docker images that work together.

To install it, run:
```bash
docker pull ghcr.io/haru-project/strawberry-ros-azure-kinect:feature-asr-improve
docker pull ghcr.io/haru-project/strawberry-ros-skeletons:feature-asr-improve
docker pull ghcr.io/haru-project/strawberry-ros-faces-module:feature-asr-improve
docker pull ghcr.io/haru-project/haru-belief:feature-asr-improve
docker pull ghcr.io/haru-project/haru-viz:feature-asr-improve
docker pull ghcr.io/haru-project/haru-domain-bridge-jazzy:latest
docker pull ghcr.io/haru-project/haru-speech-base:feature-asr-improve
docker pull ghcr.io/haru-project/haru-speech-audio:feature-asr-improve
docker pull ghcr.io/haru-project/haru-speech-recognition:feature-asr-improve
docker pull ghcr.io/haru-project/haru-speech-verification:feature-asr-improve
docker pull ghcr.io/haru-project/haru-speech-localization:feature-asr-improve
docker pull ghcr.io/haru-project/haru-llm:feature-eval-test
docker pull ghcr.io/haru-project/haru-agent-reasoner:feature-web-projector
docker pull ghcr.io/haru-project/strawberry-tts-api:latest
docker pull ghcr.io/haru-project/strawberry-tts:ros2
docker pull ghcr.io/haru-project/haru-ipad-action-server:ros2
docker pull ghcr.io/haru-project/haru-web-projector:latest
```

## Run Applications

Each application has a **download data** step (e.g., `bash scripts/download_*_data.sh`). These scripts extract default configuration files from the Docker images onto your host filesystem (into the `data/` directory). This allows you to **review and edit configuration files before launching the containers** — for example, changing microphone settings, LLM model endpoints, or ROS parameters. You should run these scripts at least once before starting each application for the first time. The Agent Memory downloader also aligns the copied Weaviate host and ports with the rendered Compose service so the mounted YAML cannot override the runtime connection settings with stale defaults.

If you want to refresh every bundle in one shot, run `bash scripts/download_all_data.sh`. That wrapper runs each download script in sequence, removes the existing `data/` tree before copying, and leaves the final permissions in the state that the downstream services expect.

The Kinect `99-k4a.rules` udev rule still needs to be installed manually; follow the Perception troubleshooting instructions (search for “udev” below) when you first set up the Azure Kinect so you only have to run `sudo` once.

We recommend using the helper script `scripts/compose.sh` for all stacks. It automatically includes the shared `apps/compose.common.yaml` file and the correct `envs/*.env`.
To quickly validate all compose files, run:
```bash
bash scripts/validate_compose.sh
```

### Perception image matrix

The default perception stack follows the branch and tag image lines used by this deployment:

```text
azure-kinect      ghcr.io/haru-project/strawberry-ros-azure-kinect:feature-asr-improve
skeletons         ghcr.io/haru-project/strawberry-ros-skeletons:feature-asr-improve
faces             ghcr.io/haru-project/strawberry-ros-faces-module:feature-asr-improve
belief            ghcr.io/haru-project/haru-belief:feature-asr-improve
viz               ghcr.io/haru-project/haru-viz:feature-asr-improve
domain-bridge     ghcr.io/haru-project/haru-domain-bridge-jazzy:latest
```

Override any service image with `*_IMAGE=...` in `envs/perception.env` or the shell environment when you need a different tested tag or an immutable digest.

`domain-bridge` uses a dedicated prebuilt image. This `apps` repository mounts `config/domain_bridge.yaml` and can validate that the published image contains the interfaces referenced by that config. The `scripts/compose.sh` helper starts the dedicated bridge project before standalone `perception` or `speech` stacks. The all-in-one stack owns its embedded bridge directly, which prevents a second Compose project from duplicating it. Image construction and branch-sensitive message overlays belong in `haru-project/haru-domain-bridge`, which publishes `ghcr.io/haru-project/haru-domain-bridge-jazzy`. Override `PERCEPTION_DOMAIN_BRIDGE_IMAGE` in `envs/domain-bridge.env` or the shell environment when testing a new bridge image tag or digest.

The `belief` and `viz` services should publish image-level healthchecks through `ros2-ci` using `healthcheck-nodes`, `healthcheck-topics`, and `healthcheck-services`. The perception compose file relies on those image healthchecks rather than maintaining repo-local overrides.

Perception model downloads are persisted outside container writable layers. Skeleton models mount at `~/haru-perception-cache/skeletons/models`; faces data, InsightFace cache, and recognition artifacts mount under `apps/data/perception` through `FACES_DATA_ROOT=/ros/strawberry_ros_faces_module`. To migrate existing local caches from older `.ros` paths without deleting the originals, run:

```bash
bash scripts/migrate_runtime_caches.sh
```

### All-in-one compose (single file)

If you want to launch all layers from a single compose file, use:
```bash
bash scripts/compose.sh all up --force-recreate -d
```

This uses `envs/all.env` for compose-time variables. Optional services still respect profiles:
```bash
bash scripts/compose.sh all --profile tts --profile webui up --force-recreate -d
```

### Isolated perception ROS domain

This branch keeps the `/perception/...` namespace in the perception ROS domain
by default. Camera, image-processing, speech, audio capture, belief, haru-viz,
and the integrated recorder use `HARU_PERCEPTION_ROS_DOMAIN_ID` (default `200`).
Robot/application services outside `/perception` continue to use
`HARU_ROBOT_ROS_DOMAIN_ID` / `ROS_DOMAIN_ID` (default `0`).

Set the robot domain once when a deployment does not use domain `0`; every
standalone robot-side stack and the bridge target will inherit it:

```bash
HARU_ROBOT_ROS_DOMAIN_ID=26 ./start.sh
```

Start the perception stack with:

```bash
bash scripts/compose.sh perception up --force-recreate -d
```

For the full belief-fusion integration path that mirrors
`perception_testing belief_fusion_isolated.launch.py`, also start the dedicated
speech stack:

```bash
bash scripts/compose.sh speech up audio recognition verification localization --force-recreate -d
```

For graph parity checks against the source launch, disable the apps domain
bridge auto-start for both commands:

```bash
HARU_COMPOSE_AUTO_DOMAIN_BRIDGE=false bash scripts/compose.sh perception up --force-recreate -d
HARU_COMPOSE_AUTO_DOMAIN_BRIDGE=false bash scripts/compose.sh speech up audio recognition verification localization --force-recreate -d
```

or the combined stack with:

```bash
bash scripts/compose.sh all up --force-recreate -d
```

The `domain-bridge` container is the only default bridge between the
perception and robot/application domains. It mirrors selected low-bandwidth
speech and belief outputs from domain `200` into the configured robot domain for
robot-domain consumers. It runs in its own compose project and is started
automatically by `scripts/compose.sh perception up`, `scripts/compose.sh speech
up`; the all-in-one stack embeds the same bridge. Docker networking is unchanged.
The Azure Kinect container mounts only USB devices by default; `/dev/snd` stays
with the speech stack so the Kinect microphone array is captured by
`haru-speech`, not by the camera driver.

`/perception/fusion/persons` is bridged directly on its canonical name using its
reliable, volatile, keep-last depth 1 contract. No robot-domain QoS adapter is
required.

The bridge allowlist is tracked in `config/domain_bridge.yaml`.
The topic bridge allowlist bridges only low-bandwidth topics:

- perception domain `200` -> robot domain `0`:
  `/perception/proc/speech/asr/status_array`,
  `/perception/proc/speech/asr/result`,
  `/perception/proc/speech/asr/result_revision`,
  `/perception/proc/speech/localization`,
  `/tf`,
  `/tf_static`,
  `/perception/fusion/persons`,
  `/perception/fusion/speech_sources`,
  `/perception/fusion/context`,
  `/perception/fusion/robot`,
  `/perception/fusion/things`,
  `/perception/fusion/things/tf`,
  `/perception/fusion/environment`, and `/strawberry/people`

It does not bridge raw Kinect, image, depth, ffmpeg, zdepth, raw audio, speech
services, belief services, or debug image topics. TF is bridged so
robot-domain `agent_reasoner` can resolve perception head frames for fusion
gazing.

Validation commands:

```bash
# Existing robot/application domain should not see raw perception image topics.
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic list | rg '/perception/sensor/camera/kinect/.*/(rgb|depth|ir)|ffmpeg|zdepth|depth_to_rgb'

# Existing domain should see only the selected low-bandwidth outputs mirrored back.
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic echo --once /perception/proc/speech/asr/status_array
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic echo --once /perception/proc/speech/asr/result
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic info /tf
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic info /tf_static
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic echo --once /perception/fusion/persons
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic echo --once /perception/fusion/environment
ROS_DOMAIN_ID=${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}} ros2 topic echo --once /strawberry/people

# Perception domain should own speech, belief, camera, and audio topics.
ROS_DOMAIN_ID=${HARU_PERCEPTION_ROS_DOMAIN_ID:-200} ros2 topic echo --once /perception/proc/speech/asr/status_array
ROS_DOMAIN_ID=${HARU_PERCEPTION_ROS_DOMAIN_ID:-200} ros2 topic echo --once /perception/proc/speech/asr/result
ROS_DOMAIN_ID=${HARU_PERCEPTION_ROS_DOMAIN_ID:-200} ros2 topic echo --once /perception/fusion/persons
ROS_DOMAIN_ID=${HARU_PERCEPTION_ROS_DOMAIN_ID:-200} ros2 topic echo --once /perception/sensor/audio/capture/state
```

The first command should produce no matches.

### Perception recording

Recording and playback are managed by the `viz` service. Use the recorder
controls in the haru-viz browser UI rather than launching a standalone
`haru-recorder` compose stack.

### Haru Simulator (HS)

The Haru Simulator uses a graphical interface, so you need to allow Docker to show windows on your screen. Run the following command in your terminal before starting the simulator:

```bash
xhost +local:docker
```

This gives Docker permission to display graphical applications on your desktop. It is required because Docker containers need access to the host's X11 display server to render GUI windows (e.g., the Unity simulator, RViz, Groot).
> Note: You only need to do this once per session, or each time you restart your computer.

**Download data**:
```bash
bash scripts/download_simulator_data.sh
```

**Start command**:
```bash
bash scripts/compose.sh simulator up --force-recreate -d
```

**Expected output**:
- A Unity Application window appears

Once the software is launched, follow these steps on the Unity Application window:

1. Set the ROS_IP
    
    Click the red button next to the text box to automatically set your **ROS_IP**.

2. Select the Scene: "Haru Virtual Avatar"

    Use the green or yellow buttons next to the scene preview to browse and select "**Haru Virtual Avatar**".

    Tick the "Set as default" box on the bottom left to set the scene selection as default.

3. Start the Scene

    Click the blue "**Start**" button to begin loading the scene.

4. Open Options

    Click the orange "**Options**" button to access the settings.

5. Adjust Scene Configuration

    In the "**Scene Configuration**" tab:
    - **Enable** the "**Autoplay scene**" checkbox (make sure it is checked).
    - **Disable** the "**Enable py_env**" checkbox (make sure it is unchecked).
    - **Enable** the "**Launch RVIZ**" checkbox (make sure it is checked).

    > Note: RViz may also be started by the perception layer. If you are running both the simulator and the perception stack, you may see two RViz windows. This is expected and will be consolidated in a future release.

6. Adjust Robot Configuration

    In the "**Haru Configuration**" tab:
    - Set "**TTS Language**" to your preferred language.
    - **Enable** the "**Publish Haru TFs**" checkbox (make sure it is checked).
    - (Optional) You can also:
        - Adjust the robot’s position in space via the "**Haru Base Pose**" settings.

7. Apply and Restart

    Click the grey "**Apply and Restart**" button to save changes and reload the scene.

8. Play the Scene

    Once the scene reloads, click the green "**Play**" button (if "**Autoplay scene**" was checked it starts automatically).

9. Confirm Scene is Active

    You should now see the **robot’s eyes and mouth appear**. Additionally, a new window named **RViz** should open.

10. Visualize Robot in RViz
    
    You should now see a 3D model of the robot appear in the RViz window.

11. Use the Haru Web Interface

    Open your web browser and go to: http://0.0.0.0:7000/haru_web
    - Click on the "Haru control" tab.
    - From here, you can:
        - Control the robot’s **motors** manually.
        - Use **Text-To-Speech (TTS)** to make the robot speak.
        - Trigger **Routines**, which are pre-programmed movements or actions.

    > Note: This web interface is still experimental, so you may encounter some limitations or bugs.

To shut down the simulator, run:
```bash
bash scripts/compose.sh simulator down
```

### Haru Communication App (HCA)

The Haru Communication App uses a graphical interface, so you need to allow Docker to show windows on your screen. Run the following command in your terminal before starting the application:

```bash
xhost +local:docker
```

This gives Docker permission to display graphical applications on your desktop. It is required because Docker containers need access to the host's X11 display server to render GUI windows (e.g., RViz, Groot).
> Note: You only need to do this once per session, or each time you restart your computer.

#### System Applications

HCA is made up of several **layers** that work together.
We recommend starting them **one at a time** so you can confirm each one runs correctly before moving on.

1. Perception layer

    Handles Haru’s vision and sensory input.

    > **Configuration note:**  
    > You can change the containers configuration in the `envs/perception.env`.

    **Start command**:
    ```bash
    bash scripts/compose.sh perception up azure-kinect skeletons faces belief viz --force-recreate -d
    ```

    **Expected output**:
    - Perception, fusion, visualization, and recording services come up on their configured perception tags
    - The haru-viz web UI is reachable at `http://127.0.0.1:5173`
    - The native bridge stays co-located with the `viz` service and continues using ports `9090`, `9091`, `9092`, and `9093`

2. Speech layer

    Enables Haru’s speech recognition and speech input.

    **Download data**:
    ```bash
    bash scripts/download_speech_data.sh
    ```

    This also provisions the ReDimNet speaker-verification model into
    `~/haru-speech-cache/models`. Keep that cache between launches: the
    verification container mounts it at `/shared/models`, so it starts without
    downloading model weights from GitHub.

    > **Configuration note:**
    > You can change the containers configuration in the `envs/speech.env`.
    > You can change the ROS nodes configuration in the `data/speech/configs/haru_speech.yaml`.

    > **Microphone selection and setup:**
    > The Zoom H8 source should be activity-gated (`detect_active_channels: true` and `process_active_channels_only: true`), and Kinect should be disabled unless you are explicitly testing its array features. Run `arecord -l` on the host to confirm the device names, then update `data/speech/configs/haru_speech.yaml` if your hardware differs.
    > If you are using a H6/H8/H12 recorder as your microphone input, make sure to set it to **Multi Track mode** on the device itself before connecting it to your computer. This ensures all input channels are available to the system.

    **Start command**:
    ```bash
    bash scripts/compose.sh speech up audio recognition verification localization --force-recreate -d
    ```

    The compose helper automatically starts the dedicated `domain-bridge` stack
    first, so speech can mirror low-bandwidth outputs back to the
    robot/application domain even when the perception stack is not running.

    **LifeCycle commands**:
    Currently, the Speech layers are started (configure + activate) automatically by setting the `dev_autostart:=true` parameter.

    **Expected output**:
    - Container logs on the `recognition` service display:
        - VAD (Voice Activity Detection) status
        - ASR (Automatic Speech Recognition) results for detected speech

    **Related repositories for debug**: [haru-speech](https://github.com/haru-project/haru-speech/tree/ros2)

3. LLM layer

    Provides Haru’s large language model capabilities.

    **Download data**:
    ```bash
    bash scripts/download_llm_data.sh
    ```

    > **Configuration note:**
    > `envs/llm.env` is the non-secret source of truth for config.
    > Secrets (API keys, tokens) live in `envs/llm.secrets.env` (untracked).
    > The canonical LiteLLM mapping is tracked in `config/llm/litellm_server.yaml`
    > and mounted read-only.
    > You can change the ROS nodes configuration in `data/llm/configs/haru_llm.yaml`.
    > You can change agent configs (prompts, settings) in `data/llm/agents/`.

    > **Canonical Bedrock Mantle model:**
    > All agents use the stable `haru:canonical` alias. By default it maps to
    > Gemma 4 26B on Bedrock Mantle in the region selected by
    > `BEDROCK_MANTLE_REGION`.
    >
    > 1. Copy `envs/llm.secrets.env.example` to `envs/llm.secrets.env`.
    > 2. Set `BEDROCK_MANTLE_API_KEY`.
    >
    > The configurator can generate an alternate local mapping for OpenAI,
    > Anthropic, or a custom OpenAI-compatible endpoint without changing agent
    > model identifiers.
    >
    > **Using local/self-hosted models:**
    > Add or generate a local LiteLLM mapping that preserves the
    > `haru:canonical` alias:
    > ```yaml
    > - model_name: haru:canonical
    >   litellm_params:
    >     model: <provider>/<model-name>
    >     api_base: http://<server-host>:<server-port>/v1
    >     api_key: "dummy-key"

    > ```
    > For a full list of supported providers and configuration options, see the [LiteLLM Providers documentation](https://docs.litellm.ai/docs/providers).

    **Start command**:
    ```bash
    bash scripts/compose.sh llm up action-args --force-recreate -d
    ```

    **Optional profiles**:
    - Dashboard:
      ```bash
      bash scripts/compose.sh llm --profile dashboard up dashboard --force-recreate -d
      ```
    - Web UI:
      ```bash
      bash scripts/compose.sh llm --profile webui up webui --force-recreate -d
      ```
    - vLLM:
      ```bash
      bash scripts/compose.sh llm --profile vllm up vllm --force-recreate -d
      ```

    **LifeCycle commands**:
    Currently, the LLM layers are started (configure + activate) automatically by setting the `dev_autostart:=true` parameter.

    **Expected output**:
    - Container logs on the `action-args` service confirm:
        - LLM agents are initialized
        - Models are successfully loaded from the server
    - LLM Dashboard is running at http://127.0.0.1:8501 only when its profile is started
    - LLM server is running at: http://127.0.0.1:4050
    - LLM Web UI is running at: http://127.0.0.1:8080 (only if the `webui` profile is started)

    **Related repositories for debug**: [haru-llm](https://github.com/haru-project/haru-llm/tree/feature-improve-goal-verif)

4. Reasoner layer

    Manages decision-making and task execution.

    **Download data**:
    ```bash
    bash scripts/download_reasoner_data.sh
    ```

    > **Configuration note:**
    > You can change the containers configuration in the `envs/reasoner.env`.

    > **Microphone and iPad mapping (important for multi-mic setups):**
    > Edit `data/reasoner/configs/params/postprocessors_params.yaml` to match your physical setup.
    > - `mic_id_to_position` — set the position (in meters) of each microphone relative to the robot's position
    > - `ipad_id_to_mic_id` — map each iPad device ID to a microphone channel ID (enables dynamic naming from iPads)
    > - `mic_id_to_person_name` — map each microphone channel ID to a default person name (used as fallback)
    >
    > When iPads are connected and participants set their names on the iPad app, the system automatically
    > uses those names instead of the static `mic_id_to_person_name` values. The mapping flows through
    > the `ipad_id_to_mic_id` configuration: each iPad ID is linked to a mic channel, and the name set
    > on the iPad is used for that channel's participant.
    >
    > Example (x = front/back, y = left/right, z = up/down):
    > ```yaml
    > mic_id_to_position: [
    >   '0: {x: 1.0, y: 0.0, z: 0.0}',      # 1m in front of robot
    >   '1: {x: 0.0, y: -1.0, z: 0.0}',     # 1m to the right
    >   '2: {x: 0.0, y: 1.0, z: 0.0}',      # 1m to the left
    >   '3: {x: -1.0, y: 0.0, z: 0.0}',     # 1m behind
    >   '4: {x: , y: , z: }'                # unused channel (ignored)
    > ]
    > ipad_id_to_mic_id: [
    >   '1: 0',                             # iPad 1 linked to mic channel 0
    >   '2: 1',                             # iPad 2 linked to mic channel 1
    >   '3: 2',                             # iPad 3 linked to mic channel 2
    > ]
    > mic_id_to_person_name: [
    >   '0: {name: alice}',                 # channel 0 assigned to alice
    >   '1: {name: bob}',                   # channel 1 assigned to bob
    >   '2: {name: charlie}',               # channel 2 assigned to charlie
    >   '3: {name: dana}',                  # channel 3 assigned to dana
    >   '4: {name: }'                       # unused channel (ignored)
    > ]
    > ```

    **Start command**:
    ```bash
    bash scripts/compose.sh reasoner up bt-forest --force-recreate -d
    ```

    **LifeCycle commands**:
    Currently, the Reasoner layers are started (configure + activate) automatically by setting the `dev_autostart:=true` parameter.

    **Expected output**:
    - Multiple Groot windows should open (one per behavior tree controller):
        - **Expressivity controller** — manages TTS/Routine-driven expressions
        - **Gaze controller** — manages gaze behavior
        - **iPad students controller** — manages requests/responses to the students iPad
        - **iPad teacher controller** — manages requests/responses to the teacher iPad
        - **Unity controller** — manages the projection of photos/videos to the Unity Projector
    - Both windows display the behavior tree and its current execution status

    > **Note:** The behavior tree controllers depend on action servers that run by different services (robot, iPad, projector, ...). If services are not running, some controllers may fail to load (timeout after ~10s) and fewer Groot windows will appear than expected. Make sure the services you wish to use are running before starting the reasoner.

    **Related repositories for debug**: [agent_reasoner](https://github.com/haru-project/agent_reasoner/tree/jazzy)

5. Expressive TTS layer (optional)

    Enhances Haru with a more expressive and natural-sounding voice

   **Download data**:
    ```bash
    bash scripts/download_tts_data.sh
    ```

    **Start command**:
    ```bash
    bash scripts/compose.sh tts --profile tts up gpt-sovits cerevoice-api tts-client --force-recreate -d
    ```

    **Required ROS bridge for expressive scenarios**:
    ```bash
    bash scripts/compose.sh tts --profile tts --profile ros up ros-node --force-recreate -d
    ```

    > The bridge provides `/strawberry/retrieve_tts_generation`. Without it,
    > expressive audio may be generated but cannot be retrieved by the reasoner.
    > Keep this container healthy before starting an expressive scenario.
    >

    > **Configuration note:**  
    > You can change the containers configuration in the `envs/tts.env`.

    **Expected output**:
    - GPT Sovits API is running at: http://127.0.0.1:9880
    - Cerevoice API is running at: http://127.0.0.1:8015
    - TTS API is running at: http://127.0.0.1:8022

    **Related repositories for debug**: [strawberry-tts](https://github.com/haru-project/strawberry-tts/tree/ros2)

6. iPad layer (optional)

    Provides an action server for controlling iPads connected to Haru. The iPads can be used as displays for students and teachers during interaction scenarios.

    > **Prerequisites:**
    > You must have the teacher and student iPad apps installed via TestFlight (provided by 4i). Make sure the iPads are connected to the same network as the host machine.

    > **Configuration note:**
    > You can change the containers configuration in the `envs/ipad.env`.
    > The `NUM_IPADS` variable controls how many student iPads the action server expects. Set this to the number of iPads running the student application that you have connected to the network. The teacher application wrapper is started automatically — no additional configuration is needed for it.

    > **iPad app settings:**
    > On each iPad, open **Settings** and find the **Encouraging Mediator** app entries (both teacher and student apps). Configure the following:
    > - **ROS IP** — set to the IP address of this machine (the one running the HCA stack)
    > - **Port** — set to `9091` (default)
    >
    > When the connection is successful, the connection icon in the app turns **green** and you should see connection logs appear in the console.

    **Start command**:
    ```bash
    bash scripts/compose.sh ipad up server --force-recreate -d
    ```

    **Expected output**:
    - Container logs on the `server` service confirm:
        - iPad action server is initialized
        - Connected to iPads

7. Projector layer (optional)

    Enables a web-based projector display, allowing Haru to project images and videos onto a surface during interactions.

    Projector resources are downloaded as part of the reasoner data and mounted into the projector service.

    > **Configuration note:**
    > You can change the containers configuration in the `envs/projector.env`.
    > Projector resources are managed through the behavior tree system. You can update or replace the resources in `data/reasoner/projector/` to change what content is available for projection.

    **Start command**:
    ```bash
    bash scripts/compose.sh projector up server --force-recreate -d
    ```

    **Expected output**:
    - Projector web server is running at: http://127.0.0.1:8081

#### User Application

The User Application provides the **Episode Builder**, a web interface for creating and managing task episodes.

> **Configuration note:**
> You can change the containers configuration in the `envs/user.env`.

**Start command**:
```bash
bash scripts/compose.sh user up episode-builder --force-recreate -d
```

**Expected output**:
- Episode Builder web UI is running at: http://127.0.0.1:8551

**Related repositories for debug**: [simple-haru-episode-builder](https://github.com/haru-project/simple-haru-episode-builder)

Once all layers are running, start a test task with:
```bash
bash scripts/compose.sh reasoner up reasoner context-manager execute-task-test
```

Once all layers are running, start a scenario task with:
```bash
bash scripts/compose.sh reasoner up reasoner context-manager execute-task-scenario
```

In the simulator or on the real robot, Haru begins carrying out the assigned task.

To shut down **all layers and running task**, run:
```bash
bash scripts/compose.sh perception down
bash scripts/compose.sh speech down
bash scripts/compose.sh llm down
bash scripts/compose.sh reasoner down
bash scripts/compose.sh tts down
bash scripts/compose.sh ipad down
bash scripts/compose.sh projector down
bash scripts/compose.sh user down
```

## Troubleshooting Tips:

Sometimes, you may need to adjust your settings if things don’t work as expected. Here are a couple of common issues and how to fix them:

1. Unity Application Won’t Start
    
    If the Unity interface fails to open:
    - In **both** your host system and the Haru Simulator container, run:
        ```bash
        env | grep DISPLAY
        ```
    - Compare the values. They must be identical.
    - If they are different, edit the file `envs/simulator.env` and replace:
        ```bash
        DISPLAY=${DISPLAY:-=:0}
        ```
        with the actual value from your host system.

2. No Sound in Simulation
    
    If you can’t hear the sound of clicks or the robot in the simulation:
    - Run `aplay -l` on your host machine to see the available audio devices.
    - Set the `AUDIO_CARD` environment variable in the `envs/simulator.env` file to the device name or ID (e.g., `1`, `2`, ...).

3. LLMs Don't Connect

    If you cannot access the LLMs:
    - If you are using LLMs that need an API key, make sure to provide it in the env file.
    - Make sure you can chat with the LLMs you want to use. You can use the WebUI running at `http://0.0.0.0:8080`.
    - For each LLM agent, you can set its LLM model by setting the following env variable `{AGENT_NAME}_MODEL_ID`.

4. Face is Not Recognized

    If your face is not being recognized by the system:
    - Set the following environment variables in the `envs/perception.env` file:
        ```bash
        LEARNING_PERSON_NAME=<your-name>    # the face will be registered as this name
        LEARNING_PERSON_ID=<your-id>        # the person id to register (visible from RVIZ)
        ```
    - Run the face registration process:
        ```bash
        bash scripts/compose.sh perception up register-face --force-recreate
        ```
    - The system will begin collecting frames of your face for training.
    - Once training is complete (typically takes about 5 minutes), your face should be recognized correctly.

5. View Logs for More Information

    If the problem persists, checking the logs can help identify errors:
    ```bash
    docker logs -f <container_name>
    ```
    Replace `<container_name>` with the name of your running container (you check running containers with `docker ps`).
    The logs will often include warnings or error messages you can use for troubleshooting.
