import pytest
from app.db import Form, Question, QuestionOption, new_uuid, utc_now
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


# Each change independently violates a rule on an otherwise valid draft.
@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"status": "archived"}, id="unknown-status"),
        pytest.param({"revision": 0}, id="zero-revision"),
        pytest.param({"revision": 1.5}, id="fractional-revision"),
        pytest.param({"slug": "public"}, id="draft-with-slug"),
        pytest.param({"published_at": utc_now()}, id="draft-with-publication-date"),
        pytest.param(
            {"status": "published", "slug": "public"}, id="published-without-date"
        ),
        pytest.param(
            {"status": "published", "published_at": utc_now()},
            id="published-without-slug",
        ),
    ],
)
def test_form_rejects_invalid_state(
    db: Session, forms: tuple[Form, Form], changes: dict
) -> None:
    draft, _ = forms
    with pytest.raises(IntegrityError, match="CHECK constraint failed"):
        db.execute(update(Form).where(Form.id == draft.id).values(**changes))


# A published slug is unique across forms, not just within one author's draft.
def test_duplicate_public_slug_is_rejected(
    db: Session, forms: tuple[Form, Form]
) -> None:
    draft, published = forms
    with pytest.raises(IntegrityError, match=r"UNIQUE constraint failed: forms\.slug"):
        db.execute(
            update(Form)
            .where(Form.id == draft.id)
            .values(
                status="published",
                slug=published.slug,
                published_at=published.published_at,
            )
        )


# The owner's ID must reference a stored author.
def test_form_rejects_missing_owner(db: Session, forms: tuple[Form, Form]) -> None:
    draft, _ = forms
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.execute(update(Form).where(Form.id == draft.id).values(owner_id=new_uuid()))


# SQLite's integer affinity alone would still allow fractional values.
@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"type": "unknown"}, id="unknown-type"),
        pytest.param({"required": 2}, id="invalid-required"),
        pytest.param({"position": -1}, id="negative-position"),
        pytest.param({"position": 0.5}, id="fractional-position"),
        pytest.param({"type": "rating", "rating_max": 5}, id="missing-rating-min"),
        pytest.param({"type": "rating", "rating_min": 1}, id="missing-rating-max"),
        pytest.param(
            {"type": "rating", "rating_min": 5, "rating_max": 1}, id="reversed-bounds"
        ),
        pytest.param(
            {"type": "rating", "rating_min": 1.5, "rating_max": 5},
            id="fractional-bound",
        ),
        pytest.param({"rating_min": 1, "rating_max": 5}, id="bounds-on-text"),
    ],
)
def test_question_rejects_invalid_fields(
    db: Session, forms: tuple[Form, Form], changes: dict
) -> None:
    draft, _ = forms
    values = {"type": "text", "position": 0, **changes}
    db.add(Question(form_id=draft.id, title="Question", **values))
    with pytest.raises(IntegrityError, match="CHECK constraint failed"):
        db.flush()


# The same position may occur on different forms but not twice on one form.
def test_question_position_is_unique_per_form(
    db: Session, forms: tuple[Form, Form]
) -> None:
    draft, _ = forms
    for form in forms:
        db.add(Question(form=form, type="text", title="First", position=0))
    db.flush()

    db.add(Question(form=draft, type="text", title="Duplicate", position=0))
    with pytest.raises(
        IntegrityError, match="UNIQUE constraint failed: questions.form_id"
    ):
        db.flush()


# Attach an unused option to a draft so cascade can be tested without responses.
@pytest.fixture
def draft_option(db: Session, forms: tuple[Form, Form]) -> QuestionOption:
    draft, _ = forms
    question = Question(form=draft, type="single_choice", title="Choice", position=0)
    option = QuestionOption(question=question, label="Yes", position=0)
    db.add(question)
    db.flush()
    return option


# Option ordering requires nonnegative integers, without duplicates within a question.
@pytest.mark.parametrize(
    ("position", "reason"),
    [
        pytest.param(0, "UNIQUE constraint failed", id="duplicate-position"),
        pytest.param(-1, "CHECK constraint failed", id="negative-position"),
        pytest.param(0.5, "CHECK constraint failed", id="fractional-position"),
    ],
)
def test_option_rejects_invalid_position(
    db: Session, draft_option: QuestionOption, position: float, reason: str
) -> None:
    db.add(
        QuestionOption(
            question_id=draft_option.question_id, label="No", position=position
        )
    )
    with pytest.raises(IntegrityError, match=reason):
        db.flush()


# Bypass ORM cascades to check the database's ON DELETE CASCADE itself.
def test_deleting_draft_question_cascades_to_options(
    db: Session, draft_option: QuestionOption
) -> None:
    db.execute(delete(Question).where(Question.id == draft_option.question_id))
    assert (
        db.scalar(select(QuestionOption.id).where(QuestionOption.id == draft_option.id))
        is None
    )
