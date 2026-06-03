#!/usr/bin/env bash
# Run the Pydantic Evals suite on a crabbox box (fresh Ubuntu, nothing preinstalled).
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync --frozen --quiet
exec uv run python -m evals.run_evals
