#!/usr/bin/env python3
"""Fetch and verify the pinned i4h dVRK PSM root USD."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

URL = (
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/"
    "Isaac/Healthcare/0.6.0/c189487/Robots/dVRK/PSM/psm.usd"
)
EXPECTED_SHA256 = "5730339c3b806f17a5228c69b97464d0b3469888002f62fb23d9621f746347c8"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    default_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    data_root = Path(os.environ.get("SURGISABRE_DATA_ROOT", default_root / "surgisabre"))
    destination = data_root / "assets/i4h-0.6.0-c189487/psm.usd"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or sha256(destination) != EXPECTED_SHA256:
        partial = destination.with_suffix(".usd.partial")
        request = urllib.request.Request(URL, headers={"User-Agent": "SurgiSabre/0.1"})
        try:
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                partial.open("wb") as output,
            ):
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            actual = sha256(partial)
            if actual != EXPECTED_SHA256:
                raise RuntimeError(
                    f"i4h PSM digest mismatch: received {actual}, expected {EXPECTED_SHA256}"
                )
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
    print(f"i4h PSM root USD verified: {destination}")


if __name__ == "__main__":
    main()
