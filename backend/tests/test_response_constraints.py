import pytest
from app.db import (
    Answer,
    AnswerOption,
    Form,
    Question,
    QuestionOption,
    Submission,
    SubmissionIdempotency,
    new_uuid,
)
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


# Both options exist; only one belongs to the question answered in the submission.
@pytest.fixture
def response(
    db: Session, forms: tuple[Form, Form]
) -> tuple[Submission, QuestionOption, QuestionOption]:
    draft, published = forms
    options = []
    for form in (published, draft):
        question = Question(
            form=form, type="multiple_choice", title="Choose", position=0
        )
        option = QuestionOption(question=question, label="Yes", position=0)
        db.add(question)
        options.append(option)
    submission = Submission(form=published)
    db.add(submission)
    db.flush()
    return submission, options[0], options[1]


# Seed a stored choice answer so tests can exercise the two FKs on answer_options.
@pytest.fixture
def answer(
    db: Session, response: tuple[Submission, QuestionOption, QuestionOption]
) -> Answer:
    submission, option, _ = response
    answer = Answer(
        submission_id=submission.id,
        form_id=submission.form_id,
        question_id=option.question_id,
    )
    db.add(answer)
    db.flush()
    return answer


# Isolate each composite FK: the other parent belongs to the declared form.
@pytest.mark.parametrize(
    "match_submission_form", [True, False], ids=["question-fk", "submission-fk"]
)
def test_answer_rejects_cross_form_reference(
    db: Session,
    forms: tuple[Form, Form],
    response: tuple[Submission, QuestionOption, QuestionOption],
    match_submission_form: bool,
) -> None:
    submission, _, other_option = response
    draft, published = forms
    db.add(
        Answer(
            submission_id=submission.id,
            form_id=published.id if match_submission_form else draft.id,
            question_id=other_option.question_id,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()


# A rating must be an integer and cannot coexist with a text value.
@pytest.mark.parametrize(
    ("text", "rating"),
    [("text", 3), (None, 1.5)],
    ids=["two-values", "fractional-rating"],
)
def test_answer_rejects_invalid_values(
    db: Session,
    response: tuple[Submission, QuestionOption, QuestionOption],
    text: str | None,
    rating: float,
) -> None:
    submission, option, _ = response
    db.add(
        Answer(
            submission_id=submission.id,
            form_id=submission.form_id,
            question_id=option.question_id,
            text_value=text,
            rating_value=rating,
        )
    )
    with pytest.raises(IntegrityError, match="CHECK constraint failed"):
        db.flush()


# Different answer IDs cannot bypass uniqueness for a submission and question.
def test_one_answer_per_submission_and_question(db: Session, answer: Answer) -> None:
    db.add(
        Answer(
            submission_id=answer.submission_id,
            form_id=answer.form_id,
            question_id=answer.question_id,
        )
    )
    with pytest.raises(
        IntegrityError, match="UNIQUE constraint failed: answers.submission_id"
    ):
        db.flush()


# Use a real option from another question to test both halves of the relation.
@pytest.mark.parametrize(
    "match_answer_question", [True, False], ids=["option-fk", "answer-fk"]
)
def test_answer_option_rejects_cross_question_reference(
    db: Session,
    response: tuple[Submission, QuestionOption, QuestionOption],
    answer: Answer,
    match_answer_question: bool,
) -> None:
    _, _, other_option = response
    db.add(
        AnswerOption(
            answer_id=answer.id,
            question_id=answer.question_id
            if match_answer_question
            else other_option.question_id,
            option_id=other_option.id,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()


# A saved selection protects its option even when deletion bypasses ORM logic.
def test_selected_option_cannot_be_deleted(
    db: Session,
    response: tuple[Submission, QuestionOption, QuestionOption],
    answer: Answer,
) -> None:
    _, option, _ = response
    db.add(
        AnswerOption(
            answer_id=answer.id, question_id=answer.question_id, option_id=option.id
        )
    )
    db.flush()
    selection = select(AnswerOption.option_id).where(
        AnswerOption.answer_id == answer.id
    )
    assert db.scalar(selection) == option.id

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.execute(delete(QuestionOption).where(QuestionOption.id == option.id))


# Reopening the session verifies what was persisted for a real submission.
def test_persists_submission_with_answers(
    db: Session,
    response: tuple[Submission, QuestionOption, QuestionOption],
    answer: Answer,
) -> None:
    submission, option, _ = response
    form_id, submission_id = submission.form_id, submission.id
    db.add(
        AnswerOption(
            answer_id=answer.id, question_id=answer.question_id, option_id=option.id
        )
    )
    for question_type, position, fields, value in (
        ("text", 1, {}, {"text_value": "Looks good"}),
        ("rating", 2, {"rating_min": 1, "rating_max": 5}, {"rating_value": 4}),
    ):
        question = Question(
            form_id=form_id,
            type=question_type,
            title=question_type,
            position=position,
            **fields,
        )
        db.add(question)
        db.flush()
        db.add(
            Answer(
                submission_id=submission_id,
                form_id=form_id,
                question_id=question.id,
                **value,
            )
        )
    option_id = option.id
    db.commit()

    with Session(db.get_bind()) as reader:
        answers = reader.scalars(
            select(Answer).where(Answer.submission_id == submission_id)
        ).all()
        assert {(row.text_value, row.rating_value) for row in answers} == {
            ("Looks good", None),
            (None, 4),
            (None, None),
        }
        choice_id = next(
            row.id
            for row in answers
            if row.text_value is None and row.rating_value is None
        )
        assert (
            reader.scalar(
                select(AnswerOption.option_id).where(
                    AnswerOption.answer_id == choice_id
                )
            )
            == option_id
        )


# A form-scoped key can be reused on a different form, even for unresolved rows.
def test_idempotency_key_is_scoped_to_form(
    db: Session, forms: tuple[Form, Form]
) -> None:
    row = {
        "idempotency_key": "request-key-0001",
        "request_hash": "a" * 64,
        "response_status": 201,
    }
    for form in forms:
        db.execute(insert(SubmissionIdempotency).values(form_id=form.id, **row))

    with pytest.raises(
        IntegrityError, match="UNIQUE constraint failed: submission_idempotency.form_id"
    ):
        db.execute(insert(SubmissionIdempotency).values(form_id=forms[0].id, **row))


# NULL submission_id skips the composite FK, not the separate form FK.
@pytest.mark.parametrize(
    "resolved", [True, False], ids=["submission-other-form", "unknown-form"]
)
def test_idempotency_rejects_invalid_form_reference(
    db: Session,
    forms: tuple[Form, Form],
    response: tuple[Submission, QuestionOption, QuestionOption],
    resolved: bool,
) -> None:
    draft, _ = forms
    submission, _, _ = response
    db.add(
        SubmissionIdempotency(
            form_id=draft.id if resolved else new_uuid(),
            submission_id=submission.id if resolved else None,
            idempotency_key="request-key-0001",
            request_hash="a" * 64,
            response_status=201,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()


# A resolved submission must not be assigned to another key on its form.
def test_idempotency_allows_only_one_key_per_submission(
    db: Session, response: tuple[Submission, QuestionOption, QuestionOption]
) -> None:
    submission, _, _ = response
    values = {
        "form_id": submission.form_id,
        "submission_id": submission.id,
        "request_hash": "a" * 64,
        "response_status": 201,
    }
    db.execute(
        insert(SubmissionIdempotency).values(
            idempotency_key="request-key-0001", **values
        )
    )
    with pytest.raises(
        IntegrityError,
        match="UNIQUE constraint failed: submission_idempotency.submission_id",
    ):
        db.execute(
            insert(SubmissionIdempotency).values(
                idempotency_key="request-key-0002", **values
            )
        )
