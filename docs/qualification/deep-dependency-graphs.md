# Deep dependency graph validation

## Defect and change

At source `49f042cf8652860aae3e8bf8d90a47641f2d6527`, constructing a valid
1,500-part native plan with each part depending on the next raises
`RecursionError: maximum recursion depth exceeded`. Its JSON representation is
flat; Python stack depth, rather than graph validity, causes the refusal. The
same shape with 100 parts succeeds.

`Plan._check_acyclic` now counts unresolved prerequisites and walks dependency
edges iteratively. Every vertex in an acyclic graph is eventually visited; an
unvisited remainder means that a cycle exists. The validator visits vertices
and edges in linear time and uses linear auxiliary space. This walk validates
only: it never reorders the stored parts or dependencies, changes a digest or
idempotency key, or dispatches work. Cycles retain the existing
`PlanError("dependency graph contains a cycle")` result.

## Author verification

Local Python 3.12.14 ran all 50 maintained tests successfully. The six additions
cover a 1,500-part chain, a deep cycle, a disconnected cycle, shared prerequisites
with original digest/key values, every three-node directed graph against an
independent permutation-order oracle, and a retained SQLite consumer workflow.

The retained-ledger test creates a temporary database, records the deep plan,
closes and reopens it, inspects its direct dependency blockers, and dispatches
only the sole ready part through a local adapter. The other 1,499 parts remain
queued. Inspection succeeds both before and after that local dispatch.

The existing dispatch and inspection examples also ran successfully, and
`git diff --check` passed. The preview consumer's existing 256-part limit and
its boundary tests remain unchanged.

## Independent review

A separate reviewer compared the original and candidate native modules across
all 4,096 directed four-node graphs without self-edges. Exact acceptance or
error text, serialized plan, digest and readiness matched: 543 graphs were
accepted and 3,553 were rejected.

The reviewer separately reproduced the original recursion failure on a
6,000-node chain. The candidate accepted that chain with `p5999` as its sole
initially ready part, and rejected an inserted internal back-edge with the
existing cycle error. Source review found no required correction.

Reviewed product file SHA-256:
`a8bea1e921bf8789d6eed45b277eb502a048749b6767dd798137afbfc201ce1b`.
Maintained regression file SHA-256:
`c2412177a7094cab00209a5a255f423a758287a982db4744802ab83e2ecb279c`.

These results qualify the native reference API and its local SQLite/adapter
consumers. They make no production worker-capacity or remote-dispatch claim.
GitHub Actions were not used for this qualification.
