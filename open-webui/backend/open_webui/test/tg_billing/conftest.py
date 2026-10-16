"""Loads utils/tg_billing as a standalone package so tests do not import the whole Open WebUI app."""

import importlib.util
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parents[2] / 'utils' / 'tg_billing'


def _load():
    if 'tg_billing_pkg' in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        'tg_billing_pkg', _PKG_DIR / '__init__.py', submodule_search_locations=[str(_PKG_DIR)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules['tg_billing_pkg'] = mod
    spec.loader.exec_module(mod)


_load()
