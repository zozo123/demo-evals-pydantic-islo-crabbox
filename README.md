# Realistic Evals for a Pydantic AI Agent — runnable demo

> *"Unlike unit tests, evals are an emerging art/science. Anyone who claims to know
> exactly how your evals should be defined can safely be ignored."*
> — Pydantic Evals docs, as quoted at PyCon DE 2026

A complete, runnable demo of [Pydantic Evals](https://pydantic.dev/docs/ai/evals/)
grading a [Pydantic AI](https://ai.pydantic.dev) agent, built around the seven
anti-lessons from Joshua Görner's PyCon DE talk *"7 Anti-Lessons from Building a
Pydantic AI Agent"* — and runnable on a disposable Linux box via
[crabbox](https://crabbox.sh).

## What's in the box

| Anti-lesson from the talk | Where it lives here |
|---|---|
| "We need a multi-agent system" → one agent | `agent/triage_agent.py` — exactly one `Agent` |
| "Lots of specific tools" → two high-level tools | `search_runbooks` + `get_build_context`, nothing else |
| "Encode workflows in code" → markdown at runtime | `agent/workflows/triage.md`, read into instructions at startup |
| "Sophisticated planning" → simple procedure | the workflow is a numbered list |
| "It works when I test it" → realistic evals | `evals/dataset.py` — vague, angry, ambiguous real journeys |
| "Automate everything" → human in the driver's seat | `EscalationPolicy` evaluator asserts the agent escalates when uncertain |
| "Apply what made you successful before" | deterministic checks first, LLM-as-judge only where code can't grade |

The demo agent triages **build failures** for a build-acceleration platform
(islo.dev flavored): a developer pastes a broken-build log, the agent classifies
it (cache poisoning / toolchain drift / flaky test / OOM / source bug), suggests
a concrete fix, and — crucially — escalates to a human when the evidence is thin.

## Run it

### 1. Offline — zero API keys, 10 seconds

```bash
uv sync
uv run python -m evals.run_evals
```

The agent runs against a deterministic `FunctionModel` stub
(`agent/offline_model.py`) that contains a **deliberate bug**: on vague reports
with no log it confidently guesses instead of escalating. Watch the eval suite
catch it:

```
PASS: assertion pass rate 91.7% (threshold 60%)

Failing cases:
  - vague_angry_no_log: EscalationPolicy, NoDestructiveGuessing
```

That failing row is the whole point. A happy-path manual test ("I pasted an OOM
log and it answered correctly, ship it") never executes this journey. The eval
suite does, every run.

### 2. Live — real model + LLM judge

```bash
export ANTHROPIC_API_KEY=...
uv run python -m evals.run_evals          # auto-switches to live mode
```

Live mode runs the agent on `claude-haiku-4-5` and adds an `LLMJudge` evaluator
that grades fix quality against a rubric (concrete, runnable, evidence-based) —
the layer of grading that deterministic code can't express.

### 3. Remote — on a disposable box via crabbox

```bash
crabbox run -provider apple-container -- bash scripts/run_evals_remote.sh
# or, with the repo-local job:
crabbox job run evals
```

crabbox leases a box, rsyncs your dirty checkout, bootstraps `uv`, runs the
suite, streams the report back, and releases the lease. Measured cold run:
**6.2s end-to-end** on the local `apple-container` provider. Swap
`-provider hetzner` / `-provider islo` for real CI fleets — same command.

## Eval design notes

- **Expectations are metadata, not expected outputs.** Each `Case` carries
  `expected_category`, `acceptable_categories`, `must_escalate`, `fix_keywords`
  — custom evaluators read these, so the dataset stays declarative and partial
  credit is possible (`CategoryMatches` returns 1.0 / 0.5 / 0.0).
- **Assertions vs scores.** Policy invariants (`EscalationPolicy`,
  `NoDestructiveGuessing`) are booleans that gate CI. Quality measures
  (`CategoryMatches`, `FixMentions`) are floats you track over time.
- **The threshold is honest.** `EVAL_MIN_PASS=0.6` — the suite is *supposed* to
  have failing cases while behavior is imperfect. An eval suite at 100% from
  day one is measuring nothing.

## Layout

```
agent/
  triage_agent.py     # the agent: 1 agent, 2 tools, structured TriageResult output
  offline_model.py    # FunctionModel stub w/ deliberate bug (no API key needed)
  workflows/triage.md # the runtime-read markdown workflow
  runbooks/*.md       # what search_runbooks greps
evals/
  dataset.py          # 6 realistic journeys w/ metadata-driven expectations
  evaluators.py       # CategoryMatches, EscalationPolicy, FixMentions, NoDestructiveGuessing
  run_evals.py        # entrypoint: offline/live modes, CI exit code
scripts/
  run_evals_remote.sh # bootstrap + run on a fresh crabbox box
.crabbox.yaml         # repo-local crabbox config + `evals` job
```
