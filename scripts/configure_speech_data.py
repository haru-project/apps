#!/usr/bin/env python3
"""Apply the demo microphone policy to a downloaded haru-speech config."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT_SECTION_RE = re.compile(r"^/\*\*/(?P<name>[^:]+):\s*(?:#.*)?$")
SOURCE_RE = re.compile(
    r"^(?P<indent>\s*)-\s+source_id\s*:\s*(?P<value>[^#\s]+|[\"'][^\"']*[\"'])"
)


def section_bounds(lines: list[str], name: str) -> tuple[int, int]:
    starts = [
        index
        for index, line in enumerate(lines)
        if (match := ROOT_SECTION_RE.match(line.rstrip("\r\n")))
        and match.group("name") == name
    ]
    if len(starts) != 1:
        raise SystemExit(
            f"Speech config must contain exactly one '/**/{name}' section; "
            f"found {len(starts)}"
        )

    start = starts[0]
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if ROOT_SECTION_RE.match(lines[index].rstrip("\r\n"))
        ),
        len(lines),
    )
    return start, end


def source_bounds(
    lines: list[str], section: tuple[int, int], source_id: str
) -> tuple[int, int]:
    section_start, section_end = section
    sources: list[tuple[int, int, str]] = []
    for index in range(section_start + 1, section_end):
        match = SOURCE_RE.match(lines[index].rstrip("\r\n"))
        if match:
            sources.append(
                (index, len(match.group("indent")), match.group("value").strip("\"'"))
            )

    matches = [source for source in sources if source[2] == source_id]
    if len(matches) != 1:
        raise SystemExit(
            f"Speech config must contain exactly one source_id {source_id!r}; "
            f"found {len(matches)}"
        )

    start, indent, _ = matches[0]
    end = next(
        (
            index
            for index, candidate_indent, _ in sources
            if index > start and candidate_indent == indent
        ),
        section_end,
    )
    return start, end


def set_key(
    lines: list[str], bounds: tuple[int, int], key: str, value: str, context: str
) -> None:
    key_re = re.compile(
        rf"^(?P<prefix>\s*(?:-\s+)?{re.escape(key)}\s*:\s*)"
        r"(?P<value>[^#\r\n]*?)(?P<comment>[ \t]+#.*)?(?P<newline>\r?\n)?$"
    )
    matches: list[tuple[int, re.Match[str]]] = []
    for index in range(*bounds):
        if match := key_re.match(lines[index]):
            matches.append((index, match))

    if len(matches) != 1:
        raise SystemExit(
            f"Speech config must contain exactly one {key!r} setting in {context}; "
            f"found {len(matches)}"
        )

    index, match = matches[0]
    lines[index] = (
        f"{match.group('prefix')}{value}{match.group('comment') or ''}"
        f"{match.group('newline') or ''}"
    )


def configure(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    speech_stack = section_bounds(lines, "speech_stack")

    zoom_h8 = source_bounds(lines, speech_stack, "mic_0")
    for key, value in (
        ("detect_active_channels", "true"),
        ("process_active_channels_only", "true"),
        ("dynamic_capture_controlled", "true"),
        ("active_channel_rms_threshold", "0.003"),
        ("active_channel_warmup_secs", "2.0"),
        ("exclude_channels", "[10, 11]"),
    ):
        set_key(lines, zoom_h8, key, value, "speech_stack source mic_0")

    kinect = source_bounds(lines, speech_stack, "mic_1")
    for key, value in (
        ("enabled", "false"),
        ("capture_enabled", "false"),
        ("speech_enabled", "false"),
        ("localization_enabled", "false"),
    ):
        set_key(lines, kinect, key, value, "speech_stack source mic_1")

    audio_monitor = section_bounds(lines, "audio_monitor")
    for key, value in (
        ("capture_device", '"zoom_h8"'),
        ("source_id", '"mic_0"'),
        ("input_topic", '"/perception/sensor/audio/zoom_h8"'),
        ("detect_active_channels", "true"),
        ("active_channel_rms_threshold", "0.003"),
        ("active_channel_warmup_secs", "2.0"),
    ):
        set_key(lines, audio_monitor, key, value, "audio_monitor")

    path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} CONFIG_PATH")
    configure(Path(sys.argv[1]))
