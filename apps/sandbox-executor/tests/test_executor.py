import json
import os
import subprocess
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

    def test_safe_float(self):
        self.assertEqual(executor._safe_float(None, 5.0), 5.0)
        self.assertEqual(executor._safe_float(None), 0.0)
        self.assertEqual(executor._safe_float(3.14), 3.14)
        self.assertEqual(executor._safe_float("2.5"), 2.5)
        self.assertEqual(executor._safe_float("invalid", 1.0), 1.0)

    def test_should_decompose_numbered_list(self):
        plan_data = {"entropy": 2.0, "entropy_budget": 5.0}
        plan_content = """# Plan
## Sub-Intents
1. Create DB schema
2. Build API routes
3. Write unit tests
"""
        decompose, sub_intents = executor.should_decompose(plan_data, plan_content)
        self.assertTrue(decompose)
        self.assertEqual(len(sub_intents), 3)
        self.assertEqual(sub_intents[0]["slug"], "create-db-schema")
        self.assertEqual(sub_intents[1]["slug"], "build-api-routes")
        self.assertEqual(sub_intents[2]["slug"], "write-unit-tests")

    def test_should_decompose_none_entropy(self):
        plan_data = {"entropy": None, "entropy_budget": None}
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
        mock_runner.build_cmd.return_value = ["agy", "--model", "gemini-3.5-flash", "prompt"]
        mock_get_runner.return_value = mock_runner

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"

        def side_effect(args, cwd=None, **kwargs):
            if "clone" in args:
                ledger_dir = os.path.join(cwd, "holon-knowledge/ledger")
                os.makedirs(ledger_dir, exist_ok=True)
                with open(os.path.join(ledger_dir, "plans.jsonl"), "w") as f:
                    f.write(json.dumps({"plan_id": None}) + "\n")
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
            return mock_result

        mock_run_cmd.side_effect = side_effect

        with (
            tempfile.TemporaryDirectory(prefix="sandbox_executor_test_") as tmp_dir,
            patch.dict(os.environ, {"HOLON_REPO_DIR": tmp_dir, "HOLON_SKIP_PUSH": "1"}),
        ):
            ledger_dir = os.path.join(tmp_dir, "holon-knowledge/ledger")

            with patch("sys.argv", ["executor.py", "I-456/P-123/_", "antigravity-agent", "gemini-3.5-flash"]):
                executor.main()

            mock_runner.validate.assert_called_once()
            mock_runner.build_cmd.assert_called_once()
            self.assertTrue(os.path.exists(os.path.join(ledger_dir, "executions.jsonl")))
            with open(os.path.join(ledger_dir, "executions.jsonl")) as ef:
                content = ef.read()
                self.assertIn("P-123", content)
                self.assertIn("success", content)

    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    def test_main_decomposition_flow(self, mock_get_repo_url, mock_get_runner, mock_run_cmd):
        mock_get_repo_url.return_value = "/mock/repo"
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        mock_result = MagicMock()
        mock_result.returncode = 0

        def side_effect(args, cwd=None, **kwargs):
            if "clone" in args:
                ledger_dir = os.path.join(cwd, "holon-knowledge/ledger")
                os.makedirs(ledger_dir, exist_ok=True)
                with open(os.path.join(ledger_dir, "plans.jsonl"), "w") as f:
                    f.write(
                        json.dumps(
                            {
                                "plan_id": "P-123",
                                "intent_branch": "I-456/_",
                                "entropy": 8.0,
                                "entropy_budget": 5.0,
                            }
                        )
                        + "\n"
                    )
                with open(os.path.join(ledger_dir, "intents.jsonl"), "w") as f:
                    f.write(
                        json.dumps(
                            {
                                "branch": "I-456/_",
                                "slug": "parent-intent",
                            }
                        )
                        + "\n"
                    )
            return mock_result

        mock_run_cmd.side_effect = side_effect

        with (
            tempfile.TemporaryDirectory(prefix="sandbox_executor_test_") as tmp_dir,
            patch.dict(os.environ, {"HOLON_REPO_DIR": tmp_dir, "HOLON_SKIP_PUSH": "1"}),
        ):
            ledger_dir = os.path.join(tmp_dir, "holon-knowledge/ledger")

            with patch("sys.argv", ["executor.py", "I-456/P-123/_", "antigravity-agent", "gemini-3.5-flash"]):
                executor.main()

            mock_runner.validate.assert_called_once()
            self.assertTrue(os.path.exists(os.path.join(ledger_dir, "executions.jsonl")))
            with open(os.path.join(ledger_dir, "executions.jsonl")) as ef:
                content = ef.read()
                self.assertIn("P-123", content)
                self.assertIn("decomposed", content)
            self.assertTrue(os.path.exists(os.path.join(ledger_dir, "intents.jsonl")))
            with open(os.path.join(ledger_dir, "intents.jsonl")) as inf:
                content = inf.read()
                self.assertIn("sub-intent-part-1", content)

    def test_run_cmd_raises_called_process_error(self):
        with self.assertRaises(subprocess.CalledProcessError) as ctx:
            executor.run_cmd(["false"], check=True)
        self.assertEqual(ctx.exception.returncode, 1)

    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    def test_main_custom_holon_repo_dir_not_deleted(self, mock_get_repo_url, mock_get_runner, mock_run_cmd):
        mock_get_repo_url.return_value = "/mock/repo"
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run_cmd.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmp_dir:
            custom_dir = os.path.join(tmp_dir, "custom_repo")
            os.makedirs(custom_dir, exist_ok=True)
            with (
                patch.dict(os.environ, {"HOLON_REPO_DIR": custom_dir, "HOLON_SKIP_PUSH": "1"}),
                patch("sys.argv", ["executor.py", "I-456/P-123/_"]),
            ):
                executor.main()

            self.assertTrue(os.path.exists(custom_dir))

    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    @patch("sandbox_executor.entrypoint.executor.os.path.expanduser")
    @patch("sandbox_executor.entrypoint.executor.shutil.rmtree")
    def test_main_default_workspace_deleted(
        self, mock_rmtree, mock_expanduser, mock_get_repo_url, mock_get_runner, mock_run_cmd
    ):
        mock_get_repo_url.return_value = "/mock/repo"
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run_cmd.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmp_dir:
            default_dir = os.path.join(tmp_dir, "repo")
            mock_expanduser.return_value = default_dir
            os.makedirs(default_dir, exist_ok=True)

            env = os.environ.copy()
            if "HOLON_REPO_DIR" in env:
                del env["HOLON_REPO_DIR"]
            env["HOLON_SKIP_PUSH"] = "1"

            with (
                patch.dict(os.environ, env, clear=True),
                patch("sys.argv", ["executor.py", "I-456/P-123/_"]),
            ):
                executor.main()

            self.assertTrue(mock_rmtree.called)
            mock_rmtree.assert_called_with(default_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
