#!/usr/bin/env python3
"""Merge session-clocked browser and Isaac JSONL traces into one ordered trace."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def load_trace(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            for field in ("type", "session_id", "sequence", "monotonic_ns"):
                if field not in event:
                    raise ValueError(f"{path}:{line_number} is missing {field}")
            event["_source_path"] = str(path)
            events.append(event)
    if not events:
        raise ValueError(f"trace is empty: {path}")
    return events


def merged_events(inputs: list[Path]) -> list[dict[str, Any]]:
    events = [event for path in inputs for event in load_trace(path)]
    session_ids = {event["session_id"] for event in events}
    if len(session_ids) != 1:
        raise ValueError("input traces do not share one session_id")
    events.sort(key=lambda event: (int(event["monotonic_ns"]), event["_source_path"], int(event["sequence"])))
    for sequence, event in enumerate(events):
        event.pop("_source_path")
        event["sequence"] = sequence
    return events


def merge_traces(inputs: list[Path], output: Path) -> int:
    events = merged_events(inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, allow_nan=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return len(events)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()
    count = merge_traces(args.inputs, args.output)
    print(f"Merged {count} events into {args.output}")


if __name__ == "__main__":
    main()
