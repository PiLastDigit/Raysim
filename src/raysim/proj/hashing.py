"""SHA-256 hashing of provenance inputs — Phase A.6.

Each provenance hash is the SHA-256 of a canonical JSON byte stream:
the same input produces the same hash on any platform, regardless of
dict-iteration order or float repr quirks. See ``canonical_json``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from raysim.proj.canonical_json import dumps as canonical_dumps


def hash_canonical(obj: Any) -> str:
    """Return the SHA-256 of ``obj`` rendered as compact canonical JSON."""
    payload = canonical_dumps(obj, indent=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_file(path: str | Path) -> str:
    """Stream-hash a file's bytes."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_files(paths: dict[str, str | Path]) -> str:
    """Hash a name → path mapping. The output depends on names + per-file SHA,
    not on dict iteration order."""
    return hash_canonical({str(k): hash_file(v) for k, v in paths.items()})
