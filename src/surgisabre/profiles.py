"""Tested runtime profiles without machine-specific network identities."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_RUNTIME_PROFILE = "gb10_arm64"


@dataclass(frozen=True)
class RuntimeProfile:
    """One tested software and hardware profile."""

    name: str
    architecture: str
    isaac_sim_version: str
    python_minor: str
    gpu_name: str

    @property
    def python_pattern(self) -> str:
        major, minor = self.python_minor.split(".", maxsplit=1)
        return rf"{major}\.{minor}(?:\.[0-9]+)?"


RUNTIME_PROFILES = {
    "gb10_arm64": RuntimeProfile(
        name="gb10_arm64",
        architecture="aarch64",
        isaac_sim_version="6.0.1",
        python_minor="3.12",
        gpu_name="NVIDIA GB10",
    ),
}


def get_runtime_profile(name: str | None = None) -> RuntimeProfile:
    """Return a tested profile without asserting a particular host address."""

    selected = name or DEFAULT_RUNTIME_PROFILE
    try:
        return RUNTIME_PROFILES[selected]
    except KeyError as error:
        choices = ", ".join(sorted(RUNTIME_PROFILES))
        raise ValueError(f"runtime profile must be one of: {choices}") from error


__all__ = [
    "DEFAULT_RUNTIME_PROFILE",
    "RUNTIME_PROFILES",
    "RuntimeProfile",
    "get_runtime_profile",
]
