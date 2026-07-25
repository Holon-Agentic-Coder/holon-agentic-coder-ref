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
        test_args = ["holon", "plan", "intent_branch_name", "--agent", "antigravity-agent", "--model", "gemini-3.5-flash"]
        with patch("sys.argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_container.assert_called_once_with(
                "planner", "holon/agent-antigravity", ["intent_branch_name", "antigravity-agent", "gemini-3.5-flash"], agent_id="antigravity"
            )


if __name__ == "__main__":
    unittest.main()
