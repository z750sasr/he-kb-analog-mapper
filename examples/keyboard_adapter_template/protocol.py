"""Translate the manufacturer's WebHID behavior to hidapi here."""


class BrandProtocol:
    def connect(self):
        raise NotImplementedError

    def prepare(self):
        raise NotImplementedError

    def read_event(self, timeout_ms=100):
        raise NotImplementedError

    def close(self):
        pass
