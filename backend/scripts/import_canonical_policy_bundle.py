import argparse
from pathlib import Path

from app.config import get_settings
from app.services.canonical_policy_import import CanonicalPolicyImportService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def main():
    parser = argparse.ArgumentParser(description="Import canonical policy bundle")
    parser.add_argument("bundle_dir", type=str, help="Path to the canonical bundle directory")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionLocal() as db:
        service = CanonicalPolicyImportService(db)
        service.stage(Path(args.bundle_dir))
        db.commit()
        print("Canonical import successful")

if __name__ == "__main__":
    main()
