# Missing stdout in read-only command reports

The authored-plan preview and retained project inspectors can be run with no standard-output stream. This occurs, for example, when Python starts with descriptor 1 closed on a POSIX system. A report cannot be written there, so the commands now return their existing output-refusal status with a useful stderr diagnostic. They do not print an AttributeError traceback.

## Existing command contracts remain distinct

| Command | Unavailable stdout status | Diagnostic prefix |
| --- | ---: | --- |
| `python -m fanout_engine.preview` | 2 | `fanout preview:` |
| `python -m fanout_engine.inspect` | 1 | `fanout inspect: cannot write report:` |
| `python -m fanout_engine.history` | 1 | `fanout history: cannot write report:` |
| `python -m fanout_engine.projects` | 1 | `fanout projects: cannot write catalog:` |

The diagnostic identifies that standard output is unavailable. Preview already groups output errors with its admission/read errors; the other three commands already have a separate output-error status. This repair preserves those conventions.

Input validation and report preparation still precede output. An invalid input therefore keeps its existing diagnostic and status even if stdout is absent. This change makes no routing, identity, report-schema, ledger-read, export-path or dispatch change. It does not change whether a command supports an explicit output file.

For preview, inspect and projects, a valid `--output NEW_FILE` can still publish a report when stdout is absent. Existing no-overwrite and output-path controls remain in place. History has no output-file option in the reviewed source. Use the existing command help and guides for their argument contracts.

Normal stdout reports are unchanged. An existing stream that fails during writing or flushing still follows the existing OSError path and buffered-flush cleanup. A stream can receive a prefix before failing; this repair does not make a stream write atomic. Stderr must remain available to receive a diagnostic. Custom replacement stream objects without the usual binary-stream interface are outside this narrow change.

## Source boundary

The repair inserts the same two-line absence check at the start of each existing `_write_stdout` helper in `fanout_engine/preview.py` and `fanout_engine/inspect.py`. The check raises OSError before the write/flush cleanup block, so cleanup does not itself dereference the absent stream. History and projects already import inspect's helper and need no source edits.

The original source pin is commit `ad99d83d23e029cc383b2adf8a999f23be642f8c`, tree `4cd5e997f9d8ac7c68d03ab5ea818667b8d0a20a`. The original helper modules have Git blobs `3af98db006853a19f60506322f7e450ce3685cfc` and `827b5760a0a95bd7960b084708225ebd478e3ff3`. Removing the two inserted lines from each reviewed successor recovers those exact original bytes.

The separately qualified queued-route consumer retains its own absence guard unchanged. This follow-up does not rewrite its source or evidence. Adjacent preview identity and history/projects export owners retain their changes and contracts. The [bounded public contract and ownership record](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6144101879) records the scope.

## Maintained regression course

From a source checkout on POSIX with Python 3.10 or later:

```sh
python3 -B -m unittest discover -s tests -p test_readonly_stdout.py -v
```

The three test methods exercise real CLI children and an owned SQLite fixture:

- All four commands with descriptor 1 closed at Python startup, followed by healthy report reads.
- Supported explicit file outputs with stdout absent.
- Existing write-error handling against the actual `/dev/full` device when available.

The fixture checks input bytes, mode and modification time, including the presence and contents of SQLite sidecars. It closes its Ledger and each test subprocess before temporary fixture cleanup. Child calls have an eight-second bound. The closed-descriptor course is POSIX-specific; the actual failing-device course skips when `/dev/full` is absent. These are targeted regressions, not a full repository suite or a Windows/macOS/installed-service qualification.

Author execution used cloud Linux and CPython 3.12.14. Corrected maintained test source shows four target subcase failures against the original helpers, with the other two methods passing; the exact successor passes all three methods with zero skips. Preview's original unhandled exception exited 1 instead of its handled output-error status 2. The other three original commands exited 1 with a traceback instead of a clean report refusal.

Two earlier author test drafts incorrectly assumed common report keys: inspect has no `schema_version`, and preview's authored plan uses `project` rather than `project_id`. Their failed logs and source drafts are retained separately; the final test checks each command's actual project-identity shape. An initial ENOSPC source-copy attempt and subsequent discovery refusal ran no product course. None of those attempts is counted as acceptance. Independent original-first consumer evidence is recorded separately from this author course.
