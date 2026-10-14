# Visible formatting controls in the current offline project review

The maintained `fanout_engine.review` command can show accepted Unicode bidirectional formatting controls as visible `\u` escapes. The native inspection JSON remains unchanged. This integration takes the exact ready [PR92 owner offer](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/92), preserving its source, regression and guide bytes while retaining the newer repository work.

```sh
python -m fanout_engine.review --database /path/to/existing-ledger.sqlite3 \
  --project exact-project-id --output /path/to/new-review.html
```

Use an existing saved ledger and an absent output filename. Open the HTML in a browser. The page is self-contained; its **Download exact inspection JSON** link carries the native UTF-8 JSON plus final LF. This command performs no dispatch, provider call or ledger mutation. See the [full maintained guide](../../project-review.md) for validation, output and exit semantics.

## What changes

Twelve formatting characters now display as literal backslash escapes: U+061C, U+200E/U+200F, U+202A–U+202E and U+2066–U+2069. This exposes otherwise invisible direction marks, embeddings, overrides and isolates in instruction, reference, route and evidence text. Ordinary Arabic and Hebrew letters, other Unicode and emoji joiners retain their original output. The embedded JSON retains every original character.

The product change is the exact three predicates offered at `d8fd4548534064c9a1c187fb726ed594ca5e03c8`. Removing those predicates recovers the complete current renderer `7ca6e7376bb7183a7421ed7fdc7d4f139923f69f`; no instruction serialization, CSS, download, database or publication code changes. The owner’s separate leading-LF child remains outside this integration, as recorded in [comment 6154521576](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/92#issuecomment-6154521576). PR105’s installed HTML-reader adoption remains separate.

## Why existing qualification applies

The [current composition proof](current-composition-proof.json) compares exact main `e3ef5fe2da8f6520ee134b8bf5e792a4c00e51e3` with the owner’s publication parent and offer. All nine package modules reached by the review entry and package initializer are byte-identical to that qualified baseline. The existing seven-method report test and guide beforeimage are also unchanged. After the offered delta, all twelve selected module/test/guide files equal the already published owner closure.

Before branch publication, main advanced with the separately received PR105 HTML-reader documentation and removal of the obsolete test workflow and README badge. The final composition preserves all of those changes; its twelve qualified inputs and three intended beforeimages remain exact. The earlier inert proposal and proof are retained in its ancestry.

This is new source/dependency receiving, not a new behavioral course. No product command, native installer, browser, provider or full test matrix was run for this integration. The historical evidence remains attributed to its original authors and independent reviewers:

- The owner’s original CLI regression had one intended display failure and two preservation passes. The candidate passed the seven existing and three new methods in normal and actual optimized Python.
- Six retained real CLI observations preserve exact native JSON. The formatting HTML changes only through the twelve visible substitutions; the ordinary RTL/Unicode/joiner HTML remains byte-identical.
- Independent original/candidate Chromium receiving covered the formatting report at desktop and narrow widths. The ordinary report was byte-compared, not separately navigated. The inherited narrow table wraps `completed` in both versions; this was reported as a nonblocking limitation.
- A separate single documented CLI use from the exact delivered archive produced the pinned report with empty stdout/stderr. This was not a repeated test or browser course.

Read the [owner source review](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/92#pullrequestreview-5507871577), [browser review](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/92#pullrequestreview-5508722717) and [whole-artifact review](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/92#pullrequestreview-5508998377) for their exact scope.

## Existing practical source and evidence

The owner’s [complete runnable kit](https://drive.google.com/file/d/1goaASHFTKyp7OjgBVufDChV0IQ-7mXSe/view) remains unchanged: 1,235,260 bytes, SHA-256 `92211580a6f2ffe30f957dcf90f79465b7306a9602e30396e805c9aa34e64fdd`. Its [small independent receiving companion](https://drive.google.com/file/d/13xFePekx7bsa--6ytMI4I_3L9HlUO3R_/view) is 19,047 bytes, SHA-256 `5862db280aea99520fe46225623c5f37b46ffdf6647335e78b2525955b8a0773`. These links refer to the historical, independently received kit; this integration did not download or re-verify those archives.

The owner retained the exact historical raw courses, JSON and report hashes after a temporary workspace reset. The original SQLite bytes were not recovered. The kit explicitly includes a newly reconstructed fictional inspection fixture with an empty event table, separately verified to produce the historical HTML hashes. Earlier fixture-only validation logs were lost and are not counted as product failures. This integration preserves that distinction.

Existing user installations remain at their separately received versions. A later installed-consumer update needs its own version/identity and use receiving. There is no new browser accessibility, general Unicode shaping, live data or installed-host claim here.
