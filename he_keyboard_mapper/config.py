"""Configuration location, loading, and atomic saving."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import MapperConfig


APP_DIR_NAME = "HallAnalogMapper"
LEGACY_APP_DIR_NAME = "HE30AnalogMapper"
CONFIG_NAME = "config.json"


def config_directory() -> Path:
    """Return a per-user writable directory suitable for an installed app."""

    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME


def config_path() -> Path:
    return config_directory() / CONFIG_NAME


def legacy_config_path() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / LEGACY_APP_DIR_NAME / CONFIG_NAME


def load_config(path: Path | None = None) -> MapperConfig:
    target = path or config_path()
    if path is None and not target.exists() and legacy_config_path().exists():
        target = legacy_config_path()
    try:
        return MapperConfig.from_dict(json.loads(target.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return MapperConfig()
    except (OSError, ValueError, TypeError):
        # A bad local file should never prevent the tray process from starting.
        return MapperConfig()


def save_config(config: MapperConfig, path: Path | None = None) -> Path:
    """Atomically replace config so a crash cannot leave half-written JSON."""

    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(config.sanitize().to_dict(), indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target
