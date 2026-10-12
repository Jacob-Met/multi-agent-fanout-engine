# Explicit observations before step-up

`EffortRouter.step_up_after_refusal` returns a configured authorized fallback
only when `refusal_before_output` is exactly `True`, `output_received` is exactly
`False`, and `effect_started` is exactly `False`.

```python
fallback = router.step_up_after_refusal(
    current,
    refusal_before_output=True,
    output_received=False,
    effect_started=False,
)
```

All three fields are Boolean observations. Unknown values such as `None`, JSON
`null`, strings such as `"false"`, numbers, containers and objects with custom
truthiness raise `UnsafeStepUp`. They are not converted to Boolean values. An
adapter must establish the required observations before asking for another
route; `bool("false")` would turn a malformed refusal into an affirmative one.

The previous truthiness guard could authorize the fallback for
`refusal_before_output="false"`, or for an affirmative refusal accompanied by
`output_received=None` or `effect_started=None`. The literal Boolean guard
refuses those calls without evaluating an observation's `__bool__` method.

Existing Boolean behavior is unchanged: of the eight combinations, only
`(True, False, False)` permits step-up. The optional output and effect arguments
still default to `False`; callers must not use those defaults to conceal an
unknown observation. Missing or identical configured fallback routes still
raise `UnsafeStepUp`, and the selected fallback must still pass the existing
authorized catalog check.

This method returns a route. It does not submit work, retry a task, verify a
remote effect, or reconcile an ambiguous outcome. The plan preview continues
to report configured step-up metadata independently of runtime eligibility.

## Focused verification

```sh
python -B -m unittest discover -s tests -p test_step_up_observations.py -v
```

The course preserves all eight Boolean cases and the optional defaults,
rejects non-Boolean observations in each field, exercises decoded JSON
unknowns and string values, and checks that custom truthiness is not invoked.
