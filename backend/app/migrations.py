"""Additive schema migration for existing SQLite installations."""
from sqlalchemy.orm import Session

from .db import Base, engine
from . import v2_models  # noqa: F401 - register the v2 tables with metadata
from .v2_models import SchemaMigration

SCHEMA_VERSION = 3


def migrate(target_engine=engine):
    # All schema additions are tables; existing records and access settings are retained.
    Base.metadata.create_all(target_engine)
    with Session(target_engine) as db:
        if not db.get(SchemaMigration, SCHEMA_VERSION):
            db.add(SchemaMigration(version=SCHEMA_VERSION))
            db.commit()


if __name__ == "__main__":
    migrate()
    print(f"NMR schema version {SCHEMA_VERSION} ready")
