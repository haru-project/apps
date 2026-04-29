ARG BASE_IMAGE=ghcr.io/haru-project/haru-belief:feature-topic-normalize
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends "ros-${ROS_DISTRO:-jazzy}-domain-bridge" && \
    rm -rf /var/lib/apt/lists/*
