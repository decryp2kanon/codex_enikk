#!/usr/bin/env python3
# 작성자: 에닉(유키짱)
"""Yuki custom text normalization only."""
import importlib.util
from pathlib import Path

_base = Path(__file__).resolve().parent
_override_spec = importlib.util.spec_from_file_location(
    "yuki_tn_overrides", _base / "yuki-text-normalization-overrides.py")
overrides = importlib.util.module_from_spec(_override_spec)
_override_spec.loader.exec_module(overrides)

class Client:
    def __init__(self, custom=None):
        self.custom = custom or overrides

    @property
    def process(self):
        return None

    def initialize(self):
        return None

    def normalize(self, text):
        if not isinstance(text, str):
            raise TypeError("text must be str")
        if len(text.encode("utf-8")) > 1024 * 1024:
            raise ValueError("normalization request too large")
        if self.custom is overrides:
            return self.custom.normalize_with_exceptions(text)
        # Preserve the callback contract for pre-existing injected custom modules.
        return self.custom.normalize_with_exceptions(text, lambda value: value)

    def close(self):
        return None

_service = Client()
initialize = _service.initialize
normalize = _service.normalize
close = _service.close

if __name__ == "__main__":
    initialize()
    close()

# EOF
