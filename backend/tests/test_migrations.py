from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine


# Check both the declared schema and the physical sort order in SQLite.
def test_upgrade_creates_schema(db_engine: Engine, migration_config: Config) -> None:
    schema = inspect(db_engine)
    assert set(schema.get_table_names()) == {
        "alembic_version",
        "authors",
        "forms",
        "questions",
        "question_options",
        "submissions",
        "answers",
        "answer_options",
        "submission_idempotency",
    }
    assert schema.get_pk_constraint("answer_options")["constrained_columns"] == [
        "answer_id",
        "option_id",
    ]
    command.check(migration_config)

    indexes = {
        "ix_forms_owner_updated_at_id": [("owner_id", 0), ("updated_at", 1), ("id", 1)],
        "ix_submissions_form_submitted_at_id": [
            ("form_id", 0),
            ("submitted_at", 1),
            ("id", 1),
        ],
        "ix_answers_question_id": [("question_id", 0)],
        "ix_answer_options_option_id": [("option_id", 0)],
        "ix_submission_idempotency_created_at": [("created_at", 0)],
    }
    with db_engine.connect() as connection:
        for name, expected in indexes.items():
            rows = connection.exec_driver_sql(f"PRAGMA index_xinfo('{name}')")
            assert [(row[2], row[3]) for row in rows if row[5]] == expected


# A rolled-back database must remain usable by Alembic on the next upgrade.
def test_downgrade_and_reupgrade(db_engine: Engine, migration_config: Config) -> None:
    tables_before = inspect(db_engine).get_table_names()

    command.downgrade(migration_config, "base")
    assert inspect(db_engine).get_table_names() == ["alembic_version"]
    with db_engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).first()
            is None
        )

    command.upgrade(migration_config, "head")
    assert inspect(db_engine).get_table_names() == tables_before
