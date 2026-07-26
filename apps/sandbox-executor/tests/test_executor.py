import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sandbox_executor.entrypoint import executor


class TestExecutor(unittest.TestCase):
    def test_should_decompose_high_entropy(self):
        plan_data = {"entropy": 6.0, "entropy_budget": 5.0, "plan_id": "P-test"}
        plan_content = "# Plan\nSome plan"
        decompose, sub_intents = executor.should_decompose(plan_data, plan_content)
        self.assertTrue(decompose)
        self.assertGreater(len(sub_intents), 0)

    def test_should_decompose_sub_intents_section(self):
        plan_data = {"entropy": 2.0, "entropy_budget": 5.0}
        plan_content = """# Plan
## Sub-Intents
- Create DB schema
- Build API routes
"""
        decompose, sub_intents = executor.should_decompose(plan_data, plan_content)
        self.assertTrue(decompose)
        self.assertEqual(len(sub_intents), 2)
        self.assertEqual(sub_intents[0]["slug"], "create-db-schema")
        self.assertEqual(sub_intents[1]["slug"], "build-api-routes")

    def test_should_not_decompose_low_entropy(self):
        plan_data = {"entropy": 2.0, "entropy_budget": 5.0}
        plan_content = "# Plan\nStandard plan without sub-intents"
        decompose, sub_intents = executor.should_decompose(plan_data, plan_content)
        self.assertFalse(decompose)
        self.assertEqual(len(sub_intents), 0)

    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    def test_main_execution_flow(self, mock_get_repo_url, mock_get_runner, mock_run_cmd):
        mock_get_repo_url.return_value = "/mock/repo"
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("os.path.expanduser", return_value=tmp_dir):
                # Create fake holon-knowledge/ledger
                ledger_dir = os.path.join(tmp_dir, "holon-knowledge/ledger")
                os.makedirs(ledger_dir, exist_ok=True)
                with open(os.path.join(ledger_dir, "plans.jsonl"), "w") as f:
                    f.write(
                        json.dumps(
                            {
                                "plan_id": "P-123",
                                "intent_branch": "I-456/_",
                                "entropy": 2.0,
                                "entropy_budget": 5.0,
                            }
                        )
                        + "\n"
                    )

                with patch(
                    "sys.argv", ["executor.py", "I-456/P-123/_", "antigravity-agent", "gemini-3.5-flash"]
                ):
                    executor.main()

                mock_runner.validate.assert_called_once()
                self.assertTrue(os.path.exists(os.path.join(ledger_dir, "executions.jsonl")))
                with open(os.path.join(ledger_dir, "executions.jsonl")) as ef:
                    content = ef.read()
                    self.assertIn("P-123", content)
                    self.assertIn("success", content)


if __name__ == "__main__":
    unittest.main()
