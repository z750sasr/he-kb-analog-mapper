"""Physical AE64 Pro matrix extracted from the companion WebHID driver."""

from __future__ import annotations

from ..base import KeyboardKey, KeyboardLayout


# The firmware addresses its five physical rows as 1..5. Key IDs remain a
# stable, compact 0..63 sequence for the mapper configuration and UI.
_ROW_DEFINITIONS = (
    (("Esc", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0), ("6", 1.0), ("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("Backspace", 2.0)),
    (("Tab", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0), ("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.5)),
    (("Caps", 1.75), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0), ("G", 1.0), ("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 2.25)),
    (("Shift", 2.0), ("Z", 1.0), ("X", 1.0), ("C", 1.0), ("V", 1.0), ("B", 1.0), ("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("Shift", 1.0), ("Up", 1.0), ("Del", 1.0)),
    (("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("Space", 6.25), ("Alt", 1.0), ("Fn", 1.0), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0)),
)


def _build_rows() -> tuple[tuple[KeyboardKey, ...], ...]:
    next_key_id = 0
    rows: list[tuple[KeyboardKey, ...]] = []
    for definitions in _ROW_DEFINITIONS:
        row: list[KeyboardKey] = []
        for label, width in definitions:
            row.append(KeyboardKey(next_key_id, label, width))
            next_key_id += 1
        rows.append(tuple(row))
    return tuple(rows)


AE64_LAYOUT = KeyboardLayout("everglide_ae64pro_64", "Everglide AE64 Pro 64-key layout", _build_rows())
PHYSICAL_KEYS = AE64_LAYOUT.keys

# Matrix rows in the protocol are one-based. Every physical row starts at
# column zero, matching the original driver's `position(key)` function.
KEY_ID_BY_POSITION = {
    (row_index, column): key.key_id
    for row_index, row in enumerate(AE64_LAYOUT.rows, start=1)
    for column, key in enumerate(row)
}
POSITION_BY_KEY_ID = {key_id: position for position, key_id in KEY_ID_BY_POSITION.items()}
AE64_MODELS = {(0x1CA6, 0x300A): "Everglide AE64 Pro"}
