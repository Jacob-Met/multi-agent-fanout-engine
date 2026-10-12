# Dependency validation without a recursion-depth boundary

The native `Plan` constructor now checks dependency cycles with an explicit
traversal stack. A valid plan's admission no longer depends on Python's call-stack
limit or the order in which its parts are authored. This does not change the
authored order, dependency order, canonical serialization, plan digest, stable
idempotency keys or dependency readiness. Actual cycles retain
`PlanError("dependency graph contains a cycle")`.

## Original failure

Original source: `49f042cf8652860aae3e8bf8d90a47641f2d6527`, tree
`dcebecc57e533a02b293ffeb64c4757c6b614e9b`.

On Python 3.12.14 with the default recursion limit of 1,000, the original 44-test
suite passes. A 1,500-part chain passes when prerequisites occur first, but the
same graph listed dependents-first raises `RecursionError`. A 1,500-part cycle
also raises `RecursionError` instead of the native `PlanError`.

For a direct reproduction against the original source:

```python
from fanout_engine import Plan

parts = [
    {"id": f"part{i}", "instruction": "Review synthetic input.",
     "depends_on": [f"part{i - 1}"] if i else []}
    for i in range(1500)
]
Plan.from_dict({"project": "deep-chain", "parts": list(reversed(parts))})
```

## Qualification

`tests/test_plan_graphs.py` adds five maintained tests:

- Deep chains in both authored orders preserve complete documents, independently
  calculated digests and idempotency keys, and native readiness order.
- Deep cycles in both authored orders raise the exact existing `PlanError`.
- Shared prerequisites and a separate component remain valid.
- A cycle in a later component remains rejected.
- All 64 directed three-node graphs, each in all six authored orders, agree with
  a separate finite oracle that checks the existence of a topological ordering.

The new tests on original source produce three failing subcases across the two
deep-graph tests; all other new cases pass. With the iterative change, all five
tests pass in ordinary and optimized Python. The complete suite passes 49 tests,
and both existing local examples run successfully:

```sh
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -p test_plan_graphs.py -v
python examples/demo.py
python examples/inspect_plan.py
```

These measurements cover Python 3.12.14 on Linux. The change uses the existing
standard-library runtime and adds no dependency. The preview consumer's existing
256-part limit stays unchanged; this repair applies to native `Plan` validation
and does not claim unlimited memory or production worker capacity. No provider
call, installed-service adoption or hosted GitHub Actions run is part of this
qualification.
