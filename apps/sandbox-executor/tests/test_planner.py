import os
import sys
import json
import tempfile
import pathlib
import unittest
from unittest.mock import patch, MagicMock

from sandbox_executor.entrypoints import planner

class TestPlanner(unittest.TestCase):
    def test_get_file_structure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            # Create some mock files and directories
            (tmp_path / "dir1").mkdir()
            (tmp_path / "dir1" / "file1.py").write_text("print('hello')")
            (tmp_path / "dir2").mkdir()
            (tmp_path / ".git").mkdir() # should be ignored
            (tmp_path / "dir1" / ".hidden").write_text("hidden") # should be ignored
            
            structure = planner.get_file_structure(str(tmp_path))
            self.assertIn("dir1/", structure)
            self.assertIn("file1.py", structure)
            self.assertNotIn(".git", structure)
            self.assertNotIn(".hidden", structure)

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('shutil.rmtree')
    def test_planner_main(self, mock_rmtree, mock_makedirs, mock_exists, mock_run):
        test_args = ["planner.py", "I-12345/_", "test-agent", "gemini"]
        
        # Directly modify and restore sys.argv
        old_argv = sys.argv
        sys.argv = test_args
        try:
            with self.assertRaisesRegex(Exception, "FIXME: not implemented yet"):
                planner.main()
        finally:
            sys.argv = old_argv

if __name__ == "__main__":
    unittest.main()
