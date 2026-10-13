#!/usr/bin/env python3
"""Build and verify this reference package with an already installed backend."""
from __future__ import annotations

import argparse
import base64
import csv
from email.parser import BytesParser
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile


NAME = "multi-agent-fanout-engine"
VERSION = "0.1.0"
WHEEL_NAME = "multi_agent_fanout_engine-0.1.0-py3-none-any.whl"
DIST_INFO = "multi_agent_fanout_engine-0.1.0.dist-info/"
SOURCE_SCOPE = "Captured packaging input bytes; not Git commit/tree authentication."


class BuildError(ValueError):
    """The backend result could not be received as the captured package."""


def _json(value: object, *, newline: bool = False) -> bytes:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
    return (text + ("\n" if newline else "")).encode("utf-8")


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _pin(content: bytes) -> dict[str, object]:
    return {"bytes": len(content), "sha256": _sha(content)}


def _linked(path: Path) -> bool:
    info = path.lstat()
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def _directory(path: Path) -> None:
    if _linked(path) or not stat.S_ISDIR(path.stat().st_mode):
        raise ValueError(f"expected an ordinary nonlinked directory: {path}")


def _read(path: Path) -> bytes:
    if _linked(path) or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"expected an ordinary nonlinked file: {path}")
    return path.read_bytes()


def _capture(source: Path) -> dict[str, bytes]:
    _directory(source)
    for name in ("setup.py", "setup.cfg"):
        if os.path.lexists(source / name):
            raise ValueError(f"unsupported source configuration: {name}")
    files = {name: _read(source / name) for name in ("pyproject.toml", "README.md")}
    package = source / "fanout_engine"
    _directory(package)

    def visit(directory: Path) -> None:
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            if _linked(entry):
                raise ValueError(f"linked package entry is unsupported: {entry}")
            if entry.is_dir():
                if entry.name != "__pycache__":
                    visit(entry)
            elif entry.is_file() and entry.suffix == ".py":
                name = entry.relative_to(source).as_posix()
                if "\\" in name or ":" in name:
                    raise ValueError(f"unsupported package path: {name}")
                files[name] = _read(entry)
            else:
                raise ValueError(f"unsupported non-Python package entry: {entry}")

    visit(package)
    if "fanout_engine/__init__.py" not in files:
        raise ValueError("fanout_engine/__init__.py is required")
    return files


def _configuration(content: bytes) -> dict[str, str]:
    value = tomllib.loads(content.decode("utf-8"))
    backend = {"requires": ["setuptools>=61"], "build-backend": "setuptools.build_meta"}
    if set(value) != {"build-system", "project"} or value["build-system"] != backend:
        raise ValueError("only the maintained static setuptools>=61 build configuration is supported")
    project = value["project"]
    if (not isinstance(project, dict)
            or set(project) != {"name", "version", "description", "requires-python"}
            or project["name"] != NAME or project["version"] != VERSION
            or project["requires-python"] != ">=3.10"
            or not isinstance(project["description"], str)):
        raise ValueError("unsupported project metadata; use the maintained static reference configuration")
    return {"name": NAME, "version": VERSION, "requires_python": ">=3.10"}


def _versions() -> dict[str, str]:
    versions = {name: importlib.metadata.version(name) for name in ("pip", "setuptools", "wheel")}
    try:
        sufficient = int(versions["setuptools"].split(".", 1)[0]) >= 61
    except ValueError:
        sufficient = False
    if not sufficient:
        raise ValueError("installed setuptools>=61 is required; nothing will be downloaded")
    return versions


def _output_path(source: Path, output: Path) -> None:
    if os.path.lexists(output):
        raise ValueError("output must be a new directory")
    _directory(output.parent)
    if output.resolve().is_relative_to(source):
        raise ValueError("output must be outside the source directory")


def _verify_wheel(content: bytes, files: dict[str, bytes]) -> tuple[int, int]:
    modules = {name: data for name, data in files.items() if name.startswith("fanout_engine/")}
    expected = set(modules) | {DIST_INFO + name for name in ("METADATA", "WHEEL", "top_level.txt", "RECORD")}
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as wheel:
            names = wheel.namelist()
            if len(names) != len(set(names)) or set(names) != expected or wheel.testzip() is not None:
                raise BuildError("wheel membership or CRC differs from the captured package")
            if any(wheel.read(name) != data for name, data in modules.items()):
                raise BuildError("wheel Python bytes differ from the captured source")
            record_name = DIST_INFO + "RECORD"
            records = list(csv.reader(io.StringIO(wheel.read(record_name).decode("utf-8"))))
            if (any(len(row) != 3 for row in records) or len(records) != len(expected)
                    or {row[0] for row in records} != expected):
                raise BuildError("wheel RECORD membership differs")
            for name, digest, size in records:
                data = wheel.read(name)
                if name == record_name:
                    valid = digest == size == ""
                else:
                    encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
                    valid = digest == "sha256=" + encoded and size == str(len(data))
                if not valid:
                    raise BuildError(f"wheel RECORD differs: {name}")
            metadata = BytesParser().parsebytes(wheel.read(DIST_INFO + "METADATA"))
            wheel_metadata = BytesParser().parsebytes(wheel.read(DIST_INFO + "WHEEL"))
            if (metadata.get_all("Name") != [NAME] or metadata.get_all("Version") != [VERSION]
                    or metadata.get_all("Requires-Python") != [">=3.10"]
                    or metadata.get_all("Requires-Dist")
                    or wheel_metadata.get_all("Root-Is-Purelib") != ["true"]
                    or wheel_metadata.get_all("Tag") != ["py3-none-any"]
                    or wheel.read(DIST_INFO + "top_level.txt") != b"fanout_engine\n"):
                raise BuildError("wheel metadata differs from the maintained pure Python package")
    except (zipfile.BadZipFile, KeyError, UnicodeError, csv.Error) as exc:
        raise BuildError(f"cannot verify wheel: {exc}") from exc
    return len(modules), len(records)


