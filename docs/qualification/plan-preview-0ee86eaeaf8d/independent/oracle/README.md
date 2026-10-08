# Independent authored-plan preview oracle

This oracle is frozen before reading the new preview implementation or its tests. Its only product inputs are the agreed `PROPOSED_CONTRACT.md` and the exact original twelve-file snapshot at `d65bde9c59b1d2593a80f6d838c0a40bf6768013` / tree `d5e5ad4e316be0b20a50151f8549ac490d3d99de`.

`build_oracle.py` computes reference bytes directly from the published native normalization, hashing and pool-selection rules. It imports no product code and launches no product process. The original two-process baseline is retained by its author and is not repeated.

The distinct six-part fixture starts with a blocked publication part, includes two initially ready roots and declares the remaining dependencies out of execution order. It checks tag normalization, preserved instruction text, all six keys and routes, exact initial readiness, an explicit choice equal to its ordinary pool choice, and a configured step-up which must never be invoked. Captured input-byte hashes are intentionally different from the normalized plan digest.

The eventual native receiver makes one actual API process and seven actual module-CLI processes. It uses the original five native package modules unchanged plus the exact frozen new preview module. No author tests, inherited full suite, baseline command or service are run. The API consumer guards database/socket/child-launch effects and observes all authored `route_for` calls. CLI cases cover exact canonical stdout; exact file delivery despite an unusable stdout device; an unauthorized blocked last part; a malformed later part; an existing symlink targeting the input; a kernel-enforced stage-write failure; and a failed stdout device. Inputs, the retained-owner marker, source bytes/inodes/modes/mtime and every success/failure artifact are preserved and checked. Failed or interrupted receiving is saved before raising.

This is a Linux receiving harness using only the existing Python standard library. `resource.RLIMIT_FSIZE`, `/dev/full`, and symlink cases are explicit receiving conditions, not new product platform requirements. The portable product and its own hosted workflow remain separate gates. A general broken stdout stream can deliver a prefix; failure cannot be labeled universal proof of no delivery.

After candidate pins are supplied, run:

```sh
PYTHONDONTWRITEBYTECODE=1 HAMON_REVIEW_TMP=/dev python3 -B receive_preview.py --original /path/to/original-twelve-files.json --candidate /path/to/frozen/preview.py --candidate-sha256 EXACT_SHA256 --output /path/to/new-receiving-directory
```

The output directory must be absent. This receiver edits no sibling source or cache. The expected report and oracle scripts are bound by `oracle-manifest.json`; later candidate findings must preserve this original oracle and any first execution outcome.
