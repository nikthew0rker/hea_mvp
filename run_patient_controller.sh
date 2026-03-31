#!/usr/bin/env bash
set -euo pipefail
uv run uvicorn agents.patient_controller.app:app --reload --port 8106
