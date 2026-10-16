"""JSON-file store with a process + file lock. Stdlib only.

Layout: <root>/{documents,employees,timesheets,runs,reviews,audit}.json (lists),
settings.json (dict) and uploads/.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional

_COLLECTIONS = ['documents', 'employees', 'timesheets', 'runs', 'reviews', 'audit']
_tlock = threading.RLock()


class Store:
    def __init__(self, root: Path, seed_fn: Optional[Callable[['Store'], None]] = None):
        self.root = Path(root)
        self.uploads = self.root / 'uploads'
        self.seed_fn = seed_fn
        self._lockfile = self.root / '.lock'
        self._depth = 0
        self.root.mkdir(parents=True, exist_ok=True)
        self.uploads.mkdir(parents=True, exist_ok=True)

    # ---- locking
    @contextmanager
    def lock(self, timeout: float = 15.0):
        """Re-entrant (per process) + cross-process lock."""
        with _tlock:
            if self._depth > 0:
                self._depth += 1
                try:
                    yield
                finally:
                    self._depth -= 1
                return
            start = time.time()
            fd = None
            while True:
                try:
                    fd = os.open(str(self._lockfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    break
                except FileExistsError:
                    try:  # stale lock (crashed writer)
                        if time.time() - self._lockfile.stat().st_mtime > 30:
                            self._lockfile.unlink()
                            continue
                    except OSError:
                        pass
                    if time.time() - start > timeout:
                        raise TimeoutError('tg_billing store lock timeout')
                    time.sleep(0.02)
            self._depth = 1
            try:
                yield
            finally:
                self._depth = 0
                try:
                    os.close(fd)
                finally:
                    try:
                        self._lockfile.unlink()
                    except OSError:
                        pass

    # ---- raw io
    def _path(self, name: str) -> Path:
        return self.root / f'{name}.json'

    def read(self, name: str, default: Any = None) -> Any:
        p = self._path(name)
        if not p.exists():
            return [] if default is None and name in _COLLECTIONS else default
        with open(p, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return [] if default is None and name in _COLLECTIONS else default

    def write(self, name: str, data: Any) -> None:
        p = self._path(name)
        tmp = p.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)

    # ---- seeding
    def ensure_seeded(self) -> None:
        with self.lock():
            if not self._path('documents').exists() and self.seed_fn:
                self.seed_fn(self)

    def reset(self) -> None:
        with self.lock():
            for n in _COLLECTIONS + ['settings']:
                p = self._path(n)
                if p.exists():
                    p.unlink()
            if self.seed_fn:
                self.seed_fn(self)

    # ---- helpers
    def all(self, name: str) -> list:
        self.ensure_seeded()
        with self.lock():
            return self.read(name, [])

    def get(self, name: str, id_: str, key: str = 'id') -> Optional[dict]:
        for x in self.all(name):
            if x.get(key) == id_:
                return x
        return None

    def save_item(self, name: str, item: dict, key: str = 'id') -> dict:
        self.ensure_seeded()
        with self.lock():
            items = self.read(name, [])
            for i, x in enumerate(items):
                if x.get(key) == item.get(key):
                    items[i] = item
                    break
            else:
                items.append(item)
            self.write(name, items)
        return item

    def delete_item(self, name: str, id_: str, key: str = 'id') -> bool:
        self.ensure_seeded()
        with self.lock():
            items = self.read(name, [])
            new = [x for x in items if x.get(key) != id_]
            if len(new) == len(items):
                return False
            self.write(name, new)
            return True

    def settings(self) -> dict:
        from .engine import merge_settings

        self.ensure_seeded()
        with self.lock():
            return merge_settings(self.read('settings', {}) or {})

    def save_settings(self, data: dict) -> dict:
        from .engine import merge_settings

        with self.lock():
            cur = self.read('settings', {}) or {}
            for k, v in data.items():
                if isinstance(v, dict) and isinstance(cur.get(k), dict):
                    cur[k].update(v)
                else:
                    cur[k] = v
            self.write('settings', cur)
            return merge_settings(cur)

    def audit(self, actor: str, action: str, detail: str, **extra) -> dict:
        from datetime import datetime, timezone

        with self.lock():
            items = self.read('audit', [])
            entry = {
                'id': f'AUD-{len(items) + 1:04d}',
                'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'actor': actor,
                'action': action,
                'detail': detail,
                **extra,
            }
            items.append(entry)
            self.write('audit', items)
            return entry
