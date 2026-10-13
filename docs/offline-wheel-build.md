# Build an offline wheel from captured source

The maintained producer builds this reference package with an already installed
Python packaging backend. It captures the packaging inputs in a private
directory, builds without an index or dependency installation, verifies the
wheel against those inputs, and publishes a new output directory.

The producer requires **Python 3.11 or later**, with `pip`, `setuptools>=61`,
and `wheel` already installed in that interpreter. The packaged library keeps
its existing Python 3.10 minimum. A missing prerequisite is a refusal; this
command does not install one.

## Build and receive the result

From the repository root, select a new directory outside the source checkout:

```sh
python tools/build_offline_wheel.py --output ../fanout-wheel --epoch 1791905209
```

The output parent must already exist. To use an explicitly selected source
directory, add `--source /path/to/source`. The source default is the repository
root containing the producer. Relative paths are interpreted from the caller's
working directory. A successful command prints one canonical UTF-8 JSON object
followed by a newline.

The epoch is required and becomes `SOURCE_DATE_EPOCH` for the backend. Accepted
integers run from 315532800 through 4102444799 inclusive (1980 through 2099 UTC).
Choose and retain the intended value with the source receipt. The example
value is a recorded qualification input, not an automatically discovered source
date. Equal source and epoch do not by themselves promise identical wheel
bytes across Python or backend versions.

The new output directory contains exactly these five files:

| File | Purpose |
| --- | --- |
| `multi_agent_fanout_engine-0.1.0-py3-none-any.whl` | Verified pure Python distribution |
| `source-build.json` | Captured source identities, producer environment, backend command and artifact hashes |
| `build.stdout` | Complete successful backend standard output |
| `build.stderr` | Complete successful backend standard error |
| `COMPLETE.json` | Final confirmation, written after the other four files and their byte readbacks |

Standard output is byte-identical to `COMPLETE.json`. It has exactly
`schema_version`, `output`, `wheel_filename`, `wheel_bytes`, `wheel_sha256`,
`source_digest`, and `manifest_sha256`. The output spelling is
`str(Path(the_supplied_argument))`; the manifest records the resolved source
directory separately.

A filename alone is not a successful receiving check. Parse the complete JSON,
check the exact manifest SHA-256, then verify the wheel, both logs and captured
source map against their recorded lengths and hashes. A failed or interrupted
publication can leave partial files, including a partial completion file.
Retain such an output for inspection and choose a different new directory for
a subsequent attempt.

## Install the selected artifact

Version 0.1.0 is shared by historical source snapshots. Use a fresh virtual
environment and retain the selected wheel hash and source manifest:

```sh
python -m venv ../fanout-installed
../fanout-installed/bin/python -m pip install --no-index --no-deps ../fanout-wheel/multi_agent_fanout_engine-0.1.0-py3-none-any.whl
../fanout-installed/bin/python -I -B -m fanout_engine.inspect --help
```

On Windows, use `../fanout-installed/Scripts/python.exe` for the environment's
interpreter. The installed package contains the runtime modules, not this
repository build script. Creating the environment and installing the already
produced wheel are separate operations; the producer does neither.

## Admitted source and configuration

The source root, `README.md`, `pyproject.toml`, package root, and all captured
package entries must be ordinary files or directories. Symbolic links and
Windows reparse points at those entries are refused. Ancestor path resolution
does not authenticate a source origin.

The captured input consists of `README.md`, `pyproject.toml`, and every
`.py` file beneath `fanout_engine`, including nested packages.
`fanout_engine/__init__.py` is required. Ordinary `__pycache__` directories
are ignored; a linked cache is refused. Non-Python package payloads and linked
package entries are refused. Root `setup.py` or `setup.cfg` is refused.
Unrelated root files, such as tests and this guide, are not packaging inputs.

Only the current static project configuration is accepted:

- Exactly `[build-system]` and `[project]` at the top level.
- Build requirement `["setuptools>=61"]` and backend `setuptools.build_meta`.
- Project name `multi-agent-fanout-engine`, version `0.1.0`,
  `requires-python = ">=3.10"`, and a text description.
- No other project keys, backend paths, dynamic metadata, extra requirements,
  setup scripts, or tool configuration.

This intentionally small admission contract is for this maintained reference
package. A future packaging configuration change needs a corresponding reviewed
producer change. It is not a general build frontend.

## What is checked

The selected temporary parent (including an inherited `TMPDIR` selection) must
resolve outside the source root. An inside-source temporary parent is refused
before any backend call or output creation. The checked parent is then passed
explicitly to private staging.

