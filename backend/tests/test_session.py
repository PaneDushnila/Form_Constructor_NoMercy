from contextlib import closing
from datetime import datetime
from uuid import UUID

import app.db.session as db_session
import pytest
from app.db import Author, Form, Question, QuestionOption, utc_now
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


# Foreign keys and busy_timeout must apply to each connection, not just the first.
def test_sqlite_settings_on_each_connection(db_engine: Engine) -> None:
    with db_engine.connect() as first, db_engine.connect() as second:
        assert (
            first.connection.dbapi_connection is not second.connection.dbapi_connection
        )
        for connection in (first, second):
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert (
                connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
            )
            assert (
                connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 5_000
            )


# Read the committed rows in a fresh session, not from the original ORM objects.
def test_orm_persists_form_and_defaults(db_engine: Engine) -> None:
    with Session(db_engine) as session, session.begin():
        author = Author(session_token_hash="a" * 64, session_expires_at=utc_now())
        form = Form(owner=author, title="Survey", description="")
        question = Question(form=form, type="single_choice", title="Choose", position=0)
        question.options.append(QuestionOption(label="Yes", position=0))
        session.add(form)
        session.flush()
        form_id = form.id

    with Session(db_engine) as session:
        form = session.get(Form, form_id)
        assert form is not None
        assert UUID(form.id).version == 4
        assert (form.status, form.revision, form.slug, form.published_at) == (
            "draft",
            1,
            None,
            None,
        )
        assert datetime.strptime(form.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
        assert len(form.created_at) == 27
        assert form.owner.session_token_hash == "a" * 64
        (question,) = form.questions
        assert question.required == 0
        (option,) = question.options
        assert (option.label, option.position) == ("Yes", 0)


# Closing the session provider must release its session without committing work.
def test_get_session_does_not_commit(
    db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(bind=db_engine))
    with closing(db_session.get_session()) as provider:
        session = next(provider)
        author = Author(session_token_hash="a" * 64, session_expires_at=utc_now())
        session.add(author)
        session.flush()
        assert inspect(author).persistent

    assert inspect(author).detached
    with Session(db_engine) as session:
        assert session.scalar(select(Author.id)) is None


# An integrity error in a later write must not leave previously flushed rows behind.
def test_transaction_rolls_back_after_integrity_error(db_engine: Engine) -> None:
    now = utc_now()
    with (
        pytest.raises(
            IntegrityError, match="UNIQUE constraint failed: authors.session_token_hash"
        ),
        Session(db_engine) as session,
        session.begin(),
    ):
        session.add(Author(session_token_hash="a" * 64, session_expires_at=now))
        session.flush()
        session.add(Author(session_token_hash="a" * 64, session_expires_at=now))

    with Session(db_engine) as session:
        assert session.scalar(select(Author.id)) is None
