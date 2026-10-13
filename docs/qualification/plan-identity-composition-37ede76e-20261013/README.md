# Combined plan identity receiving

This isolated integration candidate combines the already reviewed preview,
ledger admission/persistence and dispatcher capture increments on actual main
`23daeba5b97ea87733f95bae19b45525e40ae95c`. Root retains the main-branch
integration decision. The source owners retain PR44 and PR49; PR48 remains the
separate ready ledger contribution.

## Exact composition

The published source merge is [`b0330ae230d033d6e7d4a56b564180ef7b185092`](https://github.com/Jacob-Met/multi-agent-fanout-engine/commit/b0330ae230d033d6e7d4a56b564180ef7b185092),
with complete tree `aa06d9625bef6ecb726cc6bc4b04947f1fa810e6`.
It has the same tree and ordered parents as native tested commit
`9ca7d3553ad96e7f0ce82ed01bde4db7531bfe2c`.

| Parent | Exact commit |
| --- | --- |
| Current main | `23daeba5b97ea87733f95bae19b45525e40ae95c` |
| Corrected preview PR44 | `02ab6b6705705b9738a0f7d6601dee0d35b9efc7` |
| Ready ledger PR48 | `762ed069d7949f7a302db36a349ace17a3e0325f` |
| Dispatcher PR49 plus independent receiving | `c38f66f047cd0749dd80a450cd63014b8ac45b0f` |

The fourth parent descends from exact PR49
`842d33b92ac5fc2be186e7172535e83c2ca3a6de`. Its receiving-only follow-up to
`e860c8c40fecfb96bb9500bdaf72598a3c142cec` adds the original
`independent/source-admission.json` input and its README row. That raw manifest
matches the parsed admission embedded in the original executed receipt.

| Product file | Preserved reviewed blob |
| --- | --- |
| `fanout_engine/preview.py` | `71dabb931a1adafd7ff449b53d3a1223e08e290d` |
| `fanout_engine/ledger.py` | `627ece1c327b6a15eb47f25b3e7041c371e4d558` |
| `fanout_engine/dispatch.py` | `bec8a82063dc06653128f155b8487428847b73c2` |

The merge resolves without source conflicts. All 27 changed paths are exactly
the union of the three reviewed increments and the independent dispatcher
test/receiving files. Every reviewed production, test, guide and retained
evidence blob keeps its identity. The remaining current-main leaves stay
unchanged.

## Actual native combined receiving

macOS, CPython 3.13.7:

| Course | Result |
| --- | --- |
| Complete maintained suite, normal Python | 202 methods run: 198 pass, 4 skips, no failures/errors |
| Focused plan-identity and native-key methods, actual `-O` | 25/25 pass, no skips |
| All tracked files before/after both courses | 205/205 preserved |

The four complete-suite skips require `/dev/full`, which is unavailable on
this Mac. They are the maintained compare, history, inspect and preview output
failure methods. Their exact messages remain in the raw log; no Linux result is
implied.

The optimized pattern includes the two existing native-key work methods in
addition to the 23 preview/ledger/dispatcher regression methods. This is an
actual run on the combined source, separate from the earlier single-increment
and two-increment receiving counts. It is not another full-suite optimized run.

The unchanged commands were:

```sh
python3 -B -m unittest discover -s tests -v
python3 -O -B -m unittest discover -s tests -p 'test_*_plan_*.py' -v
```

All tracked source/test/evidence bytes stayed exact. CLI child processes left
untracked Python bytecode in the isolated checkout; none is included in this
branch.

## Retained receiving bytes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| [receiving.json](receiving.json) | 31557 | `2d43202e36a619f85fc1cf5b42e617795d124ee3045b7fa99aa1e26bfbc9ea1b` |
| [complete-normal.stderr.txt](complete-normal.stderr.txt) | 40940 | `9a1f10d317e0d9189accd33c689bc935334185b2a7a151fc7be815efe449ad55` |
| [complete-normal.stdout.txt](complete-normal.stdout.txt) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [identity-optimized.stderr.txt](identity-optimized.stderr.txt) | 4586 | `8cdfc283c10c48171d88eddcea99cb8a0b6c245246cb2a8d1e5b5d98bf9a96fc` |
| [identity-optimized.stdout.txt](identity-optimized.stdout.txt) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The JSON retains complete commands, runtime, source/parent/tree identity,
all 205 watched SHA-256 values, raw stream identities and actual exit codes.
Absolute native paths describe the original executed course.

The source and Markdown whitespace check passes. A whole-diff check returns 2
for three existing trailing spaces in the preserved original failed dispatcher
test stdout. Those historical bytes remain exact; this is not a whole-diff
whitespace pass.

The earlier [individual and paired receiving](../plan-identity-receiving-37ede76e-20261012/README.md)
and [independent ledger acceptance](../ledger-plan-identity-37ede76e-20261012/README.md)
remain intact. This integration candidate establishes source compatibility
under the stated local courses. It does not establish an installed worker,
provider submission or main-branch adoption.
