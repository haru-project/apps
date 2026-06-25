#!/usr/bin/env python3
"""Validate rendered compose ROS domain wiring."""

from __future__ import annotations

import json
import sys
from typing import Any


PERCEPTION_SERVICES = {"azure-kinect", "skeletons", "faces", "belief", "viz"}
SPEECH_SERVICES = {"audio", "audio-capture-manager", "recognition", "verification", "localization"}


def _service_env(service: dict[str, Any]) -> dict[str, str]:
    raw_env = service.get("environment") or {}
    if isinstance(raw_env, dict):
        return {str(key): str(value) for key, value in raw_env.items() if value is not None}
    if isinstance(raw_env, list):
        env: dict[str, str] = {}
        for item in raw_env:
            key, _, value = str(item).partition("=")
            if key:
                env[key] = value
        return env
    return {}


def _check_perception_domain(service_name: str, env: dict[str, str], errors: list[str]) -> None:
    ros_domain = env.get("ROS_DOMAIN_ID")
    perception_domain = env.get("HARU_PERCEPTION_ROS_DOMAIN_ID")
    if ros_domain and perception_domain and ros_domain != perception_domain:
        errors.append(
            f"{service_name}: ROS_DOMAIN_ID={ros_domain} but "
            f"HARU_PERCEPTION_ROS_DOMAIN_ID={perception_domain}",
        )
    vite_domain = env.get("VITE_ROS_DOMAIN_ID")
    if service_name == "viz" and vite_domain and perception_domain and vite_domain != perception_domain:
        errors.append(
            f"{service_name}: VITE_ROS_DOMAIN_ID={vite_domain} but "
            f"HARU_PERCEPTION_ROS_DOMAIN_ID={perception_domain}",
        )


def _check_domain_bridge(env: dict[str, str], errors: list[str]) -> None:
    from_domain = env.get("FROM_DOMAIN_ID")
    to_domain = env.get("TO_DOMAIN_ID")
    ros_domain = env.get("ROS_DOMAIN_ID")
    perception_domain = env.get("HARU_PERCEPTION_ROS_DOMAIN_ID")
    robot_domain = env.get("HARU_ROBOT_ROS_DOMAIN_ID")
    if from_domain and perception_domain and from_domain != perception_domain:
        errors.append(
            f"domain-bridge: FROM_DOMAIN_ID={from_domain} but "
            f"HARU_PERCEPTION_ROS_DOMAIN_ID={perception_domain}",
        )
    if to_domain and robot_domain and to_domain != robot_domain:
        errors.append(
            f"domain-bridge: TO_DOMAIN_ID={to_domain} but HARU_ROBOT_ROS_DOMAIN_ID={robot_domain}",
        )
    if ros_domain and to_domain and ros_domain != to_domain:
        errors.append(f"domain-bridge: ROS_DOMAIN_ID={ros_domain} but TO_DOMAIN_ID={to_domain}")


def main() -> int:
    data = json.load(sys.stdin)
    services = data.get("services") or {}
    errors: list[str] = []

    for service_name, service in services.items():
        env = _service_env(service)
        if service_name in PERCEPTION_SERVICES or service_name in SPEECH_SERVICES:
            _check_perception_domain(service_name, env, errors)
        if service_name == "domain-bridge":
            _check_domain_bridge(env, errors)

    if errors:
        print("ROS domain wiring mismatch in rendered compose config:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
