#!/usr/bin/env bash
set -euo pipefail
uv run uvicorn agents.runtime_agent.app:app --reload --port 8103
