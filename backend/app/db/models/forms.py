from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, new_uuid, utc_now

if TYPE_CHECKING:
    from .authors import Author
    from .responses import Submission


class Form(Base):
    """Survey form with draft and published states."""

    __tablename__ = "forms"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published')",
            name="ck_forms_status",
        ),
        CheckConstraint(
            "revision >= 1 AND typeof(revision) = 'integer'",
            name="ck_forms_revision",
        ),
        CheckConstraint(
            "(status = 'draft' AND slug IS NULL AND published_at IS NULL) "
            "OR (status = 'published' AND slug IS NOT NULL AND published_at IS NOT NULL)",
            name="ck_forms_publication_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("authors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False, default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    slug: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_at: Mapped[str] = mapped_column(String(27), nullable=False, default=utc_now)
    updated_at: Mapped[str] = mapped_column(
        String(27), nullable=False, default=utc_now, onupdate=utc_now
    )
    published_at: Mapped[str | None] = mapped_column(String(27), nullable=True)

    owner: Mapped[Author] = relationship(back_populates="forms")
    questions: Mapped[list[Question]] = relationship(back_populates="form")
    submissions: Mapped[list[Submission]] = relationship(back_populates="form")


class Question(Base):
    """Question belonging to a form and positioned within it."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('text', 'single_choice', 'multiple_choice', 'rating')",
            name="ck_questions_type",
        ),
        CheckConstraint(
            "typeof(required) = 'integer' AND required IN (0, 1)",
            name="ck_questions_required",
        ),
        CheckConstraint(
            "typeof(position) = 'integer' AND position >= 0",
            name="ck_questions_position",
        ),
        CheckConstraint(
            "(type = 'rating' AND typeof(rating_min) = 'integer' "
            "AND typeof(rating_max) = 'integer' AND rating_min <= rating_max) "
            "OR (type <> 'rating' AND rating_min IS NULL AND rating_max IS NULL)",
            name="ck_questions_rating_bounds",
        ),
        UniqueConstraint("form_id", "position", name="uq_questions_form_position"),
        UniqueConstraint("id", "form_id", name="uq_questions_id_form"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    form_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    form: Mapped[Form] = relationship(back_populates="questions")
    options: Mapped[list[QuestionOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )


class QuestionOption(Base):
    """Selectable option belonging to one choice question."""

    __tablename__ = "question_options"
    __table_args__ = (
        CheckConstraint(
            "typeof(position) = 'integer' AND position >= 0",
            name="ck_question_options_position",
        ),
        UniqueConstraint(
            "question_id",
            "position",
            name="uq_question_options_question_position",
        ),
        UniqueConstraint("id", "question_id", name="uq_question_options_id_question"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    question_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[Question] = relationship(back_populates="options")


# Keep the editor list query aligned with the API sort order.
Index(
    "ix_forms_owner_updated_at_id",
    Form.owner_id,
    Form.updated_at.desc(),
    Form.id.desc(),
)
