"""create the survey database schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial survey database schema."""
    op.create_table(
        "authors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("session_expires_at", sa.String(length=27), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_authors"),
        sa.UniqueConstraint("session_token_hash", name="uq_authors_session_token_hash"),
    )

    op.create_table(
        "forms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.Column("updated_at", sa.String(length=27), nullable=False),
        sa.Column("published_at", sa.String(length=27), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published')",
            name="ck_forms_status",
        ),
        sa.CheckConstraint(
            "revision >= 1 AND typeof(revision) = 'integer'",
            name="ck_forms_revision",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND slug IS NULL AND published_at IS NULL) "
            "OR (status = 'published' AND slug IS NOT NULL AND published_at IS NOT NULL)",
            name="ck_forms_publication_state",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["authors.id"],
            name="fk_forms_owner_id_authors",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_forms"),
        sa.UniqueConstraint("slug", name="uq_forms_slug"),
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("required", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("rating_min", sa.Integer(), nullable=True),
        sa.Column("rating_max", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "type IN ('text', 'single_choice', 'multiple_choice', 'rating')",
            name="ck_questions_type",
        ),
        sa.CheckConstraint(
            "typeof(required) = 'integer' AND required IN (0, 1)",
            name="ck_questions_required",
        ),
        sa.CheckConstraint(
            "typeof(position) = 'integer' AND position >= 0",
            name="ck_questions_position",
        ),
        sa.CheckConstraint(
            "(type = 'rating' AND typeof(rating_min) = 'integer' "
            "AND typeof(rating_max) = 'integer' AND rating_min <= rating_max) "
            "OR (type <> 'rating' AND rating_min IS NULL AND rating_max IS NULL)",
            name="ck_questions_rating_bounds",
        ),
        sa.ForeignKeyConstraint(
            ["form_id"],
            ["forms.id"],
            name="fk_questions_form_id_forms",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
        sa.UniqueConstraint("form_id", "position", name="uq_questions_form_position"),
        sa.UniqueConstraint("id", "form_id", name="uq_questions_id_form"),
    )

    op.create_table(
        "question_options",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "typeof(position) = 'integer' AND position >= 0",
            name="ck_question_options_position",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="fk_question_options_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_question_options"),
        sa.UniqueConstraint(
            "question_id",
            "position",
            name="uq_question_options_question_position",
        ),
        sa.UniqueConstraint(
            "id", "question_id", name="uq_question_options_id_question"
        ),
    )

    op.create_table(
        "submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("submitted_at", sa.String(length=27), nullable=False),
        sa.ForeignKeyConstraint(
            ["form_id"],
            ["forms.id"],
            name="fk_submissions_form_id_forms",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submissions"),
        sa.UniqueConstraint("id", "form_id", name="uq_submissions_id_form"),
    )

    op.create_table(
        "answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("rating_value", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "NOT (text_value IS NOT NULL AND rating_value IS NOT NULL)",
            name="ck_answers_single_value",
        ),
        sa.CheckConstraint(
            "rating_value IS NULL OR typeof(rating_value) = 'integer'",
            name="ck_answers_rating_integer",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id", "form_id"],
            ["submissions.id", "submissions.form_id"],
            name="fk_answers_submission_form",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_id", "form_id"],
            ["questions.id", "questions.form_id"],
            name="fk_answers_question_form",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_answers"),
        sa.UniqueConstraint(
            "submission_id", "question_id", name="uq_answers_submission_question"
        ),
        sa.UniqueConstraint("id", "question_id", name="uq_answers_id_question"),
    )

    op.create_table(
        "answer_options",
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("option_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["answer_id", "question_id"],
            ["answers.id", "answers.question_id"],
            name="fk_answer_options_answer_question",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["option_id", "question_id"],
            ["question_options.id", "question_options.question_id"],
            name="fk_answer_options_option_question",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("answer_id", "option_id", name="pk_answer_options"),
    )

    op.create_table(
        "submission_idempotency",
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=27), nullable=False),
        sa.ForeignKeyConstraint(
            ["form_id"],
            ["forms.id"],
            name="fk_submission_idempotency_form_id_forms",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id", "form_id"],
            ["submissions.id", "submissions.form_id"],
            name="fk_submission_idempotency_submission_form",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "form_id", "idempotency_key", name="pk_submission_idempotency"
        ),
        sa.UniqueConstraint(
            "submission_id",
            "form_id",
            name="uq_submission_idempotency_submission_form",
        ),
    )

    op.create_index(
        "ix_forms_owner_updated_at_id",
        "forms",
        ["owner_id", sa.text("updated_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_submissions_form_submitted_at_id",
        "submissions",
        ["form_id", sa.text("submitted_at DESC"), sa.text("id DESC")],
    )
    op.create_index("ix_answers_question_id", "answers", ["question_id"])
    op.create_index("ix_answer_options_option_id", "answer_options", ["option_id"])
    op.create_index(
        "ix_submission_idempotency_created_at",
        "submission_idempotency",
        ["created_at"],
    )


def downgrade() -> None:
    """Remove the survey database schema."""
    op.drop_index(
        "ix_submission_idempotency_created_at", table_name="submission_idempotency"
    )
    op.drop_index("ix_answer_options_option_id", table_name="answer_options")
    op.drop_index("ix_answers_question_id", table_name="answers")
    op.drop_index("ix_submissions_form_submitted_at_id", table_name="submissions")
    op.drop_index("ix_forms_owner_updated_at_id", table_name="forms")

    op.drop_table("submission_idempotency")
    op.drop_table("answer_options")
    op.drop_table("answers")
    op.drop_table("submissions")
    op.drop_table("question_options")
    op.drop_table("questions")
    op.drop_table("forms")
    op.drop_table("authors")
