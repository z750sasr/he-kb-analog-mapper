from __future__ import annotations

import unittest

from he_keyboard_mapper.models import TelemetryEvent
from he_keyboard_mapper.protocol import (
    HE30Protocol,
    MappingResolver,
    decode_profile_change_report,
    decode_telemetry_report,
)
from he_keyboard_mapper.keyboards.everglide_ae64pro.protocol import (
    AE64Protocol,
    EXPECTED_BOARD_ID,
    decode_axis_data_report,
)


class FakeHidDevice:
    """Small in-memory implementation of the captured 0x55 block protocol."""

    def __init__(self) -> None:
        self.responses: list[list[int]] = []
        self.config = bytearray(64 * 3)
        self.keymaps = bytearray([255] * (2048 * 3))
        self.closed = False

    def open_path(self, _path: bytes) -> None: pass
    def set_nonblocking(self, _value: bool) -> None: pass

    def write(self, report: bytes) -> int:
        payload = list(report[1:])
        subcommand = payload[1]
        response = [0] * 64
        response[0] = 0xAA
        if subcommand == 4:
            response[8] = 1
        elif subcommand in (5, 8):
            length, low, high = payload[4], payload[5], payload[6]
            offset = low | (high << 8)
            source = self.config if subcommand == 5 else self.keymaps
            response[8:8 + length] = source[offset:offset + length]
        elif subcommand == 6:
            length, low, high = payload[4], payload[5], payload[6]
            offset = low | (high << 8)
            self.config[offset:offset + length] = bytes(payload[8:8 + length])
        self.responses.append(response)
        return len(report)

    def read(self, _size: int, _timeout: int = 0) -> list[int]:
        return self.responses.pop(0) if self.responses else []

    def close(self) -> None:
        self.closed = True


class FakeHidBackend:
    def __init__(self) -> None:
        self.handle = FakeHidDevice()

    def enumerate(self, vendor_id: int, product_id: int) -> list[dict[str, object]]:
        if (vendor_id, product_id) != (0x19F5, 0xFB4C):
            return []
        return [{
            "vendor_id": vendor_id,
            "product_id": product_id,
            "path": b"fake-he30",
            "usage_page": 1,
            "usage": 0,
            "interface_number": 1,
        }]

    def device(self) -> FakeHidDevice:
        return self.handle


class TelemetryCodecTests(unittest.TestCase):
    def test_normal_key_report_uses_he30_travel_bytes(self) -> None:
        event = decode_telemetry_report([0xA0, 16, 0, 4, 0, 0, 1, 44, 0, 0, 255])
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.signal, (16, 0, 4))
        self.assertEqual(event.raw_travel, 300)
        self.assertEqual(event.status, 255)

    def test_optional_report_id_is_removed(self) -> None:
        event = decode_telemetry_report([0, 0xA0, 16, 2, 0, 0, 0, 0, 25, 0, 0, 1] + [0] * 53)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.signal, (16, 2, 0))
        self.assertEqual(event.raw_travel, 25)

    def test_global_layer_report_selects_profile(self) -> None:
        event = decode_profile_change_report([0xA1, 7, 0])
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual((event.profile_index, event.layer, event.global_layer), (1, 3, 7))


class MappingResolverTests(unittest.TestCase):
    def test_mapping_triplet_resolves_to_physical_slot(self) -> None:
        bank = bytearray([255] * 384)
        bank[9 * 3:9 * 3 + 3] = bytes([16, 0, 26])  # Physical W slot mapped to W.
        resolver = MappingResolver()
        resolver.add_mapping_bank(0, 0, bank)
        pressed = TelemetryEvent(16, 0, 26, 200, 1)
        released = TelemetryEvent(16, 0, 26, 0, 0)
        self.assertEqual(resolver.resolve(pressed, 0, 0), 9)
        self.assertEqual(resolver.resolve(released, 0, 1), 9)  # Release survives a layer change.

    def test_factory_hid_fallback(self) -> None:
        resolver = MappingResolver()
        self.assertEqual(resolver.resolve(TelemetryEvent(16, 0, 4, 100, 1), 0, 0), 14)


