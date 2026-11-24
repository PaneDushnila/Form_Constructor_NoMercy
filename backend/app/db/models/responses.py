from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, new_uuid, utc_now

if TYPE_CHECKING:
    from .forms import Form


class Submission(Base):
    """One completed response submitted for a form."""

    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("id", "form_id", name="uq_submissions_id_form"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    form_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    submitted_at: Mapped[str] = mapped_column(
        String(27), nullable=False, default=utc_now
    )

    form: Mapped[Form] = relationship(back_populates="submissions")


class Answer(Base):
    """Value supplied for one question in a submission."""

    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint(
            "NOT (text_value IS NOT NULL AND rating_value IS NOT NULL)",
            name="ck_answers_single_value",
        ),
        CheckConstraint(
            "rating_value IS NULL OR typeof(rating_value) = 'integer'",
            name="ck_answers_rating_integer",
        ),
        ForeignKeyConstraint(
            ["submission_id", "form_id"],
            ["submissions.id", "submissions.form_id"],
            name="fk_answers_submission_form",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["question_id", "form_id"],
            ["questions.id", "questions.form_id"],
            name="fk_answers_question_form",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "submission_id", "question_id", name="uq_answers_submission_question"
        ),
        UniqueConstraint("id", "question_id", name="uq_answers_id_question"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    submission_id: Mapped[str] = mapped_column(String(36), nullable=False)
    form_id: Mapped[str] = mapped_column(String(36), nullable=False)
    question_id: Mapped[str] = mapped_column(String(36), nullable=False)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating_value: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AnswerOption(Base):
    """Option selected by a choice answer."""

    __tablename__ = "answer_options"
    __table_args__ = (
        ForeignKeyConstraint(
            ["answer_id", "question_id"],
            ["answers.id", "answers.question_id"],
            name="fk_answer_options_answer_question",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["option_id", "question_id"],
            ["question_options.id", "question_options.question_id"],
            name="fk_answer_options_option_question",
            ondelete="RESTRICT",
        ),
    )

    answer_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(36), nullable=False)
    option_id: Mapped[str] = mapped_column(String(36), primary_key=True)


class SubmissionIdempotency(Base):
    """Request key used to prevent duplicate submissions."""

    __tablename__ = "submission_idempotency"
    __table_args__ = (
        ForeignKeyConstraint(
            ["form_id"],
            ["forms.id"],
            name="fk_submission_idempotency_form_id_forms",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["submission_id", "form_id"],
            ["submissions.id", "submissions.form_id"],
            name="fk_submission_idempotency_submission_form",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "submission_id",
            "form_id",
            name="uq_submission_idempotency_submission_form",
        ),
    )

    form_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    submission_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(27), nullable=False, default=utc_now)


# Keep result queries efficient by question and selected option.
Index(
    "ix_submissions_form_submitted_at_id",
    Submission.form_id,
    Submission.submitted_at.desc(),
    Submission.id.desc(),
)
Index("ix_answers_question_id", Answer.question_id)
Index("ix_answer_options_option_id", AnswerOption.option_id)
Index("ix_submission_idempotency_created_at", SubmissionIdempotency.created_at)
