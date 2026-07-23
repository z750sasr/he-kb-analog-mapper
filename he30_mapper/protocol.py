"""Compatibility exports for code written before keyboard adapters existed.

New integrations should import from ``he30_mapper.keyboards``. Keeping this
module avoids breaking existing scripts and the original protocol tests.
"""

from .keyboards.he30.protocol import (
    HE30Error,
    HE30Protocol,
    MappingResolver,
    decode_profile_change_report,
    decode_telemetry_report,
)

__all__ = [
    "HE30Error",
    "HE30Protocol",
    "MappingResolver",
    "decode_profile_change_report",
    "decode_telemetry_report",
]
