#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
from datetime import datetime, UTC

def run_cmd(args, cwd=None, env=None, check=True):
    print(f"Running: {' '.join(args)}")
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"Command failed with code {result.returncode}")
        print(f"Stdout:\n{result.stdout}")
        print(f"Stderr:\n{result.stderr}")
        sys.exit(result.returncode)
    return result

def main():
    raise Exception("FIXME: not implemented yet")

if __name__ == "__main__":
    main()
