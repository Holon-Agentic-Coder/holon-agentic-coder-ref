import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sandbox_executor.entrypoints import planner


class TestPlanner(unittest.TestCase):
    def test_get_file_structure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            # Create some mock files and directories
            (tmp_path / "dir1").mkdir()
            (tmp_path / "dir1" / "file1.py").write_text("print('hello')")
            (tmp_path / "dir2").mkdir()
            (tmp_path / ".git").mkdir()  # should be ignored
            (tmp_path / "dir1" / ".hidden").write_text("hidden")  # should be ignored

            structure = planner.get_file_structure(str(tmp_path))
            self.assertIn("dir1/", structure)
            self.assertIn("file1.py", structure)
            self.assertNotIn(".git", structure)
            self.assertNotIn(".hidden", structure)

    def test_parse_metrics(self):
        content = """
# Plan

| metric              | value                 |
|---------------------|-----------------------|
| p_success_pred      | 0.85                  |
| entropy_pred        | 2.1                   |
| impact_pred         | 1.0                   |
| cost_pred           | 0.4                   |
| learning_value_pred | 3.5                   |
| ev_pred             | 4.2                   |
"""
        metrics = planner.parse_metrics(content)
        self.assertEqual(metrics.get("p_success"), 0.85)
        self.assertEqual(metrics.get("entropy"), 2.1)
        self.assertEqual(metrics.get("impact"), 1.0)
        self.assertEqual(metrics.get("cost"), 0.4)
        self.assertEqual(metrics.get("learning_value"), 3.5)

    @patch("subprocess.run")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("os.makedirs")
    @patch("shutil.rmtree")
    def test_planner_main(self, mock_rmtree, mock_makedirs, mock_getsize, mock_exists, mock_run):
        test_args = ["planner.py", "I-12345/_", "test-agent", "gemini"]

        intent_data = {
            "branch": "I-12345",
            "intent_id": "I-12345",
            "description": "Test description",
            "goal": "Test goal",
            "entropy_budget": "15.0",
        }

        file_contents = {}

        def mock_open_impl(file, mode="r", *args, **kwargs):
            file_str = str(file)
            if "intents.jsonl" in file_str:
                mock_file = MagicMock()
                mock_file.__iter__.return_value = [json.dumps(intent_data) + "\n"]
                mock_file.__enter__.return_value = mock_file
                return mock_file
            elif "planner.template.md" in file_str:
                mock_file = MagicMock()
                mock_file.read.return_value = "Template content {intent_json} {plan_id} {safe_model}"
                mock_file.__enter__.return_value = mock_file
                return mock_file
            elif "plans/P-" in file_str and "md" in file_str and "r" in mode:
                mock_file = MagicMock()
                plan_md_content = """# Plan

## Overall Plan Metrics

| metric | value |
| p_success_pred | 0.8 |
| entropy_pred | 2.5 |
| impact_pred | 1.0 |
| cost_pred | 0.5 |
| learning_value_pred | 0.5 |
| ev_pred | 0.6 |
"""
                mock_file.read.return_value = plan_md_content
                mock_file.__enter__.return_value = mock_file
                return mock_file
            else:
                mock_file = MagicMock()
                mock_file.write = MagicMock()
                mock_file.__enter__.return_value = mock_file
                file_contents[file_str] = mock_file
                return mock_file

        def mock_exists_impl(path):
            path_str = str(path)
            if "intents.jsonl" in path_str or "planner.template.md" in path_str or "plans/P-" in path_str:
                return True
            return False

        mock_exists.side_effect = mock_exists_impl
        mock_getsize.return_value = 100

        mock_run_result = MagicMock()
        mock_run_result.returncode = 0
        mock_run_result.stdout = "Successful Agent Run Output"
        mock_run.return_value = mock_run_result

        # Directly modify and restore sys.argv
        old_argv = sys.argv
        sys.argv = test_args
        try:
            with patch("builtins.open", side_effect=mock_open_impl):
                planner.main()
        finally:
            sys.argv = old_argv

        self.assertGreaterEqual(mock_run.call_count, 5)
        called_cmds = [" ".join(call[0][0]) for call in mock_run.call_args_list]
        self.assertTrue(any("git clone" in cmd for cmd in called_cmds))
        self.assertTrue(any("git checkout -b" in cmd for cmd in called_cmds))
        self.assertTrue(any("pi -p" in cmd for cmd in called_cmds))
        self.assertTrue(any("git commit" in cmd for cmd in called_cmds))
        self.assertTrue(any("git push" in cmd for cmd in called_cmds))

        # Check plans.jsonl written
        plans_file = [k for k in file_contents.keys() if "plans.jsonl" in k][0]
        plans_mock = file_contents[plans_file]
        plans_mock.write.assert_called()
        plans_entry = json.loads(plans_mock.write.call_args[0][0].strip())
        self.assertEqual(plans_entry["p_success"], 0.8)
        self.assertEqual(plans_entry["entropy"], 2.5)

    @patch("subprocess.run")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    @patch("os.makedirs")
    @patch("shutil.rmtree")
    def test_planner_main_fail_fast(self, mock_rmtree, mock_makedirs, mock_getsize, mock_exists, mock_run):
        test_args = ["planner.py", "I-12345/_", "test-agent", "gemini"]

        intent_data = {
            "branch": "I-12345",
            "intent_id": "I-12345",
            "description": "Test description",
            "goal": "Test goal",
            "entropy_budget": "15.0",
        }

        def mock_open_impl(file, mode="r", *args, **kwargs):
            file_str = str(file)
            if "intents.jsonl" in file_str:
                mock_file = MagicMock()
                mock_file.__iter__.return_value = [json.dumps(intent_data) + "\n"]
                mock_file.__enter__.return_value = mock_file
                return mock_file
            elif "planner.template.md" in file_str:
                mock_file = MagicMock()
                mock_file.read.return_value = "Template content"
                mock_file.__enter__.return_value = mock_file
                return mock_file
            else:
                mock_file = MagicMock()
                mock_file.write = MagicMock()
                mock_file.__enter__.return_value = mock_file
                return mock_file

        def mock_exists_impl(path):
            path_str = str(path)
            if "intents.jsonl" in path_str:
                return True
            return False

        mock_exists.side_effect = mock_exists_impl
        mock_getsize.return_value = 0

        # Git commands succeed, but agent npx/pi command fails
        def mock_run_side_effect(args, *a, **kw):
            result = MagicMock()
            if args[0] in ["pi", "npx"]:
                result.returncode = 1
            else:
                result.returncode = 0
            return result

        mock_run.side_effect = mock_run_side_effect

        # Directly modify and restore sys.argv
        old_argv = sys.argv
        sys.argv = test_args
        try:
            with patch("builtins.open", side_effect=mock_open_impl):
                with self.assertRaises(SystemExit) as cm:
                    planner.main()
                self.assertEqual(cm.exception.code, 1)
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
