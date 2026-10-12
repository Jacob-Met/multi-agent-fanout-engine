# Repeated plan-key lookup

`Ledger.record_plan` and `inspect_project` ask a Plan for each part's stable
idempotency key. Previously each lookup rebuilt the complete set of part IDs.
That made membership work quadratic in the number of parts even though the
native Plan is immutable.

The correction retains one lazily computed membership set for the native shape:
an exact tuple containing exact frozen Part values with ordinary string IDs.
Historically accepted mutable Part-like objects keep fresh membership lookups.
The public JSON representation, digest, key formula, dataclass fields, equality,
representation, copying and replacement semantics are unchanged. Each eligible
Plan trades one retained O(n) frozenset for expected constant-time membership
after its first key lookup. This does not optimize every ledger or dispatch
operation.

## Current-source composition and review

The source parent for publication is
`0317b4bc80638a8e952857aa5966b0e20d1fab72`. This change preserves its accepted
iterative graph validator, constructor collection snapshots, finite JSON parser,
and ledger cancellation rollback repair.

The production Plan file has Git blob
`69a633cacd6f32e8bbc6d0d580db3b2fcb14ec82` and SHA-256
`884f85eff1ef526a8a47e6ee258fc473ce6647e914bd93298d91824640deab61`.

- The complete canonical repository suite plus six new identity tests passes:
  **75 tests**, Python 3.12.14. All inherited package, test and example blobs
  were checked against the exact source parent; only the intended Plan module
  differs. Five supplemental depth checks are retained outside this suite.
- The six new identity tests also pass on the unmodified publication parent.
  They verify behavior preservation, including constructor snapshots, exact
  independently computed keys, errors, copies, replacement and mutable
  duck-typed Parts.
- An earlier candidate on source parent `7a05c33c63b309425b5904914e9faf589ce7aff7`
  passed **25 independent identity checks on both parent and candidate**. The
  first attempt failed a mutable-list check; an intermediate correction failed
  independent mutable-Part checks. The final fast path excludes unsafe shapes.
- While publication was prepared, the accepted constructor changed to snapshot
  caller-owned lists and tuple subclasses. This composition preserves that
  deliberate change, updates the two affected identity tests, and retains the
  conservative fallback for mutable Part-like objects.
- The older independent and native receipts described below retain their
  original source identities. They are not relabeled as the newer composition.

## Complete workflow measurement

Each sample constructs the same authored prerequisite chain, opens an in-memory
SQLite Ledger, records the plan, and inspects the complete stored project.
Report comparison removes only generated `updated_at` timestamps. Every other
field, including identities, state counts, ordering and all keys, has the same
normalized SHA-256 before and after.

The measured before source is `7a05c33c63b309425b5904914e9faf589ce7aff7`, Plan
SHA-256 `a8bea1e921bf8789d6eed45b277eb502a048749b6767dd798137afbfc201ce1b`.
The measured candidate adds the same conservative membership-cache algorithm,
Plan SHA-256 `78debfebb488cac11ee52d83bf6ff42c8d0af6902377bc0ccef01f3474b9b922`.
These measurements predate the constructor/parser and ledger-only compositions.

Three sequential samples per size and source in the same Linux workspace,
Python 3.12.14, produced these medians:

| Parts | Parent total | Candidate total | Observed ratio |
| ---: | ---: | ---: | ---: |
| 256 | 0.01628 s | 0.01083 s | 1.50x |
| 1,024 | 0.10043 s | 0.05324 s | 1.89x |
| 4,096 | 1.13509 s | 0.23396 s | 4.85x |

At 4,096 parts, median recording time was 0.50982 s before and 0.04205 s after;
median inspection time was 0.59234 s before and 0.15750 s after.

The same source snapshots were separately received on the identified MSI,
Windows x64, Python 3.14.3. Three samples per size and source produced:

| Parts | Parent total | Candidate total | Observed ratio |
| ---: | ---: | ---: | ---: |
| 256 | 0.01898 s | 0.01324 s | 1.43x |
| 1,024 | 0.12610 s | 0.05343 s | 2.36x |
| 4,096 | 1.74158 s | 0.21457 s | 8.12x |

Each native snapshot also passed 21 independent disk-backed deep-plan,
dispatch, unknown-effect and restart checks, all 25 independent identity checks,
and the shipped mixed-state example. All three processes returned zero. The 24
copied source/receiver files retained their before/after hashes. This is portable
source receiving, not an installed service or production-adapter claim.

Reproduce each source separately with the same supplied benchmark:

```sh
python tools/benchmark_plan_keys.py /path/to/checkout --sizes 256,1024,4096 --repeats 3
```

Phase medians need not sum to the median total. Timing includes native plan
validation, SQLite initialization and writes, report construction and validation.
It excludes JSON serialization performed solely to compare reports after the
timed work. The samples ran sequentially on shared hosts, so order, contention
and caching can affect the observed ratios.

These finite synthetic measurements establish neither remote-worker throughput,
production latency, statistical confidence intervals nor a universal speedup.
No provider, credential or production ledger is used. The preview consumer's
existing 256-part authored-plan limit is unchanged.
