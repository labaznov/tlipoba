"""Run repository checks locally with the selected Windows Python runtime."""

import subprocess
import sys
from pathlib import Path


def main():
    if sys.version_info < (3, 13):
        print("Local tests require Python 3.13 or newer", file=sys.stderr)
        return 1
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=Path(__file__).resolve().parents[1], timeout=300, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Local tests failed: {str(error).rstrip('.')}", file=sys.stderr)
        return 1
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