class ProtocolLifecycleTests(unittest.TestCase):
    def test_dynamic_display_is_enabled_verified_and_restored(self) -> None:
        backend = FakeHidBackend()
        protocol = HE30Protocol(backend)
        protocol.connect()
        self.assertEqual(protocol.active_profile, 1)
        self.assertEqual(protocol.profile_count, 3)
        protocol.prepare_stream()
        self.assertEqual([backend.handle.config[index * 64 + 7] & 8 for index in range(3)], [8, 8, 8])
        protocol.close()
        self.assertEqual([backend.handle.config[index * 64 + 7] & 8 for index in range(3)], [0, 0, 0])
        self.assertTrue(backend.handle.closed)


class FakeAE64Device:
    """Small in-memory version of the read-only AE64 WebHID surface."""

    def __init__(self) -> None:
        self.rows = {row: [0] * 30 for row in range(1, 6)}
        self.responses: list[list[int]] = []
        self.closed = False

    def open_path(self, _path: bytes) -> None: pass
    def set_nonblocking(self, _value: bool) -> None: pass

    def write(self, report: bytes) -> int:
        payload = list(report[1:])
        response = [0] * 64
        response[0:2] = payload[0:2]
        if payload[:2] == [0x01, 0x02]:
            response[4:8] = list(EXPECTED_BOARD_ID.to_bytes(4, "big"))
            response[8:12] = [1, 2, 3, 4]
        elif payload[:2] == [0x02, 0x03]:
            response[3] = 3
        elif payload[:2] == [0x04, 0x03]:
            response[2], response[3] = payload[2], payload[3]
            for index, value in enumerate(self.rows[payload[3]]):
                response[4 + index * 2] = value & 0xFF
                response[5 + index * 2] = value >> 8
        self.responses.append(response)
        return len(report)

    def read(self, _size: int, _timeout: int = 0) -> list[int]:
        return self.responses.pop(0) if self.responses else []

    def close(self) -> None:
        self.closed = True


class FakeAE64Backend:
    def __init__(self) -> None:
        self.handle = FakeAE64Device()

    def enumerate(self, vendor_id: int, product_id: int) -> list[dict[str, object]]:
        if (vendor_id, product_id) != (0x1CA6, 0x300A):
            return []
        return [{
            "vendor_id": vendor_id,
            "product_id": product_id,
            "path": b"fake-ae64",
            "usage_page": 0xFFB0,
            "usage": 1,
            "interface_number": 2,
        }]

    def device(self) -> FakeAE64Device:
        return self.handle


class AE64ProtocolTests(unittest.TestCase):
    def test_axis_reply_uses_little_endian_travel_values(self) -> None:
        report = [0x04, 0x03, 1, 2, 0xD2, 0x04] + [0] * 58
        decoded = decode_axis_data_report(report)
        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded[:2], (1, 2))
        self.assertEqual(decoded[2][0], 1234)

    def test_ae64_polls_changed_routes_and_emits_releases(self) -> None:
        backend = FakeAE64Backend()
        protocol = AE64Protocol(backend, poll_interval_ms=0)
        info = protocol.connect()
        self.assertEqual(info["board_id"], EXPECTED_BOARD_ID)
        self.assertEqual(protocol.profile_count, 3)
        protocol.prepare_stream()
        protocol._poll()  # Establish an idle baseline without 64 zero events.
        self.assertIsNone(protocol.read_event(0))
        backend.handle.rows[2][2] = 1234  # Physical Q, key id 15, after the wide Tab slot.
        protocol._poll()
        pressed = protocol.read_event(0)
        self.assertIsNotNone(pressed)
        assert pressed is not None
        self.assertEqual((pressed.key_id, pressed.raw_value, pressed.status), (15, 1234, 1))
        backend.handle.rows[2][2] = 0
        protocol._poll()
        released = protocol.read_event(0)
        self.assertIsNotNone(released)
        assert released is not None
        self.assertEqual((released.key_id, released.raw_value, released.status), (15, 0, 0))
        protocol.close()
        self.assertTrue(backend.handle.closed)


if __name__ == "__main__":
    unittest.main()
