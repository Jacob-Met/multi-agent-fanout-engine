# Authored-plan comparison receiving

The new `fanout_engine.compare` consumer reads two explicit authored plans and
reports their native identities, exact edits and before/after keys. It contains
no ledger opening, state transition or adapter invocation. The user-facing
[comparison guide](../../compare-plans.md) contains complete inputs and commands.

## Source boundary

The four product files were independently reviewed on maintained source from
`0b169f9df939350911d76dbda88023fe37ee53bf`:

| Path | SHA-256 |
| --- | --- |
| `fanout_engine/compare.py` | `c96c941c5b4b65e890745bf2b6f4484d4e7284ad6b3c65b729f80513b6baa0c2` |
| `tests/test_compare_plans.py` | `e4f30739f52366484e0ab72a11532e9a928b399d1451280c94fc97dfd640ade7` |
| `docs/compare-plans.md` | `e7ca76209041010f5dac9c8278e9a231a1656ead27b805779a2da00f6a11b2c9` |
| `README.md` | `c9a05d970d641c4a1bf7ba93eca07b6ed2ed17b193dea8d5effa771e4cc0c116` |

`frozen-source-manifest.json` retains their source and Git blob pins. The README
delta is a thirteen-line appended introduction; existing source remains intact.

Before publication, main advanced to
`ae23e21d10c61b22397378a6974db6992e6c1806`, tree
`61a2b24d4cf0c3ad7b04be92f8216083beb3f0a9`, through the separately owned dispatch
acknowledgement guard in PR #19. Its dispatcher, six tests and guide were received
unchanged. All four reviewed product hashes still match. The earlier accepted
dispatch eligibility, read-only inspector and COMMIT rollback work also remains
unchanged. Pending Plan membership work in PR #17 remains with its owner.
The complete composed suite passes all 112 methods in both normal and genuine
optimized Python; the four independently reviewed files retain their hashes.

## Author receiving

The original source has no `fanout_engine.compare` module; invoking it exits 1
with the interpreter's module-not-found diagnostic. This is an absent-capability
witness, not an installed incident.

All 106 maintained and new tests passed in normal and genuine optimized Python
on the reviewed composition. The ten new methods check exact complete API/CLI
agreement, independently derived keys, direction and ordering, direct-constructor
tag/dependency preservation, stale mutable-input refusal, literal filenames,
malformed second-input refusal, actual size/part/report limits and output errors.

`author-guide-receipt.json` records a separate run of the guide's exact inputs.
Native recording first refuses the revised draft under the existing project ID.
The new CLI then returns 0 and writes a 1,663-byte report with the expected added
review, draft instruction edit and changed keys for both retained IDs. Reopening
the database preserves the original plan, and its file bytes remain unchanged.
The database contains only an authored local fixture.

## Independent review

HAMON Memory independently inspected all four frozen files and accepted the
source with no findings within its documented scope. The raw script and normal
and optimized receipts are preserved verbatim in `independent/`.

In each mode, six directional Plan pairs check full field changes, exact native
digests and keys, reversed direction, direct repeated tags, dependency order,
detached output and the 256/257-part boundary. Real CLI processes run from a
separate directory. They accept native-normalized plans and exactly 1 MiB, then
refuse one byte over, excessive nesting, a lone surrogate and duplicate keys
with status 2 and no stdout. Successful output repeats byte-for-byte; input and
sentinel bytes and directory membership remain unchanged. The four reviewed
source hashes match before and after the receiver.

The archived driver's `SOURCE` and `MANIFEST` assignments name the original
workspace paths. For a manual replay, point those two assignments to the desired
checkout and this directory's `frozen-source-manifest.json`. The archived script
and receipts are retained unchanged as the actual review record.

## Limits

Receiving used Linux, CPython 3.12.14 and SQLite 3.53.1. There is no new hosted
Python-version matrix, native Windows/macOS run, live Hub operation or installed
adoption claim. The ordinary strict Plan parser and native key formula define
the report; this consumer does not decide migration, reconciliation or replay.

Source publication carries `[skip ci] [skip actions]` and the skip-checks trailer
under the standing no-GitHub-Actions instruction. Workflow bytes and settings
are unchanged.
