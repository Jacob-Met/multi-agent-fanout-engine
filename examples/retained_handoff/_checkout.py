"""Record the local files used by this example without requiring an installed package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent
CHECKOUT = EXAMPLE.parents[1]


def capture_source():
    """Return a portable observation of runtime inputs, not a Git commit claim."""
    engine = CHECKOUT / "fanout_engine"
    if not (engine / "__init__.py").is_file():
        raise RuntimeError("Run this example inside a fanout repository checkout")
    paths = list(engine.rglob("*.py")) + list(EXAMPLE.glob("*.py"))
    paths += [path for path in (EXAMPLE / "fixtures").rglob("*") if path.is_file()]
    files = []
    for path in sorted(paths):
        data = path.read_bytes()
        files.append({"path": path.relative_to(CHECKOUT).as_posix(), "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(),
                      "blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
    encoded = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"schema_version": 1, "kind": "observed-checkout-files", "files": files,
            "manifest_sha256": hashlib.sha256(encoded).hexdigest()}
