"""Controller-output metadata and backward-compatible HE30 layout exports."""

from __future__ import annotations

from dataclasses import dataclass

# Compatibility aliases keep older imports working while all new code obtains
# layouts from the keyboard registry.
from .keyboards.he30.layout import (
    HE30_LAYOUT as HE30_LAYOUT_DEFINITION,
    HE30_MODELS,
    PHYSICAL_BY_HID,
    PHYSICAL_BY_INDEX,
    PHYSICAL_KEYS,
)

HE30_LAYOUT = HE30_LAYOUT_DEFINITION.rows
PhysicalKey = type(PHYSICAL_KEYS[0])


@dataclass(frozen=True, slots=True)
class ControllerAction:
    """Stable config identifier, labels, and one packaged controller icon."""

    value: str
    label: str
    short: str
    icon: str | None


CONTROLLER_ACTIONS: tuple[ControllerAction, ...] = (
    # The order mirrors the supplied 01-25 SVG pack, producing an intentional
    # 5×5 grid in the mapping panel.
    ControllerAction("button_a", "Button A", "A", "01_button_a.png"),
    ControllerAction("button_b", "Button B", "B", "02_button_b.png"),
    ControllerAction("button_x", "Button X", "X", "03_button_x.png"),
    ControllerAction("button_y", "Button Y", "Y", "04_button_y.png"),
    ControllerAction("start", "Start", "Start", "05_start.png"),
    ControllerAction("back", "Back / View", "Back", "06_back.png"),
    ControllerAction("menu", "Menu / Guide", "Menu", "07_menu.png"),
    ControllerAction("dpad_up", "D-pad · Up", "D ↑", "08_dpad_up.png"),
    ControllerAction("dpad_down", "D-pad · Down", "D ↓", "09_dpad_down.png"),
    ControllerAction("dpad_left", "D-pad · Left", "D ←", "10_dpad_left.png"),
    ControllerAction("dpad_right", "D-pad · Right", "D →", "11_dpad_right.png"),
    ControllerAction("left_stick_up", "Left stick · Up", "LS ↑", "12_left_stick_up.png"),
    ControllerAction("left_stick_down", "Left stick · Down", "LS ↓", "13_left_stick_down.png"),
    ControllerAction("left_stick_left", "Left stick · Left", "LS ←", "14_left_stick_left.png"),
    ControllerAction("left_stick_right", "Left stick · Right", "LS →", "15_left_stick_right.png"),
    ControllerAction("left_stick_click", "Left stick click", "L3", "16_left_stick_press.png"),
    ControllerAction("right_stick_up", "Right stick · Up", "RS ↑", "17_right_stick_up.png"),
    ControllerAction("right_stick_down", "Right stick · Down", "RS ↓", "18_right_stick_down.png"),
    ControllerAction("right_stick_left", "Right stick · Left", "RS ←", "19_right_stick_left.png"),
    ControllerAction("right_stick_right", "Right stick · Right", "RS →", "20_right_stick_right.png"),
    ControllerAction("right_stick_click", "Right stick click", "R3", "21_right_stick_press.png"),
    ControllerAction("left_bumper", "Left bumper", "LB", "22_left_bumper.png"),
    ControllerAction("left_trigger", "Left trigger", "LT", "23_left_trigger.png"),
    ControllerAction("right_bumper", "Right bumper", "RB", "24_right_bumper.png"),
    ControllerAction("right_trigger", "Right trigger", "RT", "25_right_trigger.png"),
    ControllerAction("none", "Unassigned", "Off", None),
)

ACTION_BY_ID = {action.value: action for action in CONTROLLER_ACTIONS}

# ViGEm enum names are retained as strings so pure mapping tests never load the
# Windows native client.
DIGITAL_BUTTON_ENUMS = {
    "button_a": "XUSB_GAMEPAD_A",
    "button_b": "XUSB_GAMEPAD_B",
    "button_x": "XUSB_GAMEPAD_X",
    "button_y": "XUSB_GAMEPAD_Y",
    "left_bumper": "XUSB_GAMEPAD_LEFT_SHOULDER",
    "right_bumper": "XUSB_GAMEPAD_RIGHT_SHOULDER",
    "menu": "XUSB_GAMEPAD_GUIDE",
    "back": "XUSB_GAMEPAD_BACK",
    "start": "XUSB_GAMEPAD_START",
    "left_stick_click": "XUSB_GAMEPAD_LEFT_THUMB",
    "right_stick_click": "XUSB_GAMEPAD_RIGHT_THUMB",
    "dpad_up": "XUSB_GAMEPAD_DPAD_UP",
    "dpad_down": "XUSB_GAMEPAD_DPAD_DOWN",
    "dpad_left": "XUSB_GAMEPAD_DPAD_LEFT",
    "dpad_right": "XUSB_GAMEPAD_DPAD_RIGHT",
}

DEFAULT_MAPPINGS = {
    "8": "left_trigger",       # Q
    "9": "left_stick_up",     # W
    "10": "right_trigger",    # E
    "14": "left_stick_left",  # A
    "15": "left_stick_down",  # S
    "16": "left_stick_right", # D
    "28": "button_a",         # Space
}
