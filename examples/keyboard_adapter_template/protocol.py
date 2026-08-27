"""Translate the manufacturer's WebHID behavior to hidapi here."""


class BrandProtocol:
    def __init__(self, hid_backend=None, preferred_id="auto"):
        self.hid_backend = hid_backend
        self.preferred_id = preferred_id

    def enumerate_candidates(self):
        """Return HID dictionaries for normal mapper-capable interfaces."""

        return ()

    def connect(self):
        raise NotImplementedError

    def prepare(self):
        raise NotImplementedError

    def read_event(self, timeout_ms=100):
        raise NotImplementedError

    def close(self):
        pass
