#!/usr/bin/env bash
set -euo pipefail
uv run uvicorn agents.compiler_agent.app:app --reload --port 8102
