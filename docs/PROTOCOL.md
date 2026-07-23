# HE30 analog-report notes

These details were carried over from the capture-derived EPOMAKER HE30 alternate
web driver. They are intentionally isolated in
`he_keyboard_mapper/keyboards/he30/protocol.py` so UI and controller code never
manipulate raw firmware bytes.

## Normal devices

| VID:PID | Model | Profiles |
| --- | --- | --- |
| `19F5:FB4C` | EPOMAKER HE30 | 3 |

Only normal configuration devices are listed. Updater and bootloader interfaces
are deliberately unsupported.

## `0xA0` Hall telemetry

| Byte | Meaning |
| --- | --- |
| 0 | `0xA0` report marker |
| 1 | current mapping type |
| 2 | mapping `code1` |
| 3 | mapping `code2` |
| 6 | raw travel high byte |
| 7 | raw travel low byte |
| 10 | firmware key status |

Raw travel is therefore `(report[6] << 8) | report[7]`. Earlier generic code in
this repository incorrectly used bytes 3–5.

Because bytes 1–3 describe the current output mapping, the mapper reads the
384-byte mapping bank for every profile/layer and builds a reverse lookup to the
physical 128-slot key bank.

## `0xA1` profile/layer reports

Some firmware reports a local layer in byte 1 and profile in byte 2. Other
firmware reports the global layer (`0–11`) directly in byte 1. The decoder accepts
both forms and tracks the active local mapping bank used for physical resolution.

## Dynamic Display

Config byte 7 bit 3 controls the diagnostic stream. Each profile has a 64-byte
config block at `profile * 64`, read with subcommand 5 and written with subcommand
6. The mapper records which profiles originally had the bit clear, sets and
verifies only that bit, then clears only those recorded flags during cleanup.

Persistent configuration writes are chunked into at most 56 data bytes and are
always verified by an immediate read-back.
