#!/usr/bin/env bash
set -euo pipefail
uv run uvicorn agents.evaluation_agent.app:app --reload --port 8105
