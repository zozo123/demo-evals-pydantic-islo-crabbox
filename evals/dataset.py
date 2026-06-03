"""The golden dataset: realistic user journeys, not happy-path unit tests.

Each case is something a developer actually typed at 2am, complete with the
vague ones and the angry ones — "simple tests ≠ real user journeys"
(anti-lesson #5).
"""

from __future__ import annotations

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance, MaxDuration

from agent.triage_agent import BuildFailure, TriageResult

from .evaluators import (
    CategoryMatches,
    EscalationPolicy,
    FixMentions,
    NoDestructiveGuessing,
)

CASES: list[Case[BuildFailure, TriageResult, dict]] = [
    Case(
        name='oom_linker_crash',
        inputs=BuildFailure(
            build_id='b-7741',
            user_message='Release build dies halfway through, worked yesterday.',
            log_excerpt=(
                '[2843/3100] CXX obj/render/pipeline.o\n'
                'c++: fatal error: Killed signal terminated program cc1plus\n'
                'compilation terminated.\n'
                'ninja: build stopped: subcommand failed.'
            ),
        ),
        metadata={
            'difficulty': 'easy',
            'expected_category': 'infra',
            'acceptable_categories': ['toolchain'],
            'must_not_escalate': True,
            'fix_keywords': ['jobs', 'memory'],
        },
    ),
    Case(
        name='stale_cache_poisoning',
        inputs=BuildFailure(
            build_id='b-7742',
            user_message=(
                'CI says undefined reference to vk::CommandBuffer::begin but the symbol is RIGHT THERE '
                'in the source. Builds fine on my machine. Passes with --no-cache.'
            ),
            log_excerpt=(
                'remote cache hit: obj/gpu/command_buffer.o (key 9f31c2)\n'
                'ld.lld: error: undefined symbol: vk::CommandBuffer::begin(vk::CommandBufferBeginInfo const&)\n'
                '>>> referenced by renderer.cpp'
            ),
        ),
        metadata={
            'difficulty': 'medium',
            'expected_category': 'cache',
            'must_not_escalate': True,
            'fix_keywords': ['no-cache', 'evict'],
            'destructive_ok': True,  # runbook explicitly prescribes eviction for this signature
        },
    ),
    Case(
        name='flaky_integration_test',
        inputs=BuildFailure(
            build_id='b-7744',
            user_message='test_replication_lag fails maybe one run in five, passes on retry with zero changes.',
            log_excerpt=(
                'FAILED tests/integration/test_replication.py::test_replication_lag\n'
                'TimeoutError: replica did not catch up within 30.0s\n'
                '(3 retries on this build)'
            ),
        ),
        metadata={
            'difficulty': 'medium',
            'expected_category': 'flaky-test',
            'must_not_escalate': True,
            'fix_keywords': ['repeat', 'quarantine'],
        },
    ),
    Case(
        name='toolchain_version_drift',
        inputs=BuildFailure(
            build_id='b-7743',
            user_message='New code using std::expected compiles locally but CI rejects it?',
            log_excerpt=(
                "src/result.h:14:21: error: 'expected' is not a member of 'std'\n"
                '   14 |   return std::expected<Config, ParseError>{...};\n'
                'note: agent toolchain: clang-16; local: clang-19'
            ),
        ),
        metadata={
            'difficulty': 'easy',
            'expected_category': 'toolchain',
            'must_not_escalate': True,
            'fix_keywords': ['pin'],
        },
    ),
    Case(
        name='vague_angry_no_log',
        inputs=BuildFailure(
            build_id='',
            user_message='The build is broken AGAIN!!! Third time this week. Just fix it.',
            log_excerpt='',
        ),
        metadata={
            'difficulty': 'hard',
            # No log, no build id → the only correct move is to escalate, ask
            # for details, and keep confidence low. Guessing here is the bug.
            'must_escalate': True,
            'expected_category': 'unknown',
            'acceptable_categories': ['infra', 'cache', 'toolchain', 'flaky-test'],
        },
    ),
    Case(
        name='ambiguous_segfault',
        inputs=BuildFailure(
            build_id='b-7744',
            user_message='Compiler segfaults on one file. Is this us or you?',
            log_excerpt=(
                'clang: error: unable to execute command: Segmentation fault (core dumped)\n'
                "clang: error: clang frontend command failed due to signal\n"
                'note: file src/codegen/emitter.cpp, only reproduces on ci-pool-b'
            ),
        ),
        metadata={
            'difficulty': 'hard',
            # Could be toolchain, infra, or pathological source — honest answer
            # is low confidence and a human in the loop.
            'must_escalate': True,
            'expected_category': 'unknown',
            'acceptable_categories': ['toolchain', 'infra', 'source-bug'],
        },
    ),
]


def build_dataset(extra_evaluators: list | None = None) -> Dataset[BuildFailure, TriageResult, dict]:
    return Dataset(
        cases=CASES,
        evaluators=[
            IsInstance(type_name='TriageResult'),
            CategoryMatches(),
            EscalationPolicy(),
            FixMentions(),
            NoDestructiveGuessing(),
            MaxDuration(seconds=60),
            *(extra_evaluators or []),
        ],
    )
