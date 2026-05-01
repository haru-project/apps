#!/usr/bin/env python3
"""Allowlisted ROS 2 service proxy between two domain IDs.

This is intentionally an apps deployment sidecar. It keeps application nodes
single-domain while exposing a small service surface from the robot domain to
the perception/viz domain.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import signal
import threading
import time
from dataclasses import dataclass
from typing import Any

import rclpy
from rclpy.context import Context
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
import yaml


@dataclass(frozen=True)
class ServiceSpec:
    target: str
    source: str
    service_type: str
    timeout_sec: float


def _load_service_type(type_name: str) -> Any:
    parts = type_name.split("/")
    if len(parts) != 3 or parts[1] != "srv":
        raise ValueError(f"Invalid service type '{type_name}', expected pkg/srv/Name")
    module = importlib.import_module(f"{parts[0]}.srv")
    return getattr(module, parts[2])


def _load_specs(path: str) -> list[ServiceSpec]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    specs: list[ServiceSpec] = []
    for raw in data.get("services", []):
        if not isinstance(raw, dict):
            continue
        target = str(raw.get("target", "") or "").strip()
        source = str(raw.get("source", target) or "").strip()
        service_type = str(raw.get("type", "") or "").strip()
        timeout_sec = max(0.1, float(raw.get("timeout_sec", 3.0) or 3.0))
        if not target or not source or not service_type:
            raise ValueError(f"Invalid service proxy entry: {raw!r}")
        specs.append(ServiceSpec(target=target, source=source, service_type=service_type, timeout_sec=timeout_sec))
    if not specs:
        raise ValueError(f"No service proxy entries configured in {path}")
    return specs


def _fill_failure(response: Any, message: str) -> Any:
    if hasattr(response, "success"):
        response.success = False
    if hasattr(response, "message"):
        response.message = message
    return response


class DomainServiceProxy:
    def __init__(self, *, source_domain: int, target_domain: int, specs: list[ServiceSpec]) -> None:
        self.source_context = Context()
        self.target_context = Context()
        rclpy.init(context=self.source_context, domain_id=source_domain)
        rclpy.init(context=self.target_context, domain_id=target_domain)

        self.source_node = Node("haru_domain_service_proxy_source", context=self.source_context)
        self.target_node = Node("haru_domain_service_proxy", context=self.target_context)
        self.source_executor = MultiThreadedExecutor(num_threads=2, context=self.source_context)
        self.target_executor = MultiThreadedExecutor(num_threads=4, context=self.target_context)
        self.source_executor.add_node(self.source_node)
        self.target_executor.add_node(self.target_node)
        self.audit_pub = self.target_node.create_publisher(String, "/haru/domain_service_proxy/events", 10)
        self.clients: dict[str, Any] = {}
        self.services: list[Any] = []
        self._shutdown = threading.Event()

        for spec in specs:
            srv_type = _load_service_type(spec.service_type)
            self.clients[spec.target] = self.source_node.create_client(srv_type, spec.source)
            self.services.append(
                self.target_node.create_service(
                    srv_type,
                    spec.target,
                    self._make_callback(spec, srv_type),
                ),
            )
            self.target_node.get_logger().info(
                f"proxying {spec.target} ({spec.service_type}) target domain {target_domain} -> source domain {source_domain}",
            )

    def _publish_event(self, payload: dict[str, Any]) -> None:
        msg = String()
        msg.data = json.dumps(payload, sort_keys=True)
        self.audit_pub.publish(msg)

    def _make_callback(self, spec: ServiceSpec, srv_type: Any):
        def callback(request: Any, response: Any) -> Any:
            started = time.monotonic()
            client = self.clients[spec.target]
            if not client.wait_for_service(timeout_sec=spec.timeout_sec):
                message = f"source service unavailable: {spec.source}"
                self._publish_event(
                    {
                        "event": "service_unavailable",
                        "target": spec.target,
                        "source": spec.source,
                        "type": spec.service_type,
                        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
                    },
                )
                return _fill_failure(response, message)

            future = client.call_async(request)
            deadline = started + spec.timeout_sec
            while not future.done() and not self._shutdown.is_set() and time.monotonic() < deadline:
                time.sleep(0.005)
            if not future.done():
                message = f"source service timed out: {spec.source}"
                self._publish_event(
                    {
                        "event": "service_timeout",
                        "target": spec.target,
                        "source": spec.source,
                        "type": spec.service_type,
                        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
                    },
                )
                return _fill_failure(response, message)

            try:
                proxied_response = future.result()
            except Exception as exc:  # noqa: BLE001
                message = f"source service failed: {exc}"
                self._publish_event(
                    {
                        "event": "service_error",
                        "target": spec.target,
                        "source": spec.source,
                        "type": spec.service_type,
                        "error": str(exc),
                        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
                    },
                )
                return _fill_failure(response, message)

            self._publish_event(
                {
                    "event": "service_call",
                    "target": spec.target,
                    "source": spec.source,
                    "type": spec.service_type,
                    "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
                    "success": bool(getattr(proxied_response, "success", True)),
                },
            )
            return proxied_response or srv_type.Response()

        return callback

    def spin(self) -> None:
        source_thread = threading.Thread(target=self.source_executor.spin, name="source_domain_executor", daemon=True)
        source_thread.start()
        try:
            self.target_executor.spin()
        finally:
            self._shutdown.set()
            self.source_executor.shutdown()
            self.target_executor.shutdown()
            source_thread.join(timeout=2.0)
            self.source_node.destroy_node()
            self.target_node.destroy_node()
            rclpy.shutdown(context=self.source_context)
            rclpy.shutdown(context=self.target_context)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--source-domain", type=int, default=int(os.environ.get("SOURCE_DOMAIN_ID", "0")))
    parser.add_argument("--target-domain", type=int, default=int(os.environ.get("TARGET_DOMAIN_ID", "20")))
    args = parser.parse_args()

    proxy = DomainServiceProxy(
        source_domain=args.source_domain,
        target_domain=args.target_domain,
        specs=_load_specs(args.config),
    )

    def _stop(_signum, _frame) -> None:  # noqa: ANN001
        proxy.target_executor.shutdown()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    proxy.spin()


if __name__ == "__main__":
    main()
