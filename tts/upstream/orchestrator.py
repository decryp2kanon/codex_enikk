"""Single global gate and dispatch point for optional upstream normalizers.

The source adapters are imported only after the global switch is checked.
Yuki custom exceptions are always retained and never import optional upstream adapters.
"""
import importlib.util
import os
from pathlib import Path
import sys


def upstream_enabled():
    return os.environ.get('CODEX_ENIKK_TTS_UPSTREAM', '0') != '0'


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
        self._upstream_adapter = None
        self._selected = None
        self._sources_loaded = False

    @property
    def process(self):
        if self._upstream_adapter is None:
            return None
        if hasattr(self._upstream_adapter, 'process'):
            return self._upstream_adapter.process
        client = getattr(self._upstream_adapter, '_client', None)
        return None if client is None else client.process

    def upstream_status(self):
        enabled = upstream_enabled()
        return {
            'enabled': enabled,
            'source': 'explicit' if 'CODEX_ENIKK_TTS_UPSTREAM' in os.environ else 'default',
            'dictionary': bool(enabled and self._selected is not None),
            'adapter': bool(enabled and self._upstream_adapter is not None),
        }

    def _sources(self):
        # Global 0 is checked before either source module is loaded.
        if not upstream_enabled():
            return None, None
        if not self._sources_loaded:
            self._selected = _load_source(
                self.upstream_dir / 'selected_korean_dictionary.py',
                'yuki_selected_korean_dictionary')
            self._upstream_adapter = _load_source(
                self.upstream_dir / 'nemo_adapter.py', 'yuki_upstream_source_adapter')
            if self._upstream_adapter is None:
                raise RuntimeError('upstream source adapter is missing; set CODEX_ENIKK_TTS_UPSTREAM=0 for custom-only mode')
            self._sources_loaded = True
        return self._selected, self._upstream_adapter

    def initialize(self):
        if not upstream_enabled():
            self.close()
            return
        _, upstream_adapter = self._sources()
        if upstream_adapter is None:
            raise RuntimeError('upstream source adapter is unavailable; set CODEX_ENIKK_TTS_UPSTREAM=0 for custom-only mode')
        upstream_adapter.initialize()

    def normalize(self, text):
        if not isinstance(text, str):
            raise TypeError('text must be str')
        if len(text.encode('utf-8')) > 1024 * 1024:
            raise ValueError('normalization request too large')
        if not upstream_enabled():
            self.close()
            return self.custom.normalize_with_exceptions(text, lambda value: value)

        selected, upstream_adapter = self._sources()
        if selected is not None:
            text = selected.apply(text)
        # Preserve the established order: exact selected upstream dictionary,
        # Yuki protection/pre-fixes, upstream callback, then checked restoration.
        result = self.custom.normalize_with_exceptions(text, upstream_adapter.normalize)
        if text.strip() and not result.strip():
            raise RuntimeError('normalization returned empty text')
        return result

    def close(self):
        if self._upstream_adapter is not None:
            self._upstream_adapter.close()
            if sys.modules.get('yuki_upstream_source_adapter') is self._upstream_adapter:
                sys.modules.pop('yuki_upstream_source_adapter', None)
        if sys.modules.get('yuki_selected_korean_dictionary') is self._selected:
            sys.modules.pop('yuki_selected_korean_dictionary', None)
        self._upstream_adapter = None
        self._selected = None
        self._sources_loaded = False
