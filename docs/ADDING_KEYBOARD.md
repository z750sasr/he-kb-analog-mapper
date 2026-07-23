# Adding another Hall-effect keyboard

The mapper discovers adapter packages automatically. Supporting another brand
does not require editing the controller, background service, tray, configuration
window, or keyboard renderer.

Create `he30_mapper/keyboards/<your_keyboard>/` with these three implementation
files and an empty `__init__.py`:

## 1. `layout.py` — physical visualization

Describe rows with stable firmware/matrix IDs and normal keyboard-unit widths:

```python
from ..base import KeyboardKey, KeyboardLayout

LAYOUT = KeyboardLayout(
    layout_id="brand_model_60",
    name="Brand Model 60%",
    rows=(
        (KeyboardKey(0, "Esc"), KeyboardKey(1, "1")),
        (KeyboardKey(20, "Shift", width=2.25), KeyboardKey(21, "Z")),
    ),
)
```

The shared canvas automatically supplies proportional widths, controller labels,
physical labels, selection states, and live travel fills.

## 2. `protocol.py` — HID/WebHID-equivalent transport

Implement the keyboard's normal configuration interface using `hidapi`. WebHID
`sendReport`/`inputreport` logic generally translates to `device.write` and
`device.read` with the same report bytes.

The protocol should:

1. enumerate only known normal-mode VID/PID/interface combinations;
2. probe candidates with a harmless read command;
3. prepare or subscribe to Hall reports;
4. resolve each report to the stable key ID from `layout.py`;
5. restore every temporary device setting in `close()`.

Keep bootloader, updater, and firmware-flashing IDs out of the adapter.

## 3. `adapter.py` — small glue layer and travel conversion

Subclass `KeyboardAdapter`, delegate USB work to the protocol, and convert the
keyboard's raw Hall unit:

```python
from ..base import KeyboardAdapter, KeyTravelEvent
from .layout import LAYOUT
from .protocol import BrandProtocol

class BrandAdapter(KeyboardAdapter):
    adapter_id = "brand_model"
    display_name = "Brand Model"
    layout = LAYOUT

    def normalize_travel(self, raw_value, calibration):
        if raw_value <= calibration.deadzone_raw:
            return 0.0
        span = max(1, calibration.full_scale_raw - calibration.deadzone_raw)
        return min(1.0, (raw_value - calibration.deadzone_raw) / span)

    # connect(), prepare(), read_event(), and close() delegate to BrandProtocol.

ADAPTER_CLASS = BrandAdapter
```

`ADAPTER_CLASS` is the registration point. The registry imports it at startup,
orders adapters by `priority`, and probes them until one connects. No central
device list needs to be edited.

## Optional capabilities

Set `capabilities = KeyboardCapabilities(...)` when firmware supports profiles,
layers, or digital keyboard-output control.

Digital-output control follows Wootility semantics:

- `keyboard_keys_enabled=False`: prevent all keys on that keyboard from typing;
- `gamepad_mapping_override=True`: suppress typing only on controller-bound keys.

Implement this only when the device protocol can do it safely and restore the
original state in `close()`. Do not use a system-wide Windows keyboard hook; it
cannot reliably distinguish the target keyboard and can block unrelated input
devices.

## Verification checklist

- Add decoder/conversion tests that do not require hardware.
- Add a fake-HID lifecycle test covering temporary state restoration.
- Confirm `KeyboardRegistry().definitions()` contains the adapter.
- Run `python -m unittest discover -s tests -v`.
- Build with `.\build.ps1`; the spec collects adapter submodules dynamically.
