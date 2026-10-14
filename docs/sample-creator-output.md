# Create the authored sample with a Unicode filename

The sample command accepts an ordinary filesystem path. Its parent directory
must exist, and the destination must be new:

```sh
python examples/create_retained_ledger.py "café-Ω-🚀.sqlite3"
python -m fanout_engine.inspect --database "café-Ω-🚀.sqlite3" --project sample
```

The resulting database contains seven authored parts covering all six native
states. The [inspection guide](inspect-ledger.md#try-a-complete-disk-example)
explains those states and the retained evidence.

## Reading the success message

The command first prints its normal success sentence through the configured
stdout text stream. ASCII, other encodable text and UTF-8 output retain their
usual appearance.

If that print raises `UnicodeEncodeError`, the command retries the diagnostic
using the same stream encoding with `backslashreplace`. Only characters that
the codec cannot represent become escapes. For example, a cp1252 stream can
display `café` but requires escapes for the other characters in this filename:

```text
Created authored sample project 'sample' in café-\u03a9-\U0001f680.sqlite3
```

The database is still named `café-Ω-🚀.sqlite3`. Pass that original filename to
the inspector; the diagnostic's backslash sequences are a display form.

The fallback is local to this message. It follows the same-encoding approach
documented for Python's
[`sys.displayhook`](https://docs.python.org/3.12/library/sys.html#sys.displayhook).
A stream that already handles the text with a configured error handler keeps
that normal behavior. Other output I/O errors still propagate.

An existing destination or missing parent retains the creator's status 2 and
stderr diagnostic. The existing file is preserved, and a missing parent is
not created.

## Verification

Run the maintained subprocess regressions from the repository root:

```sh
python -S -B -m unittest discover -s tests -p test_sample_creator_output.py -v
```

The six methods exercise actual child processes with cp1252 strict and
surrogateescape, encodable ASCII and accented text, literal UTF-8, configured
replace/ignore handlers, and both creation refusals. Successful databases are
reopened through the native read-only ledger and inspector, with their bytes
checked before and after inspection. Encoding overrides belong only to those
test children.

The reviewed production sample is Git blob
`0e0bc5d8ea3790ce4bb5028cbe3b1725fcedb21a`, composed on parent
`b69aaf7ad06bb2ac904ca037fb847baa53915846`. All six methods passed on
CPython 3.14.4. The unchanged parent reproduced both strict and surrogateescape
failures in the single non-encodable-path method.

An independently frozen seven-case course also passed on native Windows
CPython 3.12.2. Its ordinary redirected stream used cp1252/surrogateescape;
a separate child supplied the UTF-8 control. All five actual created databases
passed the native inspector with the expected states, readiness and evidence.
Both refusal controls preserved their existing behavior. The original sample
had passed five of these seven cases, failing only the two success diagnostics
containing unrepresentable text.

These are focused command and consumer checks; no full repository suite or
GitHub Actions run is claimed.
