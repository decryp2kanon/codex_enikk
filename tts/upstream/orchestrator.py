"""Single global gate and dispatch point for optional upstream normalizers.

The source adapters are imported only after the global switch is checked.
Yuki custom exceptions are always retained and never import NeMo.
"""
import importlib.util
import os
from pathlib import Path
import sys


def upstream_enabled():
    return os.environ.get('CODEX_ENIKK_TTS_UPSTREAM', '1') != '0'


def _load_source(path, module_name):
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'invalid upstream source adapter: {path.name}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except (FileNotFoundError, ModuleNotFoundError):
        return None
    return module


class Service:
    def __init__(self, custom, upstream_dir=None):
        self.custom = custom
        self.upstream_dir = Path(upstream_dir or Path(__file__).resolve().parent)
        self._nemo = None
        self._selected = None
        self._sources_loaded = False

    @property
    def process(self):
        if self._nemo is None:
            return None
        if hasattr(self._nemo, 'process'):
            return self._nemo.process
        client = getattr(self._nemo, '_client', None)
        return None if client is None else client.process

    def _sources(self):
        # Global 0 is checked before either source module is loaded.
        if not upstream_enabled():
            return None, None
        if not self._sources_loaded:
            self._selected = _load_source(
                self.upstream_dir / 'selected_korean_dictionary.py',
                'yuki_selected_korean_dictionary')
            self._nemo = _load_source(
                self.upstream_dir / 'nemo_adapter.py', 'yuki_nemo_source_adapter')
            if self._nemo is None:
                raise RuntimeError('NeMo source adapter is missing; set CODEX_ENIKK_TTS_UPSTREAM=0 for custom-only mode')
            self._sources_loaded = True
        return self._selected, self._nemo

    def initialize(self):
        if not upstream_enabled():
            self.close()
            return
        _, nemo = self._sources()
        if nemo is None:
            raise RuntimeError('NeMo source adapter is unavailable; set CODEX_ENIKK_TTS_UPSTREAM=0 for custom-only mode')
        nemo.initialize()

    def normalize(self, text):
        if not isinstance(text, str):
            raise TypeError('text must be str')
        if len(text.encode('utf-8')) > 1024 * 1024:
            raise ValueError('normalization request too large')
        if not upstream_enabled():
            self.close()
            return self.custom.normalize_with_exceptions(text, lambda value: value)

        selected, nemo = self._sources()
        if selected is not None:
            text = selected.apply(text)
        # Preserve the established order: exact selected upstream dictionary,
        # Yuki protection/pre-fixes, NeMo TN callback, then checked restoration.
        result = self.custom.normalize_with_exceptions(text, nemo.normalize)
        if text.strip() and not result.strip():
            raise RuntimeError('normalization returned empty text')
        return result

    def close(self):
        if self._nemo is not None:
            self._nemo.close()
            if sys.modules.get('yuki_nemo_source_adapter') is self._nemo:
                sys.modules.pop('yuki_nemo_source_adapter', None)
        if sys.modules.get('yuki_selected_korean_dictionary') is self._selected:
            sys.modules.pop('yuki_selected_korean_dictionary', None)
        self._nemo = None
        self._selected = None
        self._sources_loaded = False
