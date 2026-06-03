"""Offline stand-in model so the eval harness runs with zero API keys.

A `FunctionModel` that plays the agent's LLM: first turn it calls the
`search_runbooks` tool like a real model would, second turn it emits the
structured `TriageResult`.

It contains a DELIBERATE bug — on vague reports with no log it confidently
guesses instead of escalating. Exactly the kind of failure "it works when I
test it" never surfaces, and a realistic eval suite catches immediately
(anti-lesson #5).
"""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel


def _user_prompt(messages: list[ModelMessage]) -> str:
    for message in messages:
        for part in getattr(message, 'parts', []):
            if isinstance(part, UserPromptPart):
                return part.content if isinstance(part.content, str) else str(part.content)
    return ''


def _has_tool_return(messages: list[ModelMessage]) -> bool:
    return any(
        isinstance(part, ToolReturnPart)
        for message in messages
        for part in getattr(message, 'parts', [])
    )


def _heuristic_triage(prompt: str) -> dict[str, object]:
    text = prompt.lower()
    no_log = 'log excerpt: (none provided)' in text

    if 'signal 9' in text or 'killed' in text or 'cannot allocate memory' in text:
        return {
            'category': 'infra',
            'summary': 'The compiler was killed by the kernel OOM killer mid-build.',
            'suggested_fix': 'Reduce parallel jobs (islo config set jobs) or move the target to a larger memory agent class.',
            'confidence': 0.9,
            'escalate_to_human': False,
        }
    if 'cache' in text or 'no-cache' in text:
        return {
            'category': 'cache',
            'summary': 'A stale artifact from the distributed cache is poisoning the build.',
            'suggested_fix': 'Re-run with islo build --no-cache to confirm, then islo cache evict --target for the poisoned entries.',
            'confidence': 0.85,
            'escalate_to_human': False,
        }
    if 'timeout' in text or 'intermittent' in text or 'passes on retry' in text or 'connection reset' in text:
        return {
            'category': 'flaky-test',
            'summary': 'The failure is intermittent and matches the flaky-test signature, not the diff.',
            'suggested_fix': 'Re-run in isolation with islo test --repeat 10, then quarantine the test if pass rate < 100%.',
            'confidence': 0.8,
            'escalate_to_human': False,
        }
    if "std::expected" in text or 'unrecognized command-line option' in text or 'glibcxx' in text:
        return {
            'category': 'toolchain',
            'summary': 'The build agents run an older compiler than the project requires.',
            'suggested_fix': 'Pin the toolchain with islo toolchain pin clang-19 and verify the pool image.',
            'confidence': 0.85,
            'escalate_to_human': False,
        }
    if no_log:
        # THE DELIBERATE BUG: should escalate with low confidence; instead it
        # guesses 'infra' at 0.9 and keeps the human in the trunk.
        return {
            'category': 'infra',
            'summary': 'Probably an infrastructure hiccup on the build agents.',
            'suggested_fix': 'Restart the agent pool and retry the build.',
            'confidence': 0.9,
            'escalate_to_human': False,
        }
    return {
        'category': 'unknown',
        'summary': 'The log does not match any known signature.',
        'suggested_fix': 'Collect a full build log and loop in the build-infra on-call.',
        'confidence': 0.2,
        'escalate_to_human': True,
    }


def _policy(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    prompt = _user_prompt(messages)

    if not _has_tool_return(messages):
        # Turn 1: behave like a real model — consult the runbooks first.
        return ModelResponse(
            parts=[ToolCallPart(tool_name='search_runbooks', args={'query': prompt[:200]})]
        )

    # Turn 2: emit the structured TriageResult via the output tool.
    output_tool = info.output_tools[0]
    return ModelResponse(
        parts=[ToolCallPart(tool_name=output_tool.name, args=_heuristic_triage(prompt))]
    )


def offline_model() -> FunctionModel:
    return FunctionModel(_policy)
