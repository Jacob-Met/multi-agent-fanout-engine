"""Bounded producer admission, artifact verification and publication regressions."""
from pathlib import Path
import base64
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.version_info >= (3, 11), "the offline build tool requires Python 3.11+")
class OfflineWheelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("offline_wheel_under_test", ROOT / "tools/build_offline_wheel.py")
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fanout-wheel-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "fanout_engine").mkdir()
        self.inputs = {
            "README.md": b"# Authored build fixture\n",
            "pyproject.toml": (ROOT / "pyproject.toml").read_bytes(),
            "fanout_engine/__init__.py": b"raise RuntimeError('source must not be imported by producer')\n",
            "fanout_engine/example.py": b"VALUE = 'fixture'\n",
        }
        for name, data in self.inputs.items():
            (self.source / name).write_bytes(data)
        self.output = self.root / "built"
        self.versions = {"pip": "26.2.1", "setuptools": "84.0.0", "wheel": "0.48.0"}

    def argv(self):
        return ["--source", str(self.source), "--output", str(self.output), "--epoch", "1791905209"]

    def wheel(self, *, changed=False, bad_record=False, extra=False, duplicate=False, metadata=False):
        dist = "multi_agent_fanout_engine-0.1.0.dist-info/"
        data = {name: body for name, body in self.inputs.items() if name.startswith("fanout_engine/")}
        if changed:
            data["fanout_engine/example.py"] = b"VALUE = 'different, with valid recomputed RECORD'\n"
        data[dist + "METADATA"] = ("Metadata-Version: 2.4\nName: multi-agent-fanout-engine\nVersion: 0.1.0\nRequires-Python: >=3.10\n"
                                    + ("Requires-Dist: unwanted\n" if metadata else "") + "\n").encode()
        data[dist + "WHEEL"] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        data[dist + "top_level.txt"] = b"fanout_engine\n"
        if extra:
            data["unrequested.txt"] = b"extra payload"
        stream = io.StringIO(newline="")
        rows = csv.writer(stream)
        for name, body in data.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
            rows.writerow((name, "sha256=" + digest, len(body)))
        rows.writerow((dist + "RECORD", "", ""))
        data[dist + "RECORD"] = stream.getvalue().encode()
        if bad_record:
            data[dist + "RECORD"] = data[dist + "RECORD"].replace(b"sha256=", b"sha512=", 1)
        target = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, body in data.items():
                    archive.writestr(name, body)
                if duplicate:
                    archive.writestr(dist + "WHEEL", data[dist + "WHEEL"])
        return target.getvalue()

    def backend(self, wheel=None, after=None):
        body = self.wheel() if wheel is None else wheel

        def run(argv, **kwargs):
            self.assertEqual(argv[:9], [sys.executable, "-I", "-B", "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation"])
            captured = Path(argv[-1])
            self.assertNotEqual(captured, self.source)
            for name, data in self.inputs.items():
                self.assertEqual((captured / name).read_bytes(), data)
            env = kwargs["env"]
            self.assertNotIn("PIP_FIND_LINKS", env)
            self.assertNotIn("PIP_INDEX_URL", env)
            self.assertNotIn("PYTHONPATH", env)
            self.assertNotIn("PYTHONHOME", env)
            self.assertEqual(env["PIP_CONFIG_FILE"], os.devnull)
            self.assertEqual(env["SOURCE_DATE_EPOCH"], "1791905209")
            self.assertEqual(kwargs["timeout"], 90)
            dist = Path(argv[argv.index("--wheel-dir") + 1])
            (dist / self.tool.WHEEL_NAME).write_bytes(body)
            if after:
                after()
            return subprocess.CompletedProcess(argv, 0, b"authored backend stdout\n", b"authored backend stderr\n")
        return run

    def invoke(self, backend=None, stdout=None):
        captured = []
        sink = io.StringIO()
        with mock.patch.object(self.tool, "_versions", return_value=self.versions), \
             mock.patch.object(self.tool.subprocess, "run", side_effect=backend or self.backend()) as called, \
             mock.patch.object(self.tool, "_write_stdout", side_effect=stdout or captured.append), \
             contextlib.redirect_stderr(sink):
            result = self.tool.main(self.argv())
        return result, sink.getvalue(), captured, called.call_count

    def test_verified_output_and_complete_receipt(self):
        cache = self.source / "fanout_engine/__pycache__"
        cache.mkdir()
        (cache / "ignored.pyc").write_bytes(b"not a packaging input")
        with mock.patch.dict(os.environ, {"PIP_FIND_LINKS": "https://unused.invalid", "PIP_INDEX_URL": "https://unused.invalid", "PYTHONPATH": "not-used", "PYTHONHOME": "not-used"}):
            code, error, output, calls = self.invoke()
        self.assertEqual((code, error, calls), (0, "", 1))
        self.assertEqual(set(p.name for p in self.output.iterdir()), {self.tool.WHEEL_NAME, "source-build.json", "build.stdout", "build.stderr", "COMPLETE.json"})
        complete = (self.output / "COMPLETE.json").read_bytes()
        self.assertEqual(output, [complete])
        receipt = json.loads(complete)
        self.assertEqual(set(receipt), {"schema_version", "output", "wheel_filename", "wheel_bytes", "wheel_sha256", "source_digest", "manifest_sha256"})
        manifest_bytes = (self.output / "source-build.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        self.assertEqual(receipt["manifest_sha256"], hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(manifest["source"]["directory"], str(self.source.resolve()))
        self.assertEqual(set(manifest["source"]["files"]), set(self.inputs))
        self.assertEqual(manifest["wheel"]["modules"], 2)
        self.assertEqual(manifest["wheel"]["record_entries"], 6)
        for name, body in self.inputs.items():
            self.assertEqual((self.source / name).read_bytes(), body)

    def test_occupied_inside_and_missing_parent_refuse_before_backend(self):
        destinations = [self.output, self.source / "output", self.root / "absent" / "output"]
        self.output.mkdir()
        (self.output / "keep").write_bytes(b"existing")
        for destination in destinations:
            with self.subTest(destination=destination):
                self.output = destination
                code, _, stdout, calls = self.invoke()
                self.assertEqual((code, stdout, calls), (1, [], 0))
        self.assertEqual((self.root / "built" / "keep").read_bytes(), b"existing")

    def test_epoch_range_is_argument_admission(self):
        for value in ("315532799", "4102444800", "not-an-integer"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                self.tool.main(self.argv()[:-1] + [value])
            self.assertEqual(exc.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_extra_payload_and_setup_configuration_refuse(self):
        for relative in ("fanout_engine/data.json", "setup.py", "setup.cfg"):
            path = self.source / relative
            path.write_bytes(b"not admitted")
            code, _, stdout, calls = self.invoke()
            self.assertEqual((code, stdout, calls), (2, [], 0))
            path.unlink()
        self.assertFalse(self.output.exists())

    def test_linked_package_entries_refuse_without_reading(self):
        target = self.root / "external"
        target.mkdir()
        for name in ("linked.py", "linked_directory", "__pycache__"):
            link = self.source / "fanout_engine" / name
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            code, _, stdout, calls = self.invoke()
            self.assertEqual((code, stdout, calls), (2, [], 0))
            link.unlink()

    def test_nonallowlisted_metadata_refuses(self):
        original = self.inputs["pyproject.toml"]
        for suffix in (b'\n[tool.setuptools]\npackages=["fanout_engine"]\n', b'\ndynamic=["dependencies"]\n'):
            (self.source / "pyproject.toml").write_bytes(original + suffix)
            code, _, stdout, calls = self.invoke()
            self.assertEqual((code, stdout, calls), (2, [], 0))
        (self.source / "pyproject.toml").write_bytes(original.replace(b'setuptools>=61', b'setuptools>=999'))
        code, _, stdout, calls = self.invoke()
        self.assertEqual((code, stdout, calls), (2, [], 0))

    def test_temporary_parent_inside_source_refuses_before_backend(self):
        with mock.patch.object(self.tool.tempfile, "gettempdir", return_value=str(self.source)):
            code, error, stdout, calls = self.invoke()
        self.assertEqual((code, stdout, calls), (2, [], 0))
        self.assertIn("temporary directory must be outside", error)
        self.assertFalse(self.output.exists())
        self.assertEqual(set(self.tool._capture(self.source)), set(self.inputs))

    def test_missing_installed_prerequisite_does_not_fetch(self):
        with mock.patch.object(self.tool, "_versions", side_effect=self.tool.importlib.metadata.PackageNotFoundError("setuptools")), \
             mock.patch.object(self.tool.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.tool.main(self.argv()), 2)
        run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_actual_no_site_interpreter_refuses_before_build(self):
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(ROOT / "tools/build_offline_wheel.py"), *self.argv()], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertFalse(self.output.exists())

    def test_backend_error_and_timeout_publish_nothing(self):
        outcomes = [lambda argv, **kw: subprocess.CompletedProcess(argv, 7, b"partial stdout", b"backend refused"),
                    lambda argv, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired(argv, 90))]
        for backend in outcomes:
            with self.subTest(backend=backend):
                code, _, stdout, calls = self.invoke(backend)
                self.assertEqual((code, stdout, calls), (3, [], 1))
                self.assertFalse(self.output.exists())

    def test_self_consistent_altered_module_is_rejected(self):
        code, error, stdout, calls = self.invoke(self.backend(self.wheel(changed=True)))
        self.assertEqual((code, stdout, calls), (3, [], 1))
        self.assertIn("Python bytes differ", error)
        self.assertFalse(self.output.exists())

    def test_record_metadata_extra_and_duplicate_failures(self):
        for flags in ({"bad_record": True}, {"metadata": True}, {"extra": True}, {"duplicate": True}):
            with self.subTest(flags=flags):
                code, _, stdout, calls = self.invoke(self.backend(self.wheel(**flags)))
                self.assertEqual((code, stdout, calls), (3, [], 1))
                self.assertFalse(self.output.exists())

    def test_source_change_during_build_prevents_publication(self):
        def change():
            (self.source / "README.md").write_bytes(b"concurrent source edit\n")
        code, error, stdout, calls = self.invoke(self.backend(after=change))
        self.assertEqual((code, stdout, calls), (3, [], 1))
        self.assertIn("source inputs changed", error)
        self.assertFalse(self.output.exists())

    def test_competing_destination_is_preserved(self):
        def occupy():
            self.output.mkdir()
            (self.output / "keep").write_bytes(b"other publisher")
        code, error, stdout, calls = self.invoke(self.backend(after=occupy))
        self.assertEqual((code, stdout, calls), (1, [], 1))
        self.assertIn("inspect output before retrying", error)
        self.assertEqual({p.name for p in self.output.iterdir()}, {"keep"})
        self.assertEqual((self.output / "keep").read_bytes(), b"other publisher")

    def test_partial_publication_is_retained_without_success(self):
        original_open = Path.open
        def opening(path, *args, **kwargs):
            if path == self.output / "COMPLETE.json" and args == ("xb",):
                raise OSError("controlled completion-write refusal")
            return original_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", opening):
            code, error, stdout, calls = self.invoke()
        self.assertEqual((code, stdout, calls), (1, [], 1))
        self.assertIn("inspect output before retrying", error)
        self.assertTrue((self.output / self.tool.WHEEL_NAME).is_file())
        self.assertFalse((self.output / "COMPLETE.json").exists())

    def test_confirmation_failure_preserves_complete_artifact(self):
        def fail(content):
            raise OSError("controlled stdout failure")
        code, error, stdout, calls = self.invoke(stdout=fail)
        self.assertEqual((code, stdout, calls), (1, [], 1))
        self.assertIn("output was published", error)
        self.assertIn("inspect output before retrying", error)
        receipt = json.loads((self.output / "COMPLETE.json").read_bytes())
        wheel = (self.output / receipt["wheel_filename"]).read_bytes()
        self.assertEqual(hashlib.sha256(wheel).hexdigest(), receipt["wheel_sha256"])


if __name__ == "__main__":
    unittest.main()
