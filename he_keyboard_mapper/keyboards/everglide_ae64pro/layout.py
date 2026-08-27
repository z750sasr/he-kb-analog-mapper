"""Physical AE64 Pro matrix extracted from the companion WebHID driver."""

from __future__ import annotations

from ..base import KeyboardKey, KeyboardLayout


# The firmware addresses its five physical rows as 1..5. Key IDs remain a
# stable, compact 0..63 sequence for the mapper configuration and UI.
#
# Important: AE64 route-data columns are not the same as "the next key in the
# visual row." The firmware keeps empty matrix slots where wide keys live. For
# example, left Shift is two units wide, so Z is reported at matrix column 2,
# not column 1. Treating visual order as matrix order shifts Z->X, X->C, and
# drops keys such as the wide Enter that land in a skipped matrix column.
_ROW_DEFINITIONS = (
    (("Esc", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0), ("6", 1.0), ("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("Backspace", 2.0)),
    (("Tab", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0), ("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.5)),
    (("Caps", 1.75), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0), ("G", 1.0), ("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 2.25)),
    (("Shift", 2.0), ("Z", 1.0), ("X", 1.0), ("C", 1.0), ("V", 1.0), ("B", 1.0), ("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("Shift", 1.0), ("Up", 1.0), ("Del", 1.0)),
    (("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("Space", 6.25), ("Alt", 1.0), ("Fn", 1.0), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0)),
)


def _matrix_column(unit_offset: float) -> int:
    """Convert a visual x offset in keyboard units to a firmware matrix column."""

    # Python's built-in round() uses banker's rounding, so 2.5 would round down
    # to 2. Firmware columns are laid out on the nearest one-unit key grid, so
    # use explicit half-up rounding instead.
    return int(unit_offset + 0.5)


def _build_layout() -> tuple[tuple[tuple[KeyboardKey, ...], ...], dict[tuple[int, int], int]]:
    next_key_id = 0
    rows: list[tuple[KeyboardKey, ...]] = []
    key_id_by_position: dict[tuple[int, int], int] = {}
    for row_index, definitions in enumerate(_ROW_DEFINITIONS, start=1):
        row: list[KeyboardKey] = []
        unit_offset = 0.0
        for label, width in definitions:
            key = KeyboardKey(next_key_id, label, width)
            row.append(key)
            key_id_by_position[(row_index, _matrix_column(unit_offset))] = key.key_id
            next_key_id += 1
            unit_offset += width
        rows.append(tuple(row))
    return tuple(rows), key_id_by_position


_ROWS, KEY_ID_BY_POSITION = _build_layout()

AE64_LAYOUT = KeyboardLayout("everglide_ae64pro_64", "Everglide AE64 Pro 64-key layout", _ROWS)
PHYSICAL_KEYS = AE64_LAYOUT.keys

POSITION_BY_KEY_ID = {key_id: position for position, key_id in KEY_ID_BY_POSITION.items()}
AE64_MODELS = {(0x1CA6, 0x300A): "Everglide AE64 Pro"}
