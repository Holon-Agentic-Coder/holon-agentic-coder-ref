import os
import unittest
from unittest.mock import MagicMock, patch

from sandbox_executor.cli import (
    find_github_token,
    get_agent_session_mounts,
    get_ssh_auth_mounts,
    main,
    run_docker_container,
)


class TestHolonCLI(unittest.TestCase):
    def test_find_github_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "gh_test_token_123"}):
            self.assertEqual(find_github_token(), "gh_test_token_123")

    def test_get_ssh_auth_mounts(self):
        mounts, envs = get_ssh_auth_mounts()
        self.assertIsInstance(mounts, list)
        self.assertIsInstance(envs, dict)

    def test_get_agent_session_mounts(self):
        antigravity_mounts = get_agent_session_mounts("antigravity")
        self.assertIsInstance(antigravity_mounts, list)

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/docker")
    def test_run_docker_container(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with patch.dict(os.environ, {"GITHUB_TOKEN": "secret_token"}):
            code = run_docker_container("planner", "holon/agent-antigravity", ["branch", "agent", "model"])
            self.assertEqual(code, 0)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertIn("docker", args)
            self.assertIn("GITHUB_TOKEN=secret_token", args)

    @patch("sandbox_executor.cli.run_docker_container", return_value=0)
    def test_main_subcommands(self, mock_run_container):
        test_args = [
            "holon",
            "plan",
            "intent_branch_name",
            "--agent",
            "antigravity-agent",
            "--model",
            "gemini-3.5-flash",
        ]
        with patch("sys.argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_container.assert_called_once_with(
                "planner",
                "holon/agent-antigravity",
                ["intent_branch_name", "antigravity-agent", "gemini-3.5-flash"],
                agent_id="antigravity",
            )

        mock_run_container.reset_mock()
        test_intent_args = ["holon", "intent", "intents/test.json"]
        with patch("sys.argv", test_intent_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_container.assert_called_once_with(
                "intent-creator",
                "holon/orchestrator",
                [],
                agent_id="antigravity",
                intent_file="intents/test.json",
            )

        mock_run_container.reset_mock()
        test_exec_args = [
            "holon",
            "execute",
            "plan_branch_name",
            "--agent",
            "antigravity-agent",
            "--model",
            "gemini-3.5-flash",
        ]
        with patch("sys.argv", test_exec_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_container.assert_called_once_with(
                "executor",
                "holon/agent-antigravity",
                ["plan_branch_name", "antigravity-agent", "gemini-3.5-flash"],
                agent_id="antigravity",
            )

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/docker")
    def test_legacy_key_deprecation_warning(self, mock_which, mock_run):
        """Deprecation warning is printed to stderr when a legacy API key is set but HOLON_AGENT_KEY is not.

        Verifies the else-branch inside run_docker_container() that warns operators
        who haven't migrated from vendor-specific keys (e.g. ANTHROPIC_API_KEY) to
        the unified HOLON_AGENT_KEY variable.
        """
        import io

        mock_run.return_value = MagicMock(returncode=0)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123"}, clear=True), \
             patch("sys.stderr", new_callable=io.StringIO) as mock_err:
            run_docker_container("planner", "holon/agent-claude", [], agent_id="claude")
            warning_output = mock_err.getvalue()
            self.assertIn("ANTHROPIC_API_KEY", warning_output)
            self.assertIn("HOLON_AGENT_KEY", warning_output)
            self.assertIn("MIGRATION.md", warning_output)


if __name__ == "__main__":
    unittest.main()
