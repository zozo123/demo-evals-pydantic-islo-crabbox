# Runbook: toolchain version mismatch

## Signature

- `error: 'std::expected' is not a member of 'std'` (or other missing C++23 features)
- `unrecognized command-line option '-std=c++23'`
- `glibc` / `GLIBCXX` version errors at link or run time
- Local build uses clang 19, agents pinned to clang 16

## Diagnosis

The build agents run a different compiler version than the developer's
machine or than the project requires. Classify as **toolchain**.

## Fix

1. Pin the toolchain in repo config: `islo toolchain pin clang-19`.
2. Verify the agent pool image: `islo pool info --field toolchain`.
3. Rebuild after pinning; do NOT work around with per-file flags.
