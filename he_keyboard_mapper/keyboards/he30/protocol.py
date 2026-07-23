"""EPOMAKER HE30 HID protocol and physical-key resolution.

The keyboard emits analog travel as asynchronous 0xA0 reports only while the
profile's Dynamic Display flag is enabled. This module owns that temporary flag,
restores it on shutdown, and keeps binary protocol details out of UI code.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from ...models import ProfileChangeEvent, TelemetryEvent
from .layout import HE30_MODELS, PHYSICAL_BY_HID, PHYSICAL_BY_INDEX

try:  # Optional at import time so pure unit tests run without Windows drivers.
    import hid as _hid
except ImportError:  # pragma: no cover - exercised on developer machines only.
    _hid = None


REPORT_SIZE = 64
CHUNK_SIZE = 56
REQUEST_PREFIX = 0x55
RESPONSE_PREFIX = 0xAA
LAYER_COUNT = 4
KEY_COUNT = 128


class HE30Error(RuntimeError):
    """Actionable connection/protocol failure shown to the user."""


def _normalise_report(data: Iterable[int] | bytes | None) -> tuple[int, ...]:
    report = tuple(int(value) & 0xFF for value in (data or ()))
    # Some HID wrappers include report ID zero while others remove it.
    if len(report) == REPORT_SIZE + 1 and report[0] == 0:
        report = report[1:]
    return report


def decode_telemetry_report(data: Iterable[int] | bytes | None) -> TelemetryEvent | None:
    """Decode the HE30 0xA0 mapping triplet and big-endian travel distance."""

    report = _normalise_report(data)
    if len(report) < 11 or report[0] != 0xA0:
        return None
    return TelemetryEvent(
        mapping_type=report[1],
        code1=report[2],
        code2=report[3],
        raw_travel=(report[6] << 8) | report[7],
        status=report[10],
        report=report,
    )


def decode_profile_change_report(data: Iterable[int] | bytes | None) -> ProfileChangeEvent | None:
    """Decode local or global layer numbering used by different HE30 firmware."""

    report = _normalise_report(data)
    if len(report) < 3 or report[0] != 0xA1:
        return None
    raw_layer = report[1]
    reports_global_layer = LAYER_COUNT <= raw_layer < 12
    profile_index = raw_layer // LAYER_COUNT if reports_global_layer else min(2, report[2])
    layer = raw_layer % LAYER_COUNT
    return ProfileChangeEvent(profile_index, layer, profile_index * LAYER_COUNT + layer)


def _mapping_hid_code(signal: tuple[int, int, int]) -> int | None:
    """Return a normal HID code when a mapping triplet represents a keyboard key."""

    mapping_type, code1, code2 = signal
    if mapping_type != 16:
        return None
    if code1:
        return {1: 224, 2: 225, 4: 226, 8: 227, 16: 228, 32: 229, 64: 230, 128: 231}.get(code1)
    return code2


class MappingResolver:
    """Resolve a report's current mapping back to its physical firmware slot.

    Reports contain the action assigned to a key rather than an explicit physical
    index. Reading each mapping layer provides the reverse lookup. If duplicate
    mappings are present, the first visible HE30 key is used because the report
    itself contains no information that can disambiguate duplicates.
    """

    def __init__(self) -> None:
        self._slots: dict[tuple[int, int, tuple[int, int, int]], list[int]] = defaultdict(list)
        self._active: dict[tuple[int, int, int], int] = {}

    def clear(self) -> None:
        self._slots.clear()
        self._active.clear()

    def add_mapping_bank(self, profile: int, layer: int, data: Iterable[int]) -> None:
        values = tuple(int(value) & 0xFF for value in data)
        for index in range(min(KEY_COUNT, len(values) // 3)):
            signal = tuple(values[index * 3:index * 3 + 3])
            if index in PHYSICAL_BY_INDEX and signal != (255, 255, 255):
                self._slots[(profile, layer, signal)].append(index)

    def resolve(self, event: TelemetryEvent, profile: int, layer: int) -> int | None:
        signal = event.signal
        if event.raw_travel <= 0 and signal in self._active:
            return self._active.pop(signal)

        candidates = self._slots.get((profile, layer, signal), [])
        physical = candidates[0] if candidates else None

        # Fallback covers devices for which a mapping bank cannot be read. It is
        # accurate for the factory layout and all unique normal keyboard outputs.
        if physical is None:
            if signal[0] == 240 and signal[1] == 255:
                physical = 26
            else:
                physical = PHYSICAL_BY_HID.get(_mapping_hid_code(signal))

        if physical is not None and event.raw_travel > 0:
            self._active[signal] = physical
        return physical


class HE30Protocol:
    """Synchronous hidapi session used exclusively by the mapper service thread."""

    def __init__(self, hid_backend: Any | None = None, timeout_ms: int = 1800) -> None:
        self.hid = hid_backend if hid_backend is not None else _hid
        self.timeout_ms = timeout_ms
        self.device: Any | None = None
        self.device_info: dict[str, Any] | None = None
        self.model_name = "EPOMAKER HE30"
        self.profile_count = 1
        self.active_profile = 0
        self.active_layer = 0
        self.resolver = MappingResolver()
        self._restore_profiles: set[int] = set()

    def enumerate_candidates(self) -> list[dict[str, Any]]:
        if self.hid is None:
            raise HE30Error("hidapi is not installed. Run: pip install -r requirements.txt")
        candidates: list[dict[str, Any]] = []
        for vendor_id, product_id in HE30_MODELS:
            for info in self.hid.enumerate(vendor_id, product_id):
                if info.get("path") is not None:
                    candidates.append(dict(info))
        # Prefer the usage page/usage captured from the configuration interface,
        # but still probe other interfaces because hidapi metadata varies by OS.
        return sorted(
            candidates,
            key=lambda item: (
                0 if item.get("usage_page") == 1 and item.get("usage") in (0, None) else 1,
                item.get("interface_number", 99),
            ),
        )

    def connect(self) -> dict[str, Any]:
        """Probe known HE30 interfaces with a harmless active-profile request."""

        errors: list[str] = []
        for info in self.enumerate_candidates():
            candidate = self.hid.device()
            try:
                candidate.open_path(info["path"])
                candidate.set_nonblocking(False)
                self.device = candidate
                self.active_profile = self.get_active_profile()
                self.device_info = info
                key = (int(info.get("vendor_id", 0)), int(info.get("product_id", 0)))
                self.model_name, self.profile_count = HE30_MODELS.get(key, ("EPOMAKER HE30", 1))
                self.active_profile = min(self.profile_count - 1, self.active_profile)
                return info
            except Exception as error:  # Interfaces that are not config endpoints are expected.
                errors.append(str(error))
                try:
                    candidate.close()
                except Exception:
                    pass
                self.device = None
        detail = f" Last response: {errors[-1]}" if errors else ""
        raise HE30Error(f"No compatible HE30 configuration interface could be opened.{detail}")

    def _read(self, timeout_ms: int | None = None) -> tuple[int, ...]:
        if self.device is None:
            raise HE30Error("Keyboard is not connected.")
        timeout = self.timeout_ms if timeout_ms is None else timeout_ms
        try:
            return _normalise_report(self.device.read(REPORT_SIZE, timeout))
        except TypeError:  # Compatibility with older hidapi Python wrappers.
            return _normalise_report(self.device.read(REPORT_SIZE))

    def _write_report(self, payload: list[int]) -> None:
        if self.device is None:
            raise HE30Error("Keyboard is not connected.")
        report = bytes([0, *payload[:REPORT_SIZE]])
        written = self.device.write(report)
        if written <= 0:
            raise HE30Error("The keyboard rejected an output report.")

    def transact(self, command: int, args: Iterable[int] = ()) -> tuple[int, ...]:
        payload = [0] * REPORT_SIZE
        payload[0] = command & 0xFF
        for index, value in enumerate(tuple(args)[:REPORT_SIZE - 1], start=1):
            payload[index] = int(value) & 0xFF
        self._write_report(payload)
        deadline = time.monotonic() + self.timeout_ms / 1000
        while time.monotonic() < deadline:
            report = self._read(max(1, int((deadline - time.monotonic()) * 1000)))
            if report and report[0] == RESPONSE_PREFIX:
                return report
            # 0xA0/0xA1 can arrive between a request and its acknowledgement.
        raise HE30Error(f"Keyboard did not acknowledge command 0x{command:02X}.")

    def read_block(self, command: int, offset: int, size: int) -> bytes:
        output = bytearray()
        end = offset + size
        for cursor in range(offset, end, CHUNK_SIZE):
            length = min(CHUNK_SIZE, end - cursor)
            low, high = cursor & 0xFF, (cursor >> 8) & 0xFF
            checksum = (low + high + length) & 0xFF
            response = self.transact(REQUEST_PREFIX, [command, 0, checksum, length, low, high])
            output.extend(response[8:8 + length])
        return bytes(output[:size])

    def write_block(self, command: int, offset: int, data: bytes | bytearray) -> None:
        values = bytes(data)
        for cursor in range(0, len(values), CHUNK_SIZE):
            chunk = values[cursor:cursor + CHUNK_SIZE]
            absolute = offset + cursor
            low, high = absolute & 0xFF, (absolute >> 8) & 0xFF
            body = [len(chunk), low, high, 0, *chunk]
            self.transact(REQUEST_PREFIX, [command, 0, sum(body) & 0xFF, *body])

    def write_and_verify(self, write_command: int, read_command: int, offset: int, data: bytes) -> None:
        self.write_block(write_command, offset, data)
        if self.read_block(read_command, offset, len(data)) != data:
            raise HE30Error("Dynamic Display setting failed read-back verification.")

    def get_active_profile(self) -> int:
        response = self.transact(REQUEST_PREFIX, [4, 0, 32, 32])
        return min(2, response[8] if len(response) > 8 else 0)

    def _load_mapping_resolver(self) -> None:
        self.resolver.clear()
        for profile in range(self.profile_count):
            for layer in range(LAYER_COUNT):
                offset = 2048 * profile + 512 * layer
                self.resolver.add_mapping_bank(profile, layer, self.read_block(8, offset, 384))

    def _enable_dynamic_display(self) -> None:
        for profile in range(self.profile_count):
            offset = profile * 64
            config = self.read_block(5, offset, 64)
            if not (config[7] & 0x08):
                enabled = bytearray(config)
                enabled[7] |= 0x08
                self.write_and_verify(6, 5, offset, bytes(enabled))
                self._restore_profiles.add(profile)

    def prepare_stream(self) -> None:
        """Read mappings, then enable travel reports for every onboard profile."""

        if self.device is None:
            self.connect()
        self.active_profile = min(self.profile_count - 1, self.get_active_profile())
        self.active_layer = 0
        self._load_mapping_resolver()
        self._enable_dynamic_display()

    def read_event(self, timeout_ms: int = 100) -> TelemetryEvent | ProfileChangeEvent | None:
        report = self._read(timeout_ms)
        if not report:
            return None
        profile_change = decode_profile_change_report(report)
        if profile_change:
            self.active_profile = min(self.profile_count - 1, profile_change.profile_index)
            self.active_layer = profile_change.layer
            return profile_change
        return decode_telemetry_report(report)

    def resolve_physical(self, event: TelemetryEvent) -> int | None:
        return self.resolver.resolve(event, self.active_profile, self.active_layer)

    def restore_dynamic_display(self) -> None:
        """Clear only flags that this process enabled, preserving all other bytes."""

        pending = sorted(self._restore_profiles)
        self._restore_profiles.clear()
        for profile in pending:
            try:
                offset = profile * 64
                config = bytearray(self.read_block(5, offset, 64))
                config[7] &= 0xF7
                self.write_and_verify(6, 5, offset, bytes(config))
            except Exception:
                # Shutdown must continue even after a physical disconnect.
                pass

    def close(self) -> None:
        if self.device is None:
            return
        self.restore_dynamic_display()
        try:
            self.device.close()
        finally:
            self.device = None

    def __enter__(self) -> "HE30Protocol":
        self.connect()
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()
