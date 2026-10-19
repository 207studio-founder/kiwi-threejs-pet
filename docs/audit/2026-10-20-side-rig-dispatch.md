# SMALL-2: execute the requested side preparer

The CLI previously imported prepare_side for --side, but that module only invokes
its producer under its own __main__ guard. Importing did not create side assets.
The new entrypoint calls prepare_side.main() after the existing front pass.
Default front-only behavior stays unchanged and repeated --side flags call once.
Exceptions propagate rather than silently reporting successful side preparation.

Verification:

    RIG_SOURCE=tools/prepare_rig.py python3 -B tests/test_rig_dispatch.py -v

The test executes the exact CLI-dispatch AST from the specified source, with
front and side image-producing functions stubbed. Baseline:2 passed,3 failed.
Candidate:5 passed. py_compile also passed. No user image was opened, no derived
asset or release atlas was regenerated, and no graphical output/installed pet
validation is claimed. This focused dispatch test does not prove the separate
side image-processing pipeline succeeds for arbitrary inputs.

Risk: low, explicit invocation of the requested existing producer. Rollback:
revert the entrypoint change; no generated assets are included in this PR.
SMALL-1 release publication and SMALL-3 scale verification remain separate.
