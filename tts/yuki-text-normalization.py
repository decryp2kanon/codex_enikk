#!/usr/bin/env python3
"""Yuki custom exceptions plus one removable upstream orchestration boundary."""
import importlib.util
from pathlib import Path
import sys

_base = Path(__file__).resolve().parent

_override_spec = importlib.util.spec_from_file_location(
    'yuki_tn_overrides', _base / 'yuki-text-normalization-overrides.py')
overrides = importlib.util.module_from_spec(_override_spec)
_override_spec.loader.exec_module(overrides)

# This is the only integration point. The orchestrator checks the global
# switch before loading any source adapter or starting an upstream process.
_orchestrator_spec = importlib.util.spec_from_file_location(
    'yuki_tn_upstream_orchestrator', _base / 'upstream' / 'orchestrator.py')
if _orchestrator_spec is None or _orchestrator_spec.loader is None:
    raise RuntimeError('TTS upstream orchestration module is missing')
_orchestrator = importlib.util.module_from_spec(_orchestrator_spec)
sys.modules[_orchestrator_spec.name] = _orchestrator
_orchestrator_spec.loader.exec_module(_orchestrator)

class Client(_orchestrator.Service):
    def __init__(self, custom=None, upstream_dir=None):
        super().__init__(custom or overrides, upstream_dir=upstream_dir or (_base / 'upstream'))


_service = Client()
initialize = _service.initialize
normalize = _service.normalize
close = _service.close


if __name__ == '__main__':
    # Compatibility: the NeMo adapter owns its own --serve entry point.
    if sys.argv[1:] == ['--serve']:
        raise SystemExit('NeMo serving moved to tts/upstream/nemo_adapter.py')
    initialize()
    close()
