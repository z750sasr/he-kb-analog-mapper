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
    """Stable config identifier plus user-facing label and compact key badge."""

    value: str
    label: str
    short: str


CONTROLLER_ACTIONS: tuple[ControllerAction, ...] = (
    ControllerAction("none", "None", "—"),
    ControllerAction("left_stick_up", "Left stick · Up", "LS ↑"),
    ControllerAction("left_stick_down", "Left stick · Down", "LS ↓"),
    ControllerAction("left_stick_left", "Left stick · Left", "LS ←"),
    ControllerAction("left_stick_right", "Left stick · Right", "LS →"),
    ControllerAction("right_stick_up", "Right stick · Up", "RS ↑"),
    ControllerAction("right_stick_down", "Right stick · Down", "RS ↓"),
    ControllerAction("right_stick_left", "Right stick · Left", "RS ←"),
    ControllerAction("right_stick_right", "Right stick · Right", "RS →"),
    ControllerAction("left_trigger", "Left trigger", "LT"),
    ControllerAction("right_trigger", "Right trigger", "RT"),
    ControllerAction("button_a", "Button A", "A"),
    ControllerAction("button_b", "Button B", "B"),
    ControllerAction("button_x", "Button X", "X"),
    ControllerAction("button_y", "Button Y", "Y"),
    ControllerAction("left_bumper", "Left bumper", "LB"),
    ControllerAction("right_bumper", "Right bumper", "RB"),
    ControllerAction("back", "Back / View", "Back"),
    ControllerAction("start", "Start / Menu", "Start"),
    ControllerAction("left_stick_click", "Left stick click", "L3"),
    ControllerAction("right_stick_click", "Right stick click", "R3"),
    ControllerAction("dpad_up", "D-pad · Up", "D ↑"),
    ControllerAction("dpad_down", "D-pad · Down", "D ↓"),
    ControllerAction("dpad_left", "D-pad · Left", "D ←"),
    ControllerAction("dpad_right", "D-pad · Right", "D →"),
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
