"""Validate the Stage 8 synthetic internal-policy source set."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.synthetic_policy_v1 import validate_synthetic_policy_set


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("dataset/synthetic/policies/v1/manifest.json"),
        help="Stage 8 synthetic source manifest",
    )
    args = parser.parse_args()
    errors = validate_synthetic_policy_set(args.manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Synthetic policy validation passed: 3 complete documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
