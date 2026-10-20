"""Explicit runtime paths for the three-module delivery (standard library only).

Relative values are resolved against the configuration file, never the shell's
working directory. Move the entire final bundle together, or set
ENERGY_PLATFORM_CONFIG to an explicit JSON file when using a module separately.
"""
from pathlib import Path
import json
import os
import string

MODULE_ROOT = Path(__file__).resolve().parent
DELIVERY_ROOT = MODULE_ROOT.parent if MODULE_ROOT.name in {'energy-topic-identification', 'energy-topic-hotspots', 'energy-technology-trl-crl'} else MODULE_ROOT
ENV_KEYS = {
    'data_root': 'ENERGY_DATA_ROOT', 'raw_data_dir': 'ENERGY_RAW_DATA_DIR',
    'corpus_dir': 'ENERGY_CORPUS_DIR', 'metadata_db': 'ENERGY_METADATA_DB',
    'keyword_sources': 'ENERGY_KEYWORD_SOURCES', 'bge_model_dir': 'ENERGY_BGE_MODEL_DIR',
    'bge_runtime_dir': 'ENERGY_BGE_RUNTIME_DIR', 'bge_core_dir': 'ENERGY_BGE_CORE_DIR',
    'classification_run': 'ENERGY_CLASSIFICATION_RUN', 'hotspots_run': 'ENERGY_FULL_HOTSPOTS_RUN',
    'maturity_run': 'ENERGY_MATURITY_RUN', 'context_dir': 'ENERGY_CONTEXT_DIR',
}


class RuntimePaths:
    def __init__(self, config_path=None, environ=None):
        self.env = dict(os.environ if environ is None else environ)
        self.config_path = Path(config_path or self.env.get('ENERGY_PLATFORM_CONFIG') or MODULE_ROOT/'config/runtime_paths.json').expanduser().resolve()
        if not self.config_path.is_file():
            raise FileNotFoundError(f'Runtime configuration missing: {self.config_path}; set ENERGY_PLATFORM_CONFIG')
        self.config = json.loads(self.config_path.read_text())
        if self.config.get('schema_version') != 1:
            raise ValueError('Unsupported runtime configuration schema_version')
        self.values = self.config['paths']
        self._resolved = {'delivery_root': DELIVERY_ROOT}
        self._resolving = set()

    def path(self, key):
        if key in self._resolved:
            return self._resolved[key]
        if key in self._resolving:
            raise ValueError('Cyclic runtime path: ' + key)
        self._resolving.add(key)
        try:
            value = self.env.get(ENV_KEYS.get(key, '')) or self.values.get(key)
            if key == 'classification_run':
                value = self.env.get('FULL_NMF_RUN') or value
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'Runtime path {key} is unset; configure {self.config_path}')
            fields = [f for _, f, _, _ in string.Formatter().parse(value) if f]
            value = value.format(**{k: str(self.path(k)) for k in fields})
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = self.config_path.parent/path
            self._resolved[key] = path.resolve()
            return self._resolved[key]
        finally:
            self._resolving.remove(key)

    def source_path(self, value):
        """Rebase embedded source paths only through explicitly configured prefixes."""
        original=Path(value).expanduser()
        for prefix,target in sorted(self.config.get('source_path_prefixes',{}).items(),key=lambda item:-len(item[0])):
            base=Path(prefix)
            if original.is_relative_to(base):
                fields=[f for _,f,_,_ in string.Formatter().parse(target) if f]
                mapped=Path(target.format(**{k:str(self.path(k)) for k in fields}))
                if not mapped.is_absolute():mapped=self.config_path.parent/mapped
                return (mapped/original.relative_to(base)).resolve()
        return original.resolve() if original.is_absolute() else (self.config_path.parent/original).resolve()

    def require(self, key, kind=None):
        path = self.path(key)
        valid = path.is_file() if kind == 'file' else path.is_dir() if kind == 'dir' else path.exists()
        if not valid:
            raise FileNotFoundError(f'Missing runtime input {key}: {path}; edit {self.config_path} or set {ENV_KEYS.get(key, "the corresponding override")}')
        return path

    def snapshot(self):
        return {'config_file':str(self.config_path), 'schema_version':1,
                'paths':{k:str(self.path(k)) for k in self.values},
                'windows':self.config['windows']}


def load_runtime(config_path=None, environ=None):
    return RuntimePaths(config_path, environ)
