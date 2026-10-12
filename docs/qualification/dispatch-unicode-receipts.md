# Retain unknown dispatch outcomes for malformed Unicode task IDs

## Behavior

An adapter acknowledgement is usable only when its task ID is a nonblank string
that can be encoded as UTF-8 and retained by the native SQLite ledger. When an
adapter returns an unencodable ID, `dispatch_ready` records the existing
`outcome_unknown` state with the stable idempotency key as the evidence locator.
It then continues later independent ready parts. The ambiguous part is not
submitted again, and its dependents remain queued.

Valid Unicode IDs retain their exact spelling, including surrounding whitespace.
The check does not normalize, replace, trim or decode identifiers. Unrelated
adapter response fields are not serialized or retained. The Hub protocol,
dependency readiness, routing, ledger transitions and reconciliation contract
keep their existing implementations.

## Reproduced predecessor failure

Source parent: `0b169f9df939350911d76dbda88023fe37ee53bf`.

The JSON text below decodes successfully with Python's standard `json.loads`:

```json
{"task_id":"remote-\ud800"}
```

Its task ID contains a lone surrogate. On the predecessor, dispatch accepts the
nonblank string and then native SQLite parameter binding raises
`UnicodeEncodeError`. In a plan with two independent parts, only the first Hub
call runs; that first part remains `dispatching` and the later part remains
`queued`. The SQLite transaction correctly rolls back. The failure is admission
of an unusable acknowledgement before the next independent dispatch.

The source correction adds a UTF-8 encoding check immediately before the existing
invalid-task-ID branch. An encoding failure enters that same branch, retaining
the existing `submit returned no verifiable task identifier` evidence text.

## Qualification

The dedicated `tests/test_dispatch_unicode_receipts.py` uses only the standard
library, a local Hub adapter and the actual native dispatch/SQLite/inspection
implementations. Its five test methods cover:

- JSON-decoded lone high and low surrogates, embedded lone surrogates, and a
  reversed surrogate pair; a direct Python string containing two uncombined
  surrogate code units is also refused.
- Persistence through a disk-backed ledger, writable reopen, and read-only
  reopen. The report remains inspectable, later independent work starts, and a
  repeated dispatch leaves both retained rows and the event history unchanged.
- The existing missing, blank and nonstring acknowledgement behavior.
- Exact preservation of ASCII, accented, CJK, supplementary-plane and boundary
  Unicode identifiers, including surrounding whitespace and a valid surrogate
  pair combined by JSON decoding. Completing the first part still unlocks its
  dependent on the next pass.
- A valid task ID accompanied by an unrelated malformed Unicode response field;
  only the ID is used, and the response is not mutated.

Initial candidate qualification on Python 3.12.14:

| Source and course | Result |
| --- | --- |
| Exact predecessor with the five new methods | Fails with five encoding errors across the two malformed-Unicode methods; the other three methods pass |
| Initial candidate, complete maintained suite | 101 tests pass |
| Initial candidate, complete maintained suite under actual `python -O` | 101 tests pass |
| Initial candidate, existing local demo | Exit 0 |

Independent receiving used a separately authored adapter backed by actual
loopback HTTP responses parsed with `json.loads`, rather than the author test
adapter. The receiver was frozen before candidate source/test inspection, at
SHA-256 `036b6a003ff41e903d0fd42d240e0b937b97e814e4dd5925ed78d687bb35830a`.
It reproduced three malformed-receipt aborts on the predecessor. The candidate
passed all seven scenario groups in both normal and optimized Python, with
24 loopback submissions and seven separate inspector child processes per mode.
The course covered disk reopen, no replay, later dependency progression, explicit
unknown reconciliation, and exact valid IDs including embedded NUL. The reviewer
accepted the exact candidate source hash below.

Reproduce from the repository root:

```sh
python -B -m unittest discover -s tests -p test_dispatch_unicode_receipts.py -v
python -B -m unittest discover -s tests -v
python -O -B -m unittest discover -s tests -v
python -B examples/demo.py
```

The new test file can also be loaded with the predecessor package first on the
Python module path to reproduce the five original errors. No production model,
provider, external worker, or live dispatch is involved in these checks. These
results qualify the reference-core response boundary; they do not establish
installed estate uptake or verify an external task's acceptance.

Source SHA-256 before the change:
`f6fe045bce47dc333c9e582cd0492257d1674ae073e9ac4bc33a4681696e1f3c`.

Initial candidate `fanout_engine/dispatch.py` SHA-256:
`f71e3cb075c9af5419dfd3c8fd64037fde1455a4462e2eb69a1a4d735eb14412`.

Qualified regression SHA-256:
`9f2ff0bb22382a1ed275f5d8c604786d742d63fb1b37e827a992522f2f09a2dd`.

## Composition with the unreadable-response repair

Before publication, main advanced to
`ae23e21d10c61b22397378a6974db6992e6c1806`, integrating PR #19. That repair
guards task-ID extraction and string validation, including deferred mapping
failures, while preserving cancellation and SQLite persistence failures. It does
not yet check whether an otherwise nonblank ID can be encoded for SQLite.

The published candidate is based on that newer parent. Its only production
change is six added lines inside the existing response-validation `try` block:
after the existing nonblank check, attempt UTF-8 encoding and set
`valid_task_id = False` on `UnicodeEncodeError`. The outer response guard and all
ledger calls remain unchanged. The new malformed-Unicode regression is identical
to the initially qualified file. PR #19's six tests and guide remain byte-exact.

| Current-parent qualification | Result |
| --- | --- |
| Exact `ae23e21d` predecessor with the five Unicode methods | Same five encoding errors |
| Composed candidate, complete maintained suite | 107 tests pass |
| Composed candidate, complete suite under actual `python -O` | 107 tests pass |
| Independent frozen receiver on `ae23e21d` predecessor | Same three malformed-receipt aborts |
| Independent frozen receiver on composed candidate, normal and optimized | All seven groups pass in each mode; 24 loopback submissions and seven inspector child processes per mode |
| Independent PR #19 regression receiving, normal and optimized | All six methods pass in each mode |

The independent reviewer accepted the exact composed dispatcher SHA-256:
`2263528fce1bcc1393cf784d25a02ac9dd66da9c788c43eeeadfaf52afa67256`.
The initial source measurements above retain their original attribution.
