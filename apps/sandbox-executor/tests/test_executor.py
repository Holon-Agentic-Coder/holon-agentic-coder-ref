import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sandbox_executor.entrypoint import executor


class TestExecutor(unittest.TestCase):
    def test_redact_args(self):
        from sandbox_executor.entrypoint.executor import redact_args

        args = [
            "git",
            "clone",
            "https://token:secret@github.com/repo.git",
            "https://single_token@github.com/repo.git",
            "https://github.com/repo.git?token=secret123&password=mypass",
            "not-a-url",
            "--token",
            "secret_token_123",
            "--access-token",
            "access_123",
            "-p",
            "my_pass",
            "--secret",
            "top_secret",
            "--api-key",
            "key_abc",
            "--pattern",
            "*.py",
            "--author",
            "alice",
            "--path",
            "/tmp/test",
            "--auth_token",
            "at_123",
            "--client-secret",
            "cs_123",
            "--client_secret",
            "cs_456",
        ]
        redacted = redact_args(args)
        self.assertEqual(redacted[2], "https://*******@github.com/repo.git")
        self.assertEqual(redacted[3], "https://*******@github.com/repo.git")
        self.assertEqual(redacted[4], "https://github.com/repo.git?token=*******&password=*******")
        self.assertEqual(redacted[5], "not-a-url")
        self.assertEqual(redacted[6], "--token")
        self.assertEqual(redacted[7], "*******")
        self.assertEqual(redacted[8], "--access-token")
        self.assertEqual(redacted[9], "*******")
        self.assertEqual(redacted[10], "-p")
        self.assertEqual(redacted[11], "my_pass")
        self.assertEqual(redacted[12], "--secret")
        self.assertEqual(redacted[13], "*******")
        self.assertEqual(redacted[14], "--api-key")
        self.assertEqual(redacted[15], "*******")
        self.assertEqual(redacted[16], "--pattern")
        self.assertEqual(redacted[17], "*.py")
        self.assertEqual(redacted[18], "--author")
        self.assertEqual(redacted[19], "alice")
        self.assertEqual(redacted[20], "--path")
        self.assertEqual(redacted[21], "/tmp/test")
        self.assertEqual(redacted[22], "--auth_token")
        self.assertEqual(redacted[23], "*******")
        self.assertEqual(redacted[24], "--client-secret")
        self.assertEqual(redacted[25], "*******")
        self.assertEqual(redacted[26], "--client_secret")
        self.assertEqual(redacted[27], "*******")

        # When --token is followed by another flag, the positional value
        # after that flag is NOT masked (known limitation — by design).
        chained = redact_args(["--token", "--verbose", "secret"])
        self.assertEqual(chained, ["--token", "--verbose", "secret"])

        # Equal-sign formatted secret flags
        equal_fmt = redact_args(["--token=secret123", "--password=mypass", "--author=alice"])
        self.assertEqual(equal_fmt, ["--token=*******", "--password=*******", "--author=alice"])

        # Trailing secret flags at the end of args
        trailing = redact_args(["git", "clone", "--token"])
        self.assertEqual(trailing, ["git", "clone", "--token"])

        # Secret values starting with - or --
        secret_dash = redact_args(["--token", "-secret-value"])
        self.assertEqual(secret_dash, ["--token", "*******"])

        # Single-character non-flag value after a secret flag should be masked
        single_char = redact_args(["cmd", "--password", "s"])
        self.assertEqual(single_char, ["cmd", "--password", "*******"])

    def test_redact_args_trailing_secret_flag(self):
        from sandbox_executor.entrypoint.executor import redact_args

        args = ["git", "clone", "--token"]
        redacted = redact_args(args)
        self.assertEqual(redacted, ["git", "clone", "--token"])

    def test_redact_text(self):
        from sandbox_executor.entrypoint.executor import redact_text

        text = "This is a log with a secret URL: https://token:secret@github.com/repo.git and token=secret123 parameter"
        redacted = redact_text(text)
        self.assertEqual(
            redacted, "This is a log with a secret URL: https://*******@github.com/repo.git and token=******* parameter"
        )

        extended_text = (
            "api_key=secret_123 auth=abc bearer=def pat=ghi key=jkl Bearer my_jwt_token Authorization: Bearer token_xyz"
        )
        redacted_ext = redact_text(extended_text)
        expected_ext = (
            "api_key=******* auth=******* bearer=******* pat=******* "
            # Note: bare `key=` is intentionally NOT redacted to avoid over-masking non-secret
            # patterns like cache_key, sort_key, foreign_key etc. Only compound forms are matched.
            "key=jkl Bearer ******* Authorization: Bearer *******"
        )
        self.assertEqual(redacted_ext, expected_ext)

        # Quoted secrets and JSON key redaction tests
        quoted_text = 'token="secret" github_token=\'secret_abc\' {"api_key": "secret"} "auth_key": \'secret\''
        redacted_quoted = redact_text(quoted_text)
        expected_quoted = 'token="*******" github_token=\'*******\' {"api_key": "*******"} "auth_key": \'*******\''
        self.assertEqual(redacted_quoted, expected_quoted)

        # Quoted secret values with spaces
        quoted_spaces = (
            'token="secret with spaces" api_key=\'my secret key\' {"auth_token": "bearer token with spaces"}'
        )
        redacted_spaces = redact_text(quoted_spaces)
        expected_spaces = 'token="*******" api_key=\'*******\' {"auth_token": "*******"}'
        self.assertEqual(redacted_spaces, expected_spaces)

        benign_text = (
            "--pattern=*.py --author=alice --path=/tmp/test git log -p "
            "monkey=banana donkey=kong compat=1.0.0 compact=true impact=high"
        )
        self.assertEqual(redact_text(benign_text), benign_text)

        self.assertEqual(redact_text(None), None)
        self.assertEqual(redact_text(""), "")

    def test_redact_text_oversized_input(self):
        from sandbox_executor.entrypoint.executor import _MAX_REDACT_INPUT_LEN, redact_text

        # Input exceeding the limit should be returned unredacted (intentional ReDoS prevention).
        # Such large inputs are assumed to come from trusted internal subprocess outputs.
        big_text = "token=secret " + "x" * _MAX_REDACT_INPUT_LEN
        result = redact_text(big_text)
        self.assertEqual(result, big_text)

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
        mock_result.stdout = ""

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
        mock_result.stdout = ""
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
        mock_result.stdout = ""
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
            mock_rmtree.assert_any_call(default_dir, onexc=executor._handle_remove_readonly)

            mock_run_cmd_args = [call.args[0] for call in mock_run_cmd.call_args_list if call.args]
            self.assertTrue(any("add" in cmd and "-A" in cmd for cmd in mock_run_cmd_args))
            self.assertTrue(any("status" in cmd for cmd in mock_run_cmd_args))

    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    def test_main_raises_exception_on_failure(self, mock_get_repo_url, mock_get_runner, mock_run_cmd):
        mock_get_repo_url.return_value = "/mock/repo"
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        mock_run_cmd.side_effect = subprocess.CalledProcessError(1, ["git", "clone"])

        with (
            tempfile.TemporaryDirectory() as tmp_dir,
            patch.dict(os.environ, {"HOLON_REPO_DIR": tmp_dir}),
            patch("sys.argv", ["executor.py", "I-456/P-123/_"]),
            patch("sys.stderr", new_callable=io.StringIO) as mock_stderr,
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                executor.main()
            self.assertIn("Execution failed:", mock_stderr.getvalue())

    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    @patch("sandbox_executor.entrypoint.executor.shutil.rmtree")
    @patch("sandbox_executor.entrypoint.executor.os.path.lexists", return_value=True)
    @patch("sandbox_executor.entrypoint.executor.os.path.ismount", return_value=False)
    @patch("sandbox_executor.entrypoint.executor.os.path.islink", return_value=False)
    def test_main_raises_runtime_error_on_cleanup_failure(
        self, mock_islink, mock_ismount, mock_lexists, mock_rmtree, mock_get_repo_url, mock_get_runner, mock_run_cmd
    ):
        mock_rmtree.side_effect = PermissionError("Permission denied")
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.argv", ["executor.py", "I-456/P-123/_"]),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                executor.main()
            self.assertIn("Failed to clean up existing repo dir", str(ctx.exception))

    def test_clear_dir_contents(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sub_dir = os.path.join(tmp_dir, "subdir")
            file_path = os.path.join(tmp_dir, "test.txt")
            os.makedirs(sub_dir, exist_ok=True)
            with open(file_path, "w") as f:
                f.write("hello")

            executor._clear_dir_contents(tmp_dir)
            self.assertTrue(os.path.exists(tmp_dir))
            self.assertEqual(os.listdir(tmp_dir), [])

            # Test guard clause when path is a file, not a directory
            with open(file_path, "w") as f:
                f.write("hello")
            executor._clear_dir_contents(file_path)
            self.assertTrue(os.path.exists(file_path))

    def test_clear_dir_contents_raise_on_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sub_file = os.path.join(tmp_dir, "test.txt")
            with open(sub_file, "w") as f:
                f.write("test")
            with patch("os.unlink", side_effect=PermissionError("Permission denied")):
                # Default raise_on_error=False swallows error
                executor._clear_dir_contents(tmp_dir, raise_on_error=False)
                # raise_on_error=True propagates error
                with self.assertRaises(PermissionError):
                    executor._clear_dir_contents(tmp_dir, raise_on_error=True)

    def test_cleanup_repo_dir_readonly(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = os.path.join(tmp_dir, "readonly_repo")
            os.makedirs(repo_dir, exist_ok=True)
            readonly_file = os.path.join(repo_dir, "readonly.txt")
            with open(readonly_file, "w") as f:
                f.write("content")
            os.chmod(readonly_file, 0o444)
            executor._cleanup_repo_dir(repo_dir, raise_on_error=True)
            self.assertFalse(os.path.exists(repo_dir))

    @patch("sandbox_executor.entrypoint.executor._cleanup_repo_dir")
    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    @patch("sandbox_executor.entrypoint.executor.os.path.expanduser")
    def test_main_keep_workspace(self, mock_expanduser, mock_get_repo_url, mock_get_runner, mock_run_cmd, mock_cleanup):
        mock_get_repo_url.return_value = "/mock/repo"
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run_cmd.return_value = mock_result

        with tempfile.TemporaryDirectory() as tmp_dir:
            default_dir = os.path.join(tmp_dir, "repo")
            mock_expanduser.return_value = default_dir
            os.makedirs(default_dir, exist_ok=True)

            env = os.environ.copy()
            if "HOLON_REPO_DIR" in env:
                del env["HOLON_REPO_DIR"]
            env["HOLON_SKIP_PUSH"] = "1"
            env["HOLON_KEEP_WORKSPACE"] = "true"

            with (
                patch.dict(os.environ, env, clear=True),
                patch("sys.argv", ["executor.py", "I-456/P-123/_"]),
            ):
                executor.main()

            mock_cleanup.assert_not_called()

    @patch("sandbox_executor.entrypoint.executor.run_cmd")
    @patch("sandbox_executor.entrypoint.executor.get_runner")
    @patch("sandbox_executor.entrypoint.executor.get_repo_url")
    @patch("sandbox_executor.entrypoint.executor.os.path.expanduser")
    @patch("sandbox_executor.entrypoint.executor._clear_dir_contents")
    @patch("sandbox_executor.entrypoint.executor.os.path.ismount", return_value=True)
    def test_main_mount_point_clears_contents(
        self, mock_ismount, mock_clear_dir_contents, mock_expanduser, mock_get_repo_url, mock_get_runner, mock_run_cmd
    ):
        mock_get_repo_url.return_value = "/mock/repo"
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
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

            self.assertTrue(mock_clear_dir_contents.called)
            mock_clear_dir_contents.assert_any_call(default_dir, raise_on_error=True)


if __name__ == "__main__":
    unittest.main()
