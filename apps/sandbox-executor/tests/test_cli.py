import os
import unittest
from unittest.mock import patch

from sandbox_executor.cli import find_github_token, get_agent_session_mounts, get_ssh_auth_mounts


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


if __name__ == "__main__":
    unittest.main()
