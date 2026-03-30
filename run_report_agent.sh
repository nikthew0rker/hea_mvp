#!/usr/bin/env bash
set -euo pipefail
uv run uvicorn agents.report_agent.app:app --reload --port 8104
