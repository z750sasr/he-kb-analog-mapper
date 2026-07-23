"""Discovery and selection of installed keyboard adapter packages."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable
from typing import Any

from .base import KeyboardAdapter, KeyboardUnavailable


def discover_adapter_types() -> tuple[type[KeyboardAdapter], ...]:
    """Import subpackages that publish an ``ADAPTER_CLASS`` constant.

    Adding another keyboard therefore requires only a new directory under
    ``he_keyboard_mapper/keyboards``. PyInstaller is configured to collect these
    modules so the same discovery code works from source and in the EXE.
    """

    package = importlib.import_module(__package__)
    discovered: list[type[KeyboardAdapter]] = []
    for module_info in pkgutil.iter_modules(package.__path__):
        if not module_info.ispkg or module_info.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"{__package__}.{module_info.name}.adapter")
        except ModuleNotFoundError as error:
            # Ignore only a missing adapter module. Missing dependencies inside
            # a real adapter remain actionable import errors.
            if error.name == f"{__package__}.{module_info.name}.adapter":
                continue
            raise
        adapter_type = getattr(module, "ADAPTER_CLASS", None)
        if isinstance(adapter_type, type) and issubclass(adapter_type, KeyboardAdapter):
            discovered.append(adapter_type)
    return tuple(sorted(discovered, key=lambda item: (item.priority, item.adapter_id)))


class KeyboardRegistry:
    """Create adapters and try them in a deterministic auto-detection order."""

    def __init__(
        self,
        adapter_types: Iterable[type[KeyboardAdapter]] | None = None,
        hid_backend: Any | None = None,
    ) -> None:
        self.adapter_types = tuple(adapter_types) if adapter_types is not None else discover_adapter_types()
        self.hid_backend = hid_backend
        ids = [adapter.adapter_id for adapter in self.adapter_types]
        if not self.adapter_types or len(ids) != len(set(ids)):
            raise ValueError("The keyboard registry requires one or more uniquely named adapters.")

    def definitions(self) -> tuple[type[KeyboardAdapter], ...]:
        return self.adapter_types

    def adapter_type(self, adapter_id: str) -> type[KeyboardAdapter] | None:
        return next((item for item in self.adapter_types if item.adapter_id == adapter_id), None)

    def default_layout(self, preferred_id: str = "auto"):
        preferred = self.adapter_type(preferred_id) if preferred_id != "auto" else None
        return (preferred or self.adapter_types[0]).layout

    def connect(self, preferred_id: str = "auto") -> tuple[KeyboardAdapter, object]:
        """Open the requested adapter or probe every installed adapter."""

        if preferred_id != "auto":
            preferred = self.adapter_type(preferred_id)
            if preferred is None:
                raise KeyboardUnavailable(f"Unknown keyboard adapter: {preferred_id}")
            candidates = (preferred,)
        else:
            candidates = self.adapter_types

        failures: list[str] = []
        for adapter_type in candidates:
            adapter = adapter_type(self.hid_backend)
            try:
                return adapter, adapter.connect()
            except Exception as error:
                failures.append(f"{adapter_type.display_name}: {error}")
                try:
                    adapter.close()
                except Exception:
                    pass
        detail = failures[-1] if failures else "No adapters are installed."
        raise KeyboardUnavailable(f"No supported Hall-effect keyboard was detected. {detail}")
