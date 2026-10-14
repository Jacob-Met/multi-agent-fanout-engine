"""Read-only native identity helpers for this finite receiving course."""
import hashlib
import json
import os
import stat
from pathlib import Path


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def meta(value):
    return {key: getattr(value, "st_" + key)
            for key in ("dev", "ino", "mode", "uid", "gid", "mtime_ns", "size")}


def identity(path):
    path = Path(path)
    try:
        initial = path.lstat()
    except FileNotFoundError:
        return {"absent": True}
    row = meta(initial)
    if stat.S_ISREG(initial.st_mode):
        row.update(pin(path.read_bytes()))
    elif stat.S_ISLNK(initial.st_mode):
        row["target"] = os.readlink(path)
    elif stat.S_ISDIR(initial.st_mode):
        row["directory"] = True
    else:
        raise RuntimeError("unsupported path: " + str(path))
    if meta(path.lstat()) != meta(initial):
        raise RuntimeError("path changed during identity read: " + str(path))
    return row


def tree(root):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("expected real directory: " + str(root))
    return {str(path.relative_to(root)): identity(path) for path in sorted(root.rglob("*"))}


def state(config):
    return {"protected": {p: identity(p) for p in config["protected"]},
            "inputs": {p: identity(p) for p in config["inputs"]},
            "roots": {p: tree(p) for p in config["roots"]}}


def save(path, value):
    with Path(path).open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
