FROM ghcr.io/haru-project/haru-agent-reasoner@sha256:22b6584e21cee4366614d30ab369b5e710cc720e0ce602a9ca69327d6bee3cc9 AS build
USER root
RUN apt-get update && apt-get install -y --no-install-recommends g++ make python3-colcon-common-extensions libboost-system-dev libboost-filesystem-dev && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace && ln -s /opt/ros/jazzy/workspace/install /workspace/install
COPY reasoner/haru_agent_reasoner /feature_ws/src/haru_agent_reasoner
COPY behavior /feature_ws/src/behavior
ENV CMAKE_BUILD_PARALLEL_LEVEL=2
SHELL ["/bin/bash", "-c"]
RUN source /opt/ros/jazzy/setup.bash && source /opt/ros/jazzy/workspace/install/setup.bash && \
    cd /feature_ws && colcon build --merge-install --packages-select behavior_tree_haru behavior_tree_strawberry haru_agent_reasoner --executor sequential --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS=-O1 --no-warn-unused-cli
FROM ghcr.io/haru-project/haru-agent-reasoner@sha256:22b6584e21cee4366614d30ab369b5e710cc720e0ce602a9ca69327d6bee3cc9
COPY --from=build /feature_ws/install /opt/ros/jazzy/workspace/install
