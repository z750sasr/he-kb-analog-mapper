"""Replace this two-key example with the keyboard's physical matrix."""

from he_keyboard_mapper.keyboards.base import KeyboardKey, KeyboardLayout

LAYOUT = KeyboardLayout(
    "brand_model",
    "Brand Model",
    ((KeyboardKey(0, "A"), KeyboardKey(1, "B")),),
)
