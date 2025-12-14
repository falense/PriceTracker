"""CLI entry point for PriceFetcher."""

import sys
from pathlib import Path

# Redirect to run_fetch.py script
scripts_dir = Path(__file__).parent.parent / "scripts"
run_fetch = scripts_dir / "run_fetch.py"

print(f"Use: uv run {run_fetch} [options]")
print("Or: python -m src [options] (if installed)")
sys.exit(1)
