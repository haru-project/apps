#!/usr/bin/env python3
"""Create a portable Docker config for the containerized configurator."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


REGISTRY = "ghcr.io"
REGISTRY_KEYS = (REGISTRY, f"https://{REGISTRY}", f"https://{REGISTRY}/v1/")


def _credential_from_helper(config: dict[str, Any]) -> dict[str, str] | None:
    helpers = config.get("credHelpers", {})
    helper = next((helpers.get(key) for key in REGISTRY_KEYS if helpers.get(key)), None)
    helper = helper or config.get("credsStore")
    if not helper:
        return None

    executable = shutil.which(f"docker-credential-{helper}")
    if not executable:
        return None
    for server in REGISTRY_KEYS:
        result = subprocess.run(
            [executable, "get"],
            input=f"{server}\n",
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            continue
        try:
            credential = json.loads(result.stdout)
            username = credential["Username"]
            secret = credential["Secret"]
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        encoded = base64.b64encode(f"{username}:{secret}".encode()).decode()
        return {"auth": encoded}
    return None


def portable_config(config: dict[str, Any]) -> dict[str, Any]:
    auths = config.get("auths", {})
    credential = next(
        (
            auths[key]
            for key in REGISTRY_KEYS
            if isinstance(auths.get(key), dict)
            and (auths[key].get("auth") or auths[key].get("identitytoken"))
        ),
        None,
    )
    credential = credential or _credential_from_helper(config)
    return {"auths": {REGISTRY: credential} if credential else {}}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: prepare_docker_auth.py SOURCE DESTINATION", file=sys.stderr)
        return 2
    source, destination = map(Path, sys.argv[1:])
    config: dict[str, Any] = {}
    if source.is_file():
        try:
            config = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(portable_config(config), stream)
        stream.write("\n")
    os.chmod(destination, 0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