def _build(source: Path, files: dict[str, bytes], project: dict[str, str],
           versions: dict[str, str], epoch: int, temporary_parent: Path) -> dict[str, bytes]:
    file_pins = {name: {**_pin(data), "git_blob": hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
        for name, data in files.items()}
    source_digest = _sha(_json(file_pins))
    with tempfile.TemporaryDirectory(prefix="fanout-offline-wheel-", dir=temporary_parent) as temporary:
        root = Path(temporary)
        captured = root / "source"
        captured.mkdir()
        dist = root / "dist"
        dist.mkdir()
        for name, data in files.items():
            destination = captured / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        env = {name: value for name, value in os.environ.items()
               if not name.startswith("PIP_") and name not in {"PYTHONPATH", "PYTHONHOME"}}
        env.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX="1", PIP_NO_CACHE_DIR="1",
                   PIP_NO_INPUT="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONHASHSEED="0",
                   SOURCE_DATE_EPOCH=str(epoch), TMPDIR=str(root))
        command = [sys.executable, "-I", "-B", "-m", "pip", "wheel", "--no-index", "--no-deps",
                   "--no-build-isolation", "--no-cache-dir", "--wheel-dir", str(dist), str(captured)]
        try:
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=90)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise BuildError(f"offline backend did not complete: {exc}") from exc
        if result.returncode:
            detail = result.stderr.decode("utf-8", "replace")[-4000:]
            raise BuildError(f"offline backend exited {result.returncode}: {detail}")
        outputs = list(dist.iterdir())
        if len(outputs) != 1 or outputs[0].name != WHEEL_NAME:
            raise BuildError("backend must produce exactly the expected wheel")
        content = _read(outputs[0])
        module_count, record_count = _verify_wheel(content, files)
        if _capture(source) != files:
            raise BuildError("source inputs changed during the build; no output will be published")
        manifest = {
            "schema_version": 1, "project": project,
            "source": {"directory": str(source), "files": file_pins, "digest": source_digest, "scope": SOURCE_SCOPE},
            "build": {"python": sys.version, "executable": sys.executable, "versions": versions,
                      "epoch": epoch, "command": command, "returncode": result.returncode,
                      "logs": {"stdout": _pin(result.stdout), "stderr": _pin(result.stderr)}},
            "wheel": {"filename": WHEEL_NAME, **_pin(content), "modules": module_count, "record_entries": record_count},
        }
        return {WHEEL_NAME: content, "source-build.json": _json(manifest, newline=True),
                "build.stdout": result.stdout, "build.stderr": result.stderr}


def _write_stdout(content: bytes) -> None:
    if sys.stdout is None or getattr(sys.stdout, "buffer", None) is None:
        raise OSError("binary standard output is unavailable")
    try:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
    except OSError:
        try:
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        raise


def _epoch(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("epoch must be an integer") from exc
    if not 315532800 <= number <= 4102444799:
        raise argparse.ArgumentTypeError("epoch must be between 315532800 and 4102444799 inclusive")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True, help="new directory outside the source")
    parser.add_argument("--epoch", type=_epoch, required=True, help="explicit SOURCE_DATE_EPOCH")
    args = parser.parse_args(argv)
    try:
        _directory(args.source)
        source = args.source.resolve(strict=True)
        files = _capture(source)
        project = _configuration(files["pyproject.toml"])
        versions = _versions()
        temporary_parent = Path(tempfile.gettempdir()).resolve(strict=True)
        _directory(temporary_parent)
        if temporary_parent.is_relative_to(source):
            raise ValueError("temporary directory must be outside the selected source")
        _json({"source": str(source), "output": str(args.output)})
    except (OSError, ValueError, UnicodeError, importlib.metadata.PackageNotFoundError) as exc:
        print(f"fanout wheel: admission failed: {exc}", file=sys.stderr)
        return 2
    try:
        _output_path(source, args.output)
    except (OSError, ValueError) as exc:
        print(f"fanout wheel: output refused before build: {exc}", file=sys.stderr)
        return 1
    try:
        payloads = _build(source, files, project, versions, args.epoch, temporary_parent)
        manifest = json.loads(payloads["source-build.json"])
        complete = _json({"schema_version": 1, "output": str(args.output), "wheel_filename": WHEEL_NAME,
                          "wheel_bytes": len(payloads[WHEEL_NAME]), "wheel_sha256": _sha(payloads[WHEEL_NAME]),
                          "source_digest": manifest["source"]["digest"],
                          "manifest_sha256": _sha(payloads["source-build.json"])}, newline=True)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"fanout wheel: build or verification failed; no output published: {exc}", file=sys.stderr)
        return 3
    try:
        _output_path(source, args.output)
        args.output.mkdir()
        for name, content in payloads.items():
            destination = args.output / name
            with destination.open("xb") as stream:
                stream.write(content)
            if destination.read_bytes() != content:
                raise OSError(f"output readback differs: {name}")
        with (args.output / "COMPLETE.json").open("xb") as stream:
            stream.write(complete)
        if (args.output / "COMPLETE.json").read_bytes() != complete:
            raise OSError("completion readback differs")
    except (OSError, ValueError) as exc:
        print(f"fanout wheel: publication did not complete normally: {exc}; inspect output before retrying", file=sys.stderr)
        return 1
    try:
        _write_stdout(complete)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"fanout wheel: output was published; confirmation failed: {exc}; inspect output before retrying", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
