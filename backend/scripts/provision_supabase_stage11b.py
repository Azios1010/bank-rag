"""Provision and verify Stage 11B's three private Supabase Storage buckets."""
from __future__ import annotations

from app.services.supabase_storage import ensure_private_buckets


def main() -> None:
    for result in ensure_private_buckets():
        state = "created" if result.created else "already-present"
        print(f"{result.name}: {state}; private={not result.public}")


if __name__ == "__main__":
    main()
