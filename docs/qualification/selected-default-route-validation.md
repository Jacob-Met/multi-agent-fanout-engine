# Selected default route validation

A caller can replace `EffortRouter.pool` after construction. The selected default route is now validated against the router's retained authorization catalog before it is returned. This makes default selection consistent with explicit routes and step-up routes.

Deterministic selection and explicit-route precedence are unchanged. A valid selected route remains usable when a different, unselected pool entry is invalid.

## Qualification

The production change is limited to the selected default return in `fanout_engine/routing.py`. Two generic regression suites add eleven test methods:

- Four authored methods cover unauthorized model and effort refusal, valid replacements, explicit-route precedence, and queued dispatch resuming with its original idempotency key.
- Seven independently authored methods cover retained-catalog authority, dispatch refusal, accepted and unknown earlier effects across SQLite reopen/resume, explicit overrides, deterministic selected-route behavior, and in-flight/dependency skip controls.

The frozen independent suite passed seven of seven methods on the correction. Its unchanged original-source comparison passed three methods and failed four, with no errors. Those paired runs used parent `82b5a03a2d3ebaaad13841b3b9b3ffbc55ddff1d`.

Integration was then qualified on parent `ee1107dd0b74308b16f120b7c0c53006def54735`, which includes retained-project inspection. On native Python 3.14.4, the parent passed all 33 unit methods and the demo; the candidate passed all 44 unit methods and the demo. Source hashes were unchanged after execution.

Commands:

```sh
python -B -m unittest discover -s tests -v
python -B examples/demo.py
```

These are local source results; the repository's hosted Python matrix is reported separately by its workflow.

## Behavioral boundary

All tests use local recording adapters and temporary SQLite databases. They exercise caller-driven replacement of the public pool; no behavior of a deployed caller or provider is asserted.

The existing worker-selection callback can run before route refusal. A batch can already contain an accepted or outcome-unknown earlier part when a later selection is refused. The tests verify preservation and safe continuation of those earlier effects; this change does not introduce whole-batch atomicity.
