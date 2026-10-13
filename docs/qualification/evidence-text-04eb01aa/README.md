# Receive literal evidence through retained-ledger commands

This small receiving course qualifies the eleven runtime files at fanout PR67 source
`9b8265a56727e085b99a691e925cc4cfcafb57a7`. It is a local authored example:
no adapter, worker, provider, or network operation occurs.

From this checkout, with Python 3.10+ and an existing writable parent directory:

```sh
python3 -I -B docs/qualification/evidence-text-04eb01aa/receive_cli.py \
  --source . --out ../fanout-evidence-receiving-01
```

The output directory must be new and outside the source checkout. The receiver
first verifies all eleven complete runtime files against the pinned Git blobs.
A mismatched pinned runtime file refuses before creating the output directory. An
existing output directory refuses without replacing its files.

The verified captured runtime bytes are copied into a new owned `runtime`
subdirectory before import or CLI execution. This avoids inheriting a checkout's
existing Python bytecode caches. The input source and received runtime copy are
both verified again after the course.

The course creates its own two-part SQLite ledger. It proves that literal blank
and malformed UTF-8 evidence are refused before any SQL, retaining the preceding
state and database bytes. It then records valid padded Unicode evidence from a
string subclass and preserves its supplementary field. Three actual isolated
Python child commands run canonical `projects`, `inspect`, and `history`.
Their reports must agree on the plan identity, retain exact evidence, and leave
the failed prerequisite's dependent queued. Database bytes and modification
time remain unchanged through each read-only command; all eleven source files
are rechecked afterwards.

A successful run retains its SQLite database, six raw CLI streams and
`receipt.json` plus the complete eleven-file runtime copy, then prints the
receipt SHA-256. An error exits nonzero and
leaves any already created owned output available for diagnosis. Source files
are only read. Stable filesystem paths are assumed; this receiver does not
claim protection against concurrent hostile path replacement.

The checked-in `cli-qualification.json` retains one actual Linux/Python 3.12.14
course, the exact source manifest, CLI streams and separate existing-output /
wrong-source controls. The historical receiving revision linked from that JSON
preserves an initial author-side event-shape expectation error and its correction
to the existing failed-event contract. That earlier error is not counted as a
pass. The revised course executes the fresh captured runtime copy. The previously
published full-suite qualification remains `receiving.json` and has its own
scope. This course does not add a full-suite, optimized-mode, other-OS or installed
adoption claim.

The source pins describe exactly which bytes were received; they do not
authenticate the origin of a separately obtained checkout or receiver.
