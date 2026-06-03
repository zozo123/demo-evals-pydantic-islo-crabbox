# Runbook: OOM and resource exhaustion on build agents

## Signature

- `c++: fatal error: Killed signal terminated program cc1plus`
- `signal 9`, `SIGKILL`, `Cannot allocate memory`
- Linker (`ld`, `lld`) killed mid-link on large targets

## Diagnosis

The build agent ran out of memory, usually during heavily parallel C++
compilation or a fat LTO link step. This is **infra**, not a source bug.

## Fix

1. Reduce parallel compile jobs on that agent class: `islo config set jobs=<n/2>`.
2. Move fat-LTO link targets to the `beast` agent class (64 GB).
3. If recurring, raise the per-job memory reservation in the pool config.
