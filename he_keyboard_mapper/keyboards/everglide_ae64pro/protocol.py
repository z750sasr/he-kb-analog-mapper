"""Read-only Everglide AE64 Pro vendor-HID transport.

The companion WebHID driver verifies the AE64's normal configuration
collection as VID:PID 1CA6:300A, usage FFB0:0001. It exposes Hall travel
through synchronous ``04 03 01 <row>`` route-data replies rather than an
asynchronous telemetry report. This module polls that documented read surface
only; it deliberately contains no configuration, calibration, lighting, or
firmware-write command.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Iterable
from typing import Any

from ..base import KeyTravelEvent, device_selection_id
from .layout import AE64_MODELS, KEY_ID_BY_POSITION

try:  # Keep import-only tests independent from a Windows HID installation.
    import hid as _hid
except ImportError:  # pragma: no cover - exercised only without dependencies.
    _hid = None


REPORT_ID = 0
REPORT_SIZE = 64
VENDOR_ID = 0x1CA6
PRODUCT_ID = 0x300A
USAGE_PAGE = 0xFFB0
USAGE = 0x01
EXPECTED_BOARD_ID = 0x0030000A
PHYSICAL_ROWS = tuple(range(1, 6))
ROUTE_AXIS_DATA = 1


class AE64ProtocolError(RuntimeError):
    """An actionable AE64 configuration-interface failure."""


def _normalise_report(data: Iterable[int] | bytes | None) -> tuple[int, ...]:
    """Accept either hidapi's payload or a payload prefixed by report ID zero."""

    report = tuple(int(value) & 0xFF for value in (data or ()))
    if len(report) == REPORT_SIZE + 1 and report[0] == REPORT_ID:
        return report[1:]
    return report


def read16(data: Iterable[int] | bytes, offset: int) -> int:
    """Decode the little-endian 16-bit values used in AE64 replies."""

    values = tuple(data)
    return (int(values[offset]) if offset < len(values) else 0) | (
        (int(values[offset + 1]) if offset + 1 < len(values) else 0) << 8
    )


def decode_axis_data_report(
    data: Iterable[int] | bytes | None,
) -> tuple[int, int, tuple[int, ...]] | None:
    """Decode ``04 03 <kind> <row>`` reply values without touching hardware."""

    report = _normalise_report(data)
    if len(report) < 4 or report[:2] != (0x04, 0x03):
        return None
    return report[2], report[3], tuple(read16(report, offset) for offset in range(4, REPORT_SIZE - 1, 2))


