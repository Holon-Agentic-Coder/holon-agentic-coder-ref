#!/usr/bin/env python3
import os
import sys
import json
import shutil
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

def get_file_structure(root_dir, max_depth=3):
    lines = []
    root_dir = os.path.abspath(root_dir)
    prefix_len = len(root_dir) + 1
    
    for root, dirs, files in os.walk(root_dir):
        # Filter out dot directories in-place to prevent os.walk from recursing into them
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        rel_path = root[prefix_len:]
        depth = rel_path.count(os.sep) + 1 if rel_path else 0
        if depth >= max_depth:
            dirs[:] = []
            
        indent = "  " * depth
        if rel_path:
            lines.append(f"{indent}{os.path.basename(root)}/")
        else:
            lines.append("./")
            
        for f in files:
            if not f.startswith('.'):
                lines.append(f"{indent}  {f}")
                
    return "\n".join(lines)

def main():
    raise Exception("FIXME: not implemented yet")

if __name__ == "__main__":
    main()
