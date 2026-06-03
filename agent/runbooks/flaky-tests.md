# Runbook: flaky / intermittent test failures

## Signature

- Same commit passes on retry with no changes
- `TimeoutError`, `connection reset`, port-already-in-use in test logs
- Failures correlate with agent load, not with the diff

## Diagnosis

Intermittent failure, usually a race condition or an external-dependency
timeout in the test itself. Classify as **flaky-test** — do NOT blame the
user's diff without evidence the failure reproduces deterministically.

## Fix

1. Re-run the test in isolation 10×: `islo test --repeat 10 <test>`.
2. If pass rate < 100%, quarantine it: `islo test quarantine <test>` and file
   a ticket against the owning team.
3. Look for hardcoded ports, shared tmp dirs, or wall-clock assertions.
