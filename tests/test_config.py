from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "src" / "hea" / "shared" / "config.py"
TOGETHER_CLIENT_PATH = PROJECT_ROOT / "src" / "hea" / "shared" / "together_client.py"
MODEL_ROUTER_PATH = PROJECT_ROOT / "src" / "hea" / "shared" / "model_router.py"


class ConfigTests(unittest.TestCase):
    def test_config_anchors_relative_db_path_to_project_root(self) -> None:
        source = CONFIG_PATH.read_text(encoding="utf-8")
        self.assertIn("PROJECT_ROOT = Path(__file__).resolve().parents[3]", source)
        self.assertIn("path = PROJECT_ROOT / path", source)

    def test_json_safeguard_blocks_gpt_oss_for_structured_calls(self) -> None:
        source = TOGETHER_CLIENT_PATH.read_text(encoding="utf-8")
        self.assertIn('JSON_UNSAFE_MODELS = {', source)
        self.assertIn('"openai/gpt-oss-120b"', source)
        self.assertIn("def _json_safe_model", source)

    def test_model_router_logs_startup_warning_for_unsafe_json_roles(self) -> None:
        source = MODEL_ROUTER_PATH.read_text(encoding="utf-8")
        self.assertIn("def log_model_configuration_warnings", source)
        self.assertIn("JSON-unsafe Together model configured for %s role", source)


if __name__ == "__main__":
    unittest.main()
