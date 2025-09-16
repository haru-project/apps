# Haru System

This guide is intended for **non-developers** and walks you through installing, setting up, and running the Haru system.

## Pre-requisities

Before you begin, make sure you're installing the system on a machine running either Ubuntu 20.xx or 24.xx.

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
    export PAT=...
    echo $PAT | docker login ghcr.io -u AntoineBlanot --password-stdin
    ```

2. Download the Base Image

    Pull the base image used by all Haru applications:

    ```bash
    docker pull ghcr.io/haru-project/haru-os:ros2-cyclonedds
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
docker pull ghcr.io/haru-project/haru-simulator:ros2-fastdds
```

### Haru Communication App (HCA)

The Haru Communication App is Haru’s **main application**.
It’s made up of several Docker images that work together.

To install it, run:
```bash
docker pull ghcr.io/haru-project/perception-azure-kinect:ros2-fastdds
docker pull ghcr.io/haru-project/perception-faces:ros2-fastdds
docker pull ghcr.io/haru-project/perception-hands:ros2-fastdds
docker pull ghcr.io/haru-project/perception-people:ros2-fastdds
docker pull ghcr.io/haru-project/perception-visualization:ros2-fastdds
docker pull ghcr.io/haru-project/haru-speech:ros2-fastdds
docker pull ghcr.io/haru-project/haru-llm:ros2-fastdds
docker pull ghcr.io/haru-project/agent-reasoner:ros2-fastdds
```

## Run Applications

### Haru Simulator (HS)

The Haru Simulator uses a graphical interface, so you need to allow Docker to show windows on your screen. Run the following command in your terminal before starting the simulator:

```bash
xhost +local:docker
```

This gives Docker permission to display graphical applications on your desktop.
> Note: You only need to do this once per session, or each time you restart your computer.

To start the Haru Simulator, run the following command in your terminal:

```bash
docker compose -f apps/docker-compose-simulator.yaml --env-file envs/simulator.env up --force-recreate -d
```

This will launch the simulator in the **background** using the settings from `envs/simulator.env` file.

To stop the simulator and shut down all related containers, run:
```bash
docker compose -f apps/docker-compose-simulator.yaml down
```

Once the software is launched, follow these steps:

1. Set the ROS_IP
    
    Click the red button next to the text box to automatically set your **ROS_IP**.

2. Select the Scene: "Haru Virtual Avatar"

    Use the green or yellow buttons next to the scene preview to browse and select "**Haru Virtual Avatar**".

3. Start the Scene

    Click the blue "**Start**" button to begin loading the scene.

4. Open Options

    Click the orange "**Options**" button to access the settings.

5. Adjust Scene Configuration

    In the "**Scene Configuration**" tab:
    - **Disable** the "**Enable py_env**" checkbox (make sure it is unchecked).
    - **Enable** the "**Launch RVIZ**" checkbox (make sure it is checked).

6. Adjust Robot Configuration

    In the "**Haru Configuration**" tab:
    - Set "**TTS Language**" to **English**.
    - **Enable** the "**Publish Haru TFs**" checkbox.
    - (Optional) You can also:
        - Change the audio output device using the "**Haru audio device**" option.
        - Adjust the robot’s position in space via the "**Haru Base Pose**" settings.

7. Apply and Restart

    Click the grey "**Apply and Restart**" button to save changes and reload the scene.

8. Play the Scene

    Once the scene reloads, click the green "**Play**" button.

9. Confirm Scene is Active

    You should now see the **robot’s eyes and mouth appear**. Additionally, a new window named **RViz** should open.

10. Visualize Robot in RViz

    In the **RViz window**:
    - On the left side, find the "**Display**" panel and open the "**RobotModel**" section.
    - Set the "**Description Topic**" to `/robot_description`.
    
    You should now see a 3D model of the robot appear in the main view.

11. Use the Haru Web Interface

    Open your web browser and go to: http://0.0.0.0:7000/haru_web
    - Click on the "Haru control" tab.
    - From here, you can:
        - Control the robot’s **motors** manually.
        - Use **Text-To-Speech (TTS)** to make the robot speak.
        - Trigger **Routines**, which are pre-programmed movements or actions.
    
    > Note: This web interface is still experimental, so you may encounter some limitations or bugs.

### Haru Communication App (HCA)

The Haru Communication App uses a graphical interface, so you need to allow Docker to show windows on your screen. Run the following command in your terminal before starting the simulator:

```bash
xhost +local:docker
```

This gives Docker permission to display graphical applications on your desktop.
> Note: You only need to do this once per session, or each time you restart your computer.

HCA is made up of several **layers** that work together.
We recommend starting them **one at a time** so you can confirm each one runs correctly before moving on.

1. Perception layer

    Handles Haru’s vision and sensory input.

    **Start command**:
    ```bash
    docker compose -f apps/docker-compose-perception.yaml --env-file envs/perception.env up \
        azure-kinect faces hands people \  
        --force-recreate -d
    ```

    **Expected output**:
    - An RViz window appears showing:
        - Live camera feed
        - Detected skeletons and tracking markers

    **Related repositories for debug**: [strawberry-ros-people](https://github.com/haru-project/strawberry-ros-people)

2. Speech layer

    Enables Haru’s speech recognition and speech input.

    **Start command**:
    ```bash
    docker compose -f apps/docker-compose-speech.yaml --env-file envs/speech.env up \
        audio process speech-recognition speaker-verification \  
        --force-recreate -d
    ```

    **Expected output**:
    - Container logs display:
        - VAD (Voice Activity Detection) status
        - ASR (Automatic Speech Recognition) results for detected speech

    **Related repositories for debug**: [haru-speech](https://github.com/haru-project/haru-spech)

3. LLM layer

    Provides Haru’s large language model capabilities.

    **Start command**:
    ```bash
    docker compose -f apps/docker-compose-llm.yaml --env-file envs/llm.env up \
        node server webui \  
        --force-recreate -d
    ```

    **Expected output**:
    - Container logs on the `llm` service confirm:
        - LLM agents are initialized
        - Models are successfully loaded from the server
    - LLM server is running at: http://0.0.0.0:4000
    - LLM Web UI is running at: http://0.0.0.0:8080

    **Related repositories for debug**: [haru-llm](https://github.com/haru-project/haru-llm)

4. Reasoner layer

    Manages decision-making and task execution.

    **Start command**:
    ```bash
    docker compose -f apps/docker-compose-reasoner.yaml --env-file envs/reasoner.env up \
        bt-forest context-manager reasoner \  
        --force-recreate -d
    ```

    **Expected output**:
    - Multiple Groot windows open, displaying:
        - Behavior trees
        - Current execution status

    **Related repositories for debug**: [agent_reasoner](https://github.com/haru-project/agent_reasoner)

Once all layers are running, start a task with:
```bash
docker compose -f apps/docker-compose-reasoner.yaml --env-file envs/reasoner.env up \
    execute-task \  
    --force-recreate
