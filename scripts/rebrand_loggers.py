#!/usr/bin/env python3
"""
Djinn Logger Rebranding Script
Walks through all Python files in the codebase and updates remaining
'youkai' logging namespaces in `logging.getLogger` to 'djinn'.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def rebrand_files():
    count = 0
    # Walk cogs/ and utils/ and root python files
    for path in list(ROOT.glob("cogs/**/*.py")) + list(ROOT.glob("utils/**/*.py")) + list(ROOT.glob("*.py")):
        if path.is_dir() or path.name == "rebrand_loggers.py":
            continue
            
        content = path.read_text(encoding="utf-8")
        original = content
        
        # Replace both double and single quotes
        content = content.replace('logging.getLogger("youkai.', 'logging.getLogger("djinn.')
        content = content.replace("logging.getLogger('youkai.", "logging.getLogger('djinn.")
        
        if content != original:
            path.write_text(content, encoding="utf-8")
            print(f"✅ Rebranded loggers in {path.relative_to(ROOT)}")
            count += 1
            
    print(f"\n🎉 Successfully rebranded logging namespaces in {count} files!")

if __name__ == "__main__":
    rebrand_files()