class AE64Protocol:
    """Synchronous, read-only AE64 session used by the mapper service thread."""

    def __init__(
        self,
        hid_backend: Any | None = None,
        timeout_ms: int = 250,
        poll_interval_ms: int = 8,
        preferred_id: str = "auto",
    ) -> None:
        self.hid = hid_backend if hid_backend is not None else _hid
        self.timeout_ms = timeout_ms
        self.poll_interval_ms = poll_interval_ms
        self.preferred_id = preferred_id
        self.device: Any | None = None
        self.device_info: dict[str, Any] | None = None
        self.model_name = "Everglide AE64 Pro"
        self.profile_count = 1
        self._previous_values: dict[int, int] = {}
        self._pending_events: deque[KeyTravelEvent] = deque()
        self._next_poll_at = 0.0

    def enumerate_candidates(self) -> list[dict[str, Any]]:
        if self.hid is None:
            raise AE64ProtocolError("hidapi is not installed. Run: pip install -r requirements.txt")
        candidates = [
            dict(info)
            for info in self.hid.enumerate(VENDOR_ID, PRODUCT_ID)
            if info.get("path") is not None
        ]
        # Do not blindly open an ordinary keyboard interface when hidapi gives
        # us collection metadata. Older hidapi builds omit it, so the harmless
        # board-information read remains the final compatibility probe.
        return sorted(
            candidates,
            key=lambda item: (
                0 if item.get("usage_page") == USAGE_PAGE and item.get("usage") == USAGE else 1,
                item.get("interface_number", 99),
            ),
        )

    def _matches_preferred_device(self, info: dict[str, Any]) -> bool:
        if self.preferred_id in ("auto", "", "everglide_ae64pro"):
            return True
        return device_selection_id("everglide_ae64pro", info) == self.preferred_id

    def connect(self) -> dict[str, Any]:
        """Open only an interface that proves it is the AE64 configuration HID."""

        errors: list[str] = []
        for info in (item for item in self.enumerate_candidates() if self._matches_preferred_device(item)):
            candidate = self.hid.device()
            try:
                candidate.open_path(info["path"])
                candidate.set_nonblocking(False)
                self.device = candidate
                details = self.get_device_info()
                if details["board_id"] != EXPECTED_BOARD_ID:
                    raise AE64ProtocolError(
                        f"Unexpected board ID 0x{details['board_id']:08X}; expected AE64 Pro 0x{EXPECTED_BOARD_ID:08X}."
                    )
                self.device_info = {**info, **details}
                self.model_name = AE64_MODELS[(VENDOR_ID, PRODUCT_ID)]
                self.profile_count = self.get_profile_count()
                return self.device_info
            except Exception as error:
                errors.append(str(error))
                try:
                    candidate.close()
                except Exception:
                    pass
                self.device = None
        detail = f" Last response: {errors[-1]}" if errors else ""
        raise AE64ProtocolError(f"No compatible Everglide AE64 Pro configuration interface could be opened.{detail}")

    def _read(self, timeout_ms: int | None = None) -> tuple[int, ...]:
        if self.device is None:
            raise AE64ProtocolError("Keyboard is not connected.")
        timeout = self.timeout_ms if timeout_ms is None else timeout_ms
        try:
            return _normalise_report(self.device.read(REPORT_SIZE, timeout))
        except TypeError:  # Compatibility with older hidapi Python wrappers.
            return _normalise_report(self.device.read(REPORT_SIZE))

    def _write(self, payload: Iterable[int]) -> None:
        if self.device is None:
            raise AE64ProtocolError("Keyboard is not connected.")
        frame = [0] * REPORT_SIZE
        for index, value in enumerate(tuple(payload)[:REPORT_SIZE]):
            frame[index] = int(value) & 0xFF
        written = self.device.write(bytes([REPORT_ID, *frame]))
        if written <= 0:
            raise AE64ProtocolError("The AE64 Pro rejected a configuration-interface read request.")

    def transact(self, payload: Iterable[int]) -> tuple[int, ...]:
        """Send one documented read request and wait for its family/op reply."""

        request = tuple(int(value) & 0xFF for value in payload)
        if len(request) < 2:
            raise ValueError("An AE64 request needs family and operation bytes.")
        self._write(request)
        deadline = time.monotonic() + self.timeout_ms / 1000
        while time.monotonic() < deadline:
            remaining = max(1, int((deadline - time.monotonic()) * 1000))
            report = self._read(remaining)
            if report[:2] == request[:2]:
                return report
        raise AE64ProtocolError(f"AE64 Pro did not answer read command {request[0]:02X}:{request[1]:02X}.")

    def get_device_info(self) -> dict[str, int | str]:
        data = self.transact((0x01, 0x02))
        board_id = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]
        firmware = ".".join(str(value) for value in data[8:12])
        return {"board_id": board_id, "firmware": firmware}

    def get_profile_count(self) -> int:
        """Read the AE64 configuration-slot count; safe fallback is one."""

        data = self.transact((0x02, 0x03, 0x00))
        return max(1, min(16, int(data[3] or 1)))

    def read_route_row(self, row: int) -> tuple[int, ...]:
        """Read one physical row's Hall route/travel values in thousandths mm."""

        if row not in PHYSICAL_ROWS:
            raise ValueError(f"AE64 physical row must be one of {PHYSICAL_ROWS}.")
        data = self.transact((0x04, 0x03, ROUTE_AXIS_DATA, row))
        decoded = decode_axis_data_report(data)
        if decoded is None:
            raise AE64ProtocolError("Malformed AE64 route-data reply.")
        axis_type, response_row, values = decoded
        if axis_type != ROUTE_AXIS_DATA or response_row != row:
            raise AE64ProtocolError("AE64 returned a different axis-data row than requested.")
        return values

    def prepare_stream(self) -> None:
        """Prime a zero baseline; no device settings are changed."""

        self._previous_values.clear()
        self._pending_events.clear()
        self._next_poll_at = 0.0

    def _poll(self) -> None:
        samples = {row: self.read_route_row(row) for row in PHYSICAL_ROWS}
        for (row, column), key_id in KEY_ID_BY_POSITION.items():
            raw_value = int(samples[row][column]) if column < len(samples[row]) else 0
            previous = self._previous_values.get(key_id)
            self._previous_values[key_id] = raw_value
            # Ignore startup zeros but always send transitions, including a
            # release to zero, so MappingEngine can release virtual buttons.
            if previous is not None and previous == raw_value:
                continue
            if previous is None and raw_value == 0:
                continue
            self._pending_events.append(KeyTravelEvent(key_id, raw_value, 1 if raw_value > 0 else 0))

    def read_event(self, timeout_ms: int = 100) -> KeyTravelEvent | None:
        """Return changed Hall values while rate-limiting row-poll requests."""

        if self._pending_events:
            return self._pending_events.popleft()
        now = time.monotonic()
        if now < self._next_poll_at:
            time.sleep(min(timeout_ms / 1000, self._next_poll_at - now))
            return None
        self._poll()
        self._next_poll_at = time.monotonic() + self.poll_interval_ms / 1000
        return self._pending_events.popleft() if self._pending_events else None

    def close(self) -> None:
        """Close the configuration interface; no temporary state needs restore."""

        self._pending_events.clear()
        if self.device is None:
            return
        try:
            self.device.close()
        finally:
            self.device = None
