# SMALL-1: validate stage inputs before output writes

Pinned base: 0c9a5441548ea583885fc12f4fd86541c398e077.

The old builder records missing state rows and continues, potentially replacing an existing atlas with blank rows. The new preflight requires the expected count for all nine state rows, sixteen look frames, and the neutral frame. It checks PNG format, dimensions and container integrity before the first output-directory creation.

## Verification

Python 3, NumPy 2.3.5, Pillow 12.3.0; no installation or network calls.

`ATLAS_SOURCE=/absolute/path/to/tools/build_codex.py python3 -m unittest discover -s tests -p test_atlas_preflight.py -v`

- Baseline: 8 tests, 7 failures, 1 pass.
- Candidate: 8/8 pass; py_compile passes.
- Real main entrypoint invoked with synthetic PNG fixtures, nine production row definitions, smaller test dimensions. Output-directory creation is trapped to prove rejection occurs before any output write; existing sentinel files remain byte-identical.
- Covers absent row, wrong count, extra frame, missing look, missing neutral, malformed PNG, wrong dimensions, and valid input reaching the existing build.

## Boundaries

This patch fixes invalid/missing input publication, not the entire build transaction. It does not prove a full production atlas render, downstream validator success, or crash-atomic publication of multiple output files. Concurrent modification of stage files during building remains outside this check. No real artwork, installed pet, or release outputs were opened or modified.

## Risk and rollback

Low code scope: one read-only preflight call before existing build. Invalid input now raises a descriptive error instead of silently continuing. Revert this source/test commit to restore the old behavior. Existing optional validator policy is unchanged and needs separate review before a release-quality claim.

## Review corrections

Final baseline: 11 failures / 12 tests; candidate: 12/12 pass. Added exact filename-set checks matching src/pet-main.js atlasJobs (state NN.png; look NN_AAAA.png at 22.5-degree increments), native RGBA mode, and actual pixel decoding after container verification. New cases cover same-count stale filename substitution, wrong look angle, lost alpha, and valid PNG checksums with invalid compressed pixels. The latter passes Pillow verify() but is rejected by load() before output creation. Earlier eight-test logs are historical; final logs supersede them.
