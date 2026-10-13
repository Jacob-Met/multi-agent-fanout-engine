# Portable authored-plan comparison package

This directory preserves the reviewed builder and verifier for the portable HTML comparison delivered from [PR #74](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/74). The package contains a readable report, its exact native JSON, the existing release-notes example inputs, and the selected Python runtime needed to compare another authored pair.

The product workflow is documented in [the comparison guide](../../compare-plans.md). Open the extracted package's `comparison.html` for the supplied example. To create another report, run the comparator from the extracted folder with Python 3.10 or newer:

```sh
python3 -B -m fanout_engine.compare --before examples/before.json --after examples/after.json --format html --output ../release-notes-review.html
```

On Windows use `py -3 -B` in place of `python3 -B`. JSON remains the default format. Output paths must be new. Keep generated reports outside the extracted folder so its exact membership remains verifiable. Comparing authored plans does not dispatch work, contact a Hub, or read a retained ledger.

## Qualified package

| Item | Exact identity |
| --- | --- |
| Archive | `Fanout-Plan-Comparison-Offline-v1-20261013.zip` |
| Archive bytes | 51,086 |
| Archive SHA-256 | `21fdff31e837cdd7dcfc188b3b8426114b462f44899de797886e8b6ffe64bcca` |
| Membership | 24 regular files: 22 manifest payloads, manifest, and checksum list |
| Checksums | 23 entries; the checksum list does not include itself |
| Source repository | `Jacob-Met/multi-agent-fanout-engine` |
| Source commit | `2a70639b26a267ff5b70de8254c23eaf2a0839e5` |
| Source tree | `33cf84d66550fd8ffe16bdf17ae10609472ab920` |
| Declared inputs | 17 files, 100,990 bytes |
| Input configuration SHA-256 | `8a15fca4b71910542d033b931cf261f7b8a62afaca6877654c1f4cff254e45e6` |
| INDEX snapshot SHA-256 | `b09abcc3902926eda4cc4e8cccd38fede2788111e5874a6922b17c3716a87aba` |

The selected source is 12 runtime modules plus the exact comparison guide. Nine modules form the comparator's transitive import closure; the three retained optional command modules are `history.py`, `inspect.py`, and `projects.py`. The independently owned retained-project viewer `review.py` is not included. This is a selected comparison runtime, not a complete repository snapshot.

A concurrent queued-withdrawal change reached the actual merge parent. The package includes its exact merged `ledger.py` blob `938a5e68a7b33b01a4219356c6894614b95fb0b5`. Independent source review proved that this change adds only one ordinary instance method, leaving all other original bytes, imports, and module execution unchanged. Native Windows receiving of the selected merged runtime reproduced the prior 2,115-byte JSON and 12,009-byte HTML exactly.

The before/after inputs are unchanged from the previously delivered fictional release-notes comparison export: [original artifact](https://drive.google.com/file/d/1njn5AOpgGVw-ZcJa-5Gaiqs7X5cHrqxE/view), SHA-256 `3959c81a9d3bc60e5358bf9d676c5385ee362b704060deb611c59f6c59e46949`. The new package's 2,167-byte native example JSON is byte-for-byte identical to that delivery. The HTML download link embeds those same bytes, including the final line feed. These authored examples do not assert that any tasks ran.

## Verify an extracted package

Run the supplied verifier from the extracted folder:

```sh
python3 -B verify-package.py
```

Use `py -3 -B verify-package.py` on Windows. The verifier locates the package beside its own file. It checks every manifest payload's byte count and SHA-256, the complete checksum set, and exact regular-file membership. Linked and nonregular entries, mismatched bytes, missing files, or extra files cause refusal.

The verifier runs no engine code. It establishes agreement with the supplied manifest and checksums; it does not independently authenticate the author, Git origin, or statements in INDEX.json. The pinned Git source and receiving evidence provide that separate binding.

## Build from explicit reviewed inputs

`build-package.py` uses only the Python standard library. It requires six arguments:

```sh
python3 -B build-package.py \
  --inputs /absolute/path/portable-inputs-final.json \
  --index /absolute/path/portable-INDEX.json \
  --readme /absolute/path/portable-README.md \
  --verifier /absolute/path/verify-package.py \
  --stage /absolute/path/Fanout-Plan-Comparison-Offline-v1 \
  --output /absolute/path/Fanout-Plan-Comparison-Offline-v1-20261013.zip
```

The stage directory and output archive must both be absent, including dangling links. Their parent directories must already exist. The builder leaves a failed partial stage or archive available for inspection; use a new destination for another attempt.

The input configuration has this shape:

```json
{
  "format": "fanout.offline-comparison.inputs/1",
  "status": "READY_FOR_ARCHIVE",
  "files": [
    {
      "name": "fanout_engine/compare.py",
      "path": "/absolute/source/fanout_engine/compare.py",
      "expectedBytes": 6957,
      "expectedSHA256": "ec28e7331482f83fda3f2efc6b591ae5c3a5cb452e78e3b5e0947daa1f39b6d1"
    }
  ]
}
```

Each row maps a package-relative name to an accessible regular source file and its exact expected bytes and hash. The qualified configuration contains all 17 declared inputs: 12 Python modules, the comparison guide, two authored input files, and the actual generated HTML and JSON. Package names must be relative slash-separated NFC text without empty, dot, or parent components, backslashes, colons, or case-fold collisions.

The separate INDEX document must include `status: "READY_FOR_ARCHIVE"`, `functionalCoverage.independentStatus: "PASS"`, and the reviewed `source` metadata copied into the manifest. Those fields record the review decision; the builder does not perform that review or authenticate the metadata.

The builder captures five further payloads under reserved names:

- `INDEX.json`: the supplied index snapshot.
- `README.md`: the supplied consumer opening guide.
- `verify-package.py`: the supplied verifier.
- `build-package.py`: the executing builder's source.
- `PACKAGING-INPUTS.json`: the original input configuration bytes.

It then adds `MANIFEST.json` and `SHA256SUMS`, writes fresh regular files with mode 0644, runs the staged verifier, and creates the exclusive ZIP. Members are sorted with a fixed 2026-10-13 timestamp and deflate level 9. The builder reads back archive membership, CRC, modes, and every member's bytes. It also rereads all 17 declared source inputs after construction. The five packaging extras are captured snapshots bound by the manifest.

For identical archive bytes, retain the exact input and metadata bytes, stage basename, and compression implementation. `PACKAGING-INPUTS.json` intentionally retains the original source paths. The builder needs those files accessible at the configured paths; extraction alone does not restore them on another machine. Editing a copied configuration to point at relocated sources enables a new build, but changes the captured configuration and therefore the archive identity.

## Recorded receiving scope

The completed courses remain separate; their check counts are not an aggregate score.

- Author regression: 14 new HTML methods passed normally and with genuine Python optimization. The existing comparison/export course grew from 17 to 31 passing methods. The original implementation's expected feature failures remain retained.
- Independent native Windows CLI: 120 original-source checks, 89 candidate checks, and a separate 176-check read-only audit. Exact JSON compatibility, deterministic HTML stdout/file output, exclusive publication and malformed-input refusal were observed.
- Actual Chrome 154 browser receiving: 131 checks over two real CLI-generated reports, with a separate 122-check read-only audit and all eight screenshots inspected. This course used owned loopback HTTP at 1440 and 390 pixels and real trusted keyboard downloads.
- Independent final package preparation: 58 read-only checks bound all 13 selected source blobs to the exact merged tree, every declared input, the import closure and the existing example/native JSON bytes.
- Fresh producer receiving: 52 checks on a new extraction verified all 24 members, all 13 Git blob identities, supplied verification before and after use, and actual packaged JSON/HTML regeneration. The complete package and archive remained unchanged.

The fresh producer receipt is 8,748 bytes, SHA-256 `f10585049c3f685508786b336829eccd54b8461031e2579a52531447b68850f7`. The independent preparation receipt is 7,995 bytes, SHA-256 `837f07be7a6d6d342f484b02ad9f9d3db6f7411f84f2428e5dcca9c0417f6bf8`.

The immutable package INDEX is a pre-archive checkpoint. It explicitly leaves attachment placement and direct `file://` browser receiving for subsequent evidence. Those results belong to the existing [comparison, history and retained-examples record](https://app.notion.com/p/3f4aedcdf4a58119bf4ff87a0c51f6a4?pvs=204) and [source thread](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/74); they are not implied by the earlier HTTP-origin course. The separate evidence packet preserves the raw original/candidate receipts and reviewer corrections.

## Reviewed script identities

- `build-package.py`: SHA-256 `b9c224e398a969919327545c8179a55f0235fd6327d4df510ac4faecb7e12b69`.
- `verify-package.py`: SHA-256 `ad7cbc79d8baab9382d7c0e442866930f57ec08ae575df59c32894d8a145593c`.

This additive source record preserves the already used producer and verifier. It changes no comparison implementation, workflow, existing owner branch, or delivered archive.
