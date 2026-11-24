from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.db import Author, Form, create_db_engine, utc_now
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session


# Each test gets its own file so WAL and multiple connections behave normally.
@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return str(URL.create("sqlite", database=str(tmp_path / "test.db")))


# Force the temporary URL even if the developer has DATABASE_URL set locally.
@pytest.fixture
def migration_config(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
    )
    return config


# Use the actual migration, rather than creating the schema from ORM metadata.
@pytest.fixture
def db_engine(migration_config: Config, database_url: str) -> Iterator[Engine]:
    command.upgrade(migration_config, "head")
    engine = create_db_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


# Uncommitted fixture data is rolled back when the test session closes.
@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session


# The two forms let tests distinguish a missing parent from a mismatched parent.
@pytest.fixture
def forms(db: Session) -> tuple[Form, Form]:
    author = Author(session_token_hash="a" * 64, session_expires_at=utc_now())
    draft = Form(owner=author, title="Draft", description="")
    published = Form(
        owner=author,
        title="Published",
        description="",
        status="published",
        slug="published-form",
        published_at=utc_now(),
    )
    db.add_all([draft, published])
    db.flush()
    return draft, published
