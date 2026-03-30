#!/usr/bin/env bash
set -euo pipefail
uv run uvicorn agents.definition_agent.app:app --reload --port 8101
