# Runbook: distributed cache corruption / stale hits

## Signature

- Build succeeds locally but fails on CI with impossible errors
  (e.g. `undefined reference` to a symbol that exists in the source)
- Object files with mismatched compiler flags pulled from cache
- `cache hit` lines immediately followed by link errors
- Errors disappear after `--no-cache` rebuild

## Diagnosis

A stale or corrupt artifact in the distributed cache is being substituted
for a fresh compile. Classify as **cache**.

## Fix

1. Confirm: re-run the failing target with `islo build --no-cache <target>`.
2. If it passes, evict the poisoned entries: `islo cache evict --target <target>`.
3. Check for non-hermetic inputs (timestamps, `__DATE__`, absolute paths)
   that defeat cache keys.

Cache eviction is destructive — prescribe it only when the signature above
matches; otherwise escalate.
