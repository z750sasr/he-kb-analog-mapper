"""Keyboard adapter framework.

Each supported keyboard lives in its own subpackage. The registry discovers
those packages automatically, which keeps brand-specific USB details out of the
controller and user-interface layers.
"""

from .base import (
    DigitalOutputPolicy,
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardIdentity,
    KeyboardKey,
    KeyboardLayout,
    KeyTravelEvent,
    LayerChangeEvent,
    TravelCalibration,
)
from .registry import KeyboardRegistry

__all__ = [
    "DigitalOutputPolicy",
    "KeyboardAdapter",
    "KeyboardCapabilities",
    "KeyboardIdentity",
    "KeyboardKey",
    "KeyboardLayout",
    "KeyboardRegistry",
    "KeyTravelEvent",
    "LayerChangeEvent",
    "TravelCalibration",
]
