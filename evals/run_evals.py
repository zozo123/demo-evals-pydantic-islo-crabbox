"""Run the triage-agent eval suite.

Modes (auto-detected, override with EVAL_MODE=offline|live):

- offline  — no API key needed. The agent runs against a deterministic
             FunctionModel stub with a deliberate escalation bug, so you can
             watch the eval suite catch it.
- live     — ANTHROPIC_API_KEY set. The agent runs on a real Claude model and
             an LLMJudge evaluator grades fix quality against a rubric.

Exit code is non-zero when the assertion pass rate drops below EVAL_MIN_PASS
(default 0.6), so this slots straight into CI — or a crabbox box.
"""

from __future__ import annotations

import os
import sys

from agent.offline_model import offline_model
from agent.triage_agent import BuildFailure, TriageResult, build_agent, format_failure
from evals.dataset import build_dataset


def main() -> int:
    mode = os.environ.get('EVAL_MODE') or ('live' if os.environ.get('ANTHROPIC_API_KEY') else 'offline')

    extra_evaluators = []
    if mode == 'live':
        from pydantic_evals.evaluators import LLMJudge

        agent = build_agent()
        extra_evaluators.append(
            LLMJudge(
                rubric=(
                    'The suggested fix must be concrete and runnable by the developer '
                    '(specific commands or config changes, not "investigate further"), '
                    'must follow from the evidence in the input, and the summary must '
                    'be plain language a non-build-expert understands.'
                ),
                include_input=True,
                model='anthropic:claude-haiku-4-5',
            )
        )
    else:
        agent = build_agent(model=offline_model())

    async def triage(inputs: BuildFailure) -> TriageResult:
        result = await agent.run(format_failure(inputs))
        return result.output

    dataset = build_dataset(extra_evaluators)
    print(f'mode={mode}  cases={len(dataset.cases)}\n')
    report = dataset.evaluate_sync(triage, name=f'triage-agent[{mode}]')
    report.print(include_input=False, include_output=True)

    averages = report.averages()
    pass_rate = averages.assertions if averages and averages.assertions is not None else 0.0
    min_pass = float(os.environ.get('EVAL_MIN_PASS', '0.6'))
    status = 'PASS' if pass_rate >= min_pass else 'FAIL'
    print(f'\n{status}: assertion pass rate {pass_rate:.1%} (threshold {min_pass:.0%})')

    if pass_rate < 1.0:
        print('\nFailing cases:')
        for case in report.cases:
            failed = [a for a in case.assertions.values() if not a.value]
            if failed:
                names = ', '.join(a.source.name if hasattr(a.source, "name") else str(a.source) for a in failed)
                print(f'  - {case.name}: {names}')

    return 0 if pass_rate >= min_pass else 1


if __name__ == '__main__':
    sys.exit(main())
