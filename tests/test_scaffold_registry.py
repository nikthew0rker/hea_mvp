from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hea.shared import scaffold_registry  # noqa: E402
from hea.shared.scaffold_registry import get_scaffold, infer_scaffold_framework, infer_scaffold_topic  # noqa: E402


class ScaffoldRegistryTests(unittest.TestCase):
    def tearDown(self) -> None:
        scaffold_registry.reload_scaffold_catalog()

    def test_infers_findrisk_diabetes(self) -> None:
        self.assertEqual(infer_scaffold_topic("я хочу собрать findrisk диабета"), "diabetes")
        self.assertEqual(infer_scaffold_framework("я хочу собрать findrisk диабета"), "findrisk")

    def test_returns_findrisk_scaffold(self) -> None:
        scaffold = get_scaffold("diabetes", "findrisk")
        self.assertEqual(scaffold["understood"]["framework"], "findrisk")
        self.assertEqual(len(scaffold["candidate_questions"]), 8)
        self.assertEqual(scaffold["_proposal_meta"]["strategy_id"], "diabetes/findrisk")

    def test_unknown_topic_returns_empty_scaffold(self) -> None:
        self.assertEqual(get_scaffold("unknown", None), {})

    def test_loads_catalog_from_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            catalog_path = Path(tmp_dir) / "catalog.json"
            catalog_path.write_text(
                """
                {
                  "strategies": [
                    {
                      "strategy_id": "custom/default",
                      "topic": "custom",
                      "question_source_summary": "custom scaffold",
                      "scaffold": {
                        "understood": {"topic": "custom"},
                        "candidate_questions": [{"id": "q1", "text": "Custom?", "source": "custom scaffold", "options": []}],
                        "candidate_scoring_rules": {"method": "sum"},
                        "candidate_risk_bands": [],
                        "candidate_report_requirements": [],
                        "candidate_safety_requirements": [],
                        "missing_fields": []
                      }
                    }
                  ]
                }
                """.strip(),
                encoding="utf-8",
            )
            original_path = scaffold_registry.CATALOG_PATH
            scaffold_registry.CATALOG_PATH = catalog_path
            scaffold_registry.reload_scaffold_catalog()
            try:
                scaffold = get_scaffold("custom", None)
                self.assertEqual(scaffold["understood"]["topic"], "custom")
                self.assertEqual(scaffold["_proposal_meta"]["strategy_id"], "custom/default")
            finally:
                scaffold_registry.CATALOG_PATH = original_path
                scaffold_registry.reload_scaffold_catalog()


if __name__ == "__main__":
    unittest.main()
