"""islo.dev build-failure triage agent.

Built the way the PyCon DE talk says to build it:

- ONE agent, not a multi-agent system           (anti-lesson #1)
- TWO high-level tools, not dozens              (anti-lesson #3)
- The workflow lives in markdown, read at
  runtime, not encoded in Python control flow   (anti-lesson #4)
- Uncertainty escalates to a human              (anti-lesson #6)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

PACKAGE_ROOT = Path(__file__).parent
RUNBOOKS_DIR = PACKAGE_ROOT / 'runbooks'
WORKFLOW_PATH = PACKAGE_ROOT / 'workflows' / 'triage.md'

Category = Literal['cache', 'toolchain', 'flaky-test', 'source-bug', 'infra', 'unknown']


class BuildFailure(BaseModel):
    """What a developer reports when their build breaks."""

    build_id: str = ''
    user_message: str
    log_excerpt: str = ''


class TriageResult(BaseModel):
    """The agent's structured verdict."""

    category: Category
    summary: str
    suggested_fix: str
    confidence: float = Field(ge=0.0, le=1.0)
    escalate_to_human: bool


# A tiny fake build-metadata "API" — in production this is one OpenAPI-backed
# high-level tool instead of a dozen bespoke ones.
BUILD_METADATA: dict[str, dict[str, object]] = {
    'b-7741': {'agent_class': 'standard-16gb', 'cache_hit_rate': 0.91, 'toolchain': 'clang-19', 'retries': 0},
    'b-7742': {'agent_class': 'standard-16gb', 'cache_hit_rate': 0.97, 'toolchain': 'clang-19', 'retries': 0},
    'b-7743': {'agent_class': 'ci-pool-a', 'cache_hit_rate': 0.42, 'toolchain': 'clang-16', 'retries': 0},
    'b-7744': {'agent_class': 'ci-pool-b', 'cache_hit_rate': 0.88, 'toolchain': 'clang-19', 'retries': 3},
}


def build_agent(model: object | None = None) -> Agent[None, TriageResult]:
    """Create the triage agent. `model` overrides the default (used for offline evals)."""
    workflow = WORKFLOW_PATH.read_text()

    agent: Agent[None, TriageResult] = Agent(
        model or os.environ.get('TRIAGE_MODEL', 'anthropic:claude-haiku-4-5'),
        output_type=TriageResult,
        retries=2,
        instructions=(
            'Follow this workflow exactly. It is the source of truth for how you triage.\n\n'
            + workflow
        ),
    )

    @agent.tool_plain
    def search_runbooks(query: str) -> str:
        """Search the operations runbooks for guidance matching the query.

        Returns the full text of the best-matching runbooks.
        """
        terms = [t.lower() for t in query.split() if len(t) > 2]
        scored: list[tuple[int, str, str]] = []
        for path in sorted(RUNBOOKS_DIR.glob('*.md')):
            text = path.read_text()
            lower = text.lower()
            score = sum(lower.count(t) for t in terms)
            if score:
                scored.append((score, path.name, text))
        scored.sort(reverse=True)
        if not scored:
            return 'No runbook matched. Consider escalating to a human.'
        return '\n\n---\n\n'.join(f'[{name}]\n{text}' for _, name, text in scored[:2])

    @agent.tool_plain
    def get_build_context(build_id: str) -> dict[str, object]:
        """Fetch build metadata (agent class, cache hit rate, toolchain, retries) by build id."""
        return BUILD_METADATA.get(build_id, {'error': f'unknown build id {build_id!r}'})

    return agent


def format_failure(failure: BuildFailure) -> str:
    """Render a BuildFailure as the user prompt."""
    parts = [f'Build ID: {failure.build_id or "(not provided)"}', f'User says: {failure.user_message}']
    if failure.log_excerpt:
        parts.append(f'Log excerpt:\n```\n{failure.log_excerpt}\n```')
    else:
        parts.append('Log excerpt: (none provided)')
    return '\n\n'.join(parts)