Before the backend runs, the producer reads the complete admitted file set.
Only those captured bytes are copied into a private temporary directory. The
command uses the current interpreter with isolated mode and these pip options:
`wheel --no-index --no-deps --no-build-isolation --no-cache-dir`.
It removes inherited `PIP_*`, `PYTHONPATH`, and `PYTHONHOME` settings, disables
pip configuration and version checks, supplies `PYTHONHASHSEED=0` in the
environment, and sets the requested epoch. Python isolated mode ignores
`PYTHON*` variables in the pip interpreter itself; supplying that environment
value does not guarantee a fixed hash seed in every process. See the
[Python isolated-mode documentation](https://docs.python.org/3.12/using/cmdline.html#cmdoption-I).
Installed backend versions are recorded. The backend has a 90-second timeout.

The produced wheel must have the expected filename and exactly the captured
Python paths plus its four distribution metadata files. Verification checks
unique ZIP membership and CRC, every Python byte, each SHA-256 RECORD entry and
size, the blank RECORD self-entry, package name/version/Python requirement,
absence of runtime dependency metadata, the pure-library flag, and the
`py3-none-any` tag. Source modules are not imported to perform these checks.

After wheel verification, the complete admitted source membership and bytes are
read again. A detected source change refuses publication. Destination admission
is also repeated immediately before an exclusive directory creation. These
checks support ordinary stable paths; they do not provide an atomic filesystem
snapshot or protect against a hostile concurrent namespace change.

The destination must not already exist, even as a broken link, and its existing
parent must be an ordinary nonlinked directory. Its resolved path must be
outside the source root. Existing destinations are never overwritten. A
publication failure leaves the newly created partial output in place for
inspection rather than deleting it.

## Manifest format and identity boundary

`source-build.json` has `schema_version: 1`, `project`, `source`,
`build`, and `wheel`.

- `source.files` maps each relative captured path to integer `bytes`,
  hexadecimal `sha256`, and the Git blob SHA-1 computed from those exact bytes.
- `source.digest` is SHA-256 of that files map encoded as compact sorted-key
  UTF-8 JSON, with no trailing newline.
- `source.directory` is the resolved source spelling, and `source.scope` is
  exactly `Captured packaging input bytes; not Git commit/tree authentication.`
- `build.python` is `sys.version`, `build.executable` is the producer
  interpreter, and `build.versions` maps `pip`, `setuptools`, and `wheel`
  to their installed version strings.
- `build.epoch` and `build.returncode` are integers; `build.command` is
  the actual argument array. Its private temporary paths are historical
  execution details and disappear when the build finishes.
- `build.logs.stdout` and `build.logs.stderr` each contain integer
  `bytes` and hexadecimal `sha256`.
- `wheel` contains `filename`, integer `bytes`, hexadecimal `sha256`,
  integer `modules`, and integer `record_entries`.

Manifest, completion and stdout JSON use sorted keys, compact separators,
literal Unicode, and one final newline. The completion's manifest hash covers
that newline.

These hashes bind the captured content. They do not establish a repository
commit, current branch, clean working tree, source author or remote publication.
When a Git source pin matters, separately receive the commit/tree and compare
the recorded blob IDs with that qualified source. Byte-for-byte wheel
reproducibility likewise needs a qualified source, epoch and toolchain
comparison; this receipt makes those inputs inspectable.

## Exit status and failure stages

| Status | Meaning |
| --- | --- |
| 0 | Build verified, five files published and confirmation written |
| 1 | Destination admission, publication, or confirmation failure |
| 2 | Arguments, source/configuration, or installed prerequisite refused before build |
| 3 | Backend failure/timeout, invalid wheel, or changed source; no output published |

An occupied or inadmissible destination is refused before a build. A later
publication error may leave some or all output files; the diagnostic asks you
to inspect the output before retrying. If standard output fails after successful
publication, the diagnostic explicitly says that output was published. Inspect
the retained artifact instead of blindly repeating the command against it.

## Focused regression checks

```sh
python -B -m unittest discover -s tests -p 'test_offline_wheel_b3d7b32e.py' -v
python -O -B -m unittest discover -s tests -p 'test_offline_wheel_b3d7b32e.py' -v
```

The focused tests exercise admission, captured-copy/environment handling,
independently constructed wheel corruption, source changes, output competition,
partial publication and confirmation failure. They also execute a real
no-site interpreter refusal. Backend fixture tests do not install dependencies
or import captured package modules. The class is skipped on Python 3.10 because
the producer itself requires Python 3.11+.
