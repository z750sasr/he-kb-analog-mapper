"""EPOMAKER HE30-family adapter package."""

from .layout import HE30_LAYOUT

__all__ = ["HE30Adapter", "HE30_LAYOUT"]


def __getattr__(name: str):
    """Load the adapter lazily so layout metadata has no model dependency."""

    if name == "HE30Adapter":
        from .adapter import HE30Adapter

        return HE30Adapter
    raise AttributeError(name)