```

In the simulator or on the real robot, Haru begins carrying out the assigned task.

To shut down **all layers and running task**, run:
```bash
docker compose -f apps/docker-compose-perception.yaml down
docker compose -f apps/docker-compose-speech.yaml down
docker compose -f apps/docker-compose-llm.yaml down
docker compose -f apps/docker-compose-reasoner.yaml down
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
    - If they are different, edit the file envs/simulator.env and replace:
        ```bash
        DISPLAY=${DISPLAY:-=:0}
        ```
        with the actual value from your host system.

2. No Sound in Robot Simulation
    
    If you can’t hear Haru in the simulation:
    - Open "**Options**" > "**Haru Configuration**" in the simulator.
    - Find the **Haru audio device** setting.
    - Try changing its value (common options are `-1`, `0`, `1`, …) until audio works.

3. LLMs Don't Connect

    If you cannot access the LLMs:
    - If you are using LLMs that need an API key, make sure to provide it in the env file.
    - Make sure you can chat with the LLMs you want to use. You can use the WebUI running at `http://0.0.0.0:8080`.
    - For each LLM agent, you can set its LLM model by setting the following env variable `{AGENT_NAME}_MODEL_ID`.

4. View Logs for More Information

    If the problem persists, checking the logs can help identify errors:
    ```bash
    docker logs <container_name>
    ```
    Replace `<container_name>` with the name of your running container.
    The logs will often include warnings or error messages you can use for troubleshooting.