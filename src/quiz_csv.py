"""The quiz CSV format, in one place.

    question;answer1;answer2;answer3;answer4;correctAnswer

Semicolon-separated, no header row, exactly six fields per row. Empty answer
cells are allowed so a question can have fewer than four options, but at least
two must be filled. `correctAnswer` has to match one of them exactly; for a
multiple-choice question with several correct answers, list them separated by
"|" (e.g. "Vienna|Graz"). Answer texts must therefore not contain "|".

Kept free of Flet and FastAPI imports so both front ends can use it.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

DELIMITER = ";"
COLUMNS = 6
MAX_ANSWERS = 4
MIN_ANSWERS = 2
# Several correct answers (multiple choice) are listed in the last column
# separated by this character, e.g. "Vienna|Graz". A single correct answer
# needs no separator, so existing files stay valid.
CORRECT_SEPARATOR = "|"


@dataclass
class Question:
    text: str
    answers: list[str] = field(default_factory=list)  # 2..4 non-empty
    correct: list[str] = field(default_factory=list)   # 1..n, each in answers

    @property
    def is_multiple(self) -> bool:
        return len(self.correct) > 1

    def as_row(self) -> list[str]:
        """Pad the answers back out to four columns for the CSV."""
        padded = list(self.answers) + [""] * (MAX_ANSWERS - len(self.answers))
        return [
            self.text,
            *padded[:MAX_ANSWERS],
            CORRECT_SEPARATOR.join(self.correct),
        ]


def validate_row(row: list[str], row_number: int) -> tuple[bool, str | None]:
    if len(row) != COLUMNS:
        return False, f"Row {row_number}: expected {COLUMNS} columns, found {len(row)}."

    # Strip a UTF-8 BOM that spreadsheet exports like to put on the first cell.
    row[0] = row[0].lstrip("﻿")

    if not row[0].strip():
        return False, f"Row {row_number}: question is empty."

    answers = row[1:5]
    non_empty = [a for a in answers if a.strip()]
    if len(non_empty) < MIN_ANSWERS:
        return (
            False,
            f"Row {row_number}: needs at least {MIN_ANSWERS} answer options.",
        )

    correct = [c.strip() for c in row[5].split(CORRECT_SEPARATOR) if c.strip()]
    if not correct:
        return False, f"Row {row_number}: no correct answer given."
    for c in correct:
        if c not in answers:
            return (
                False,
                f"Row {row_number}: every correct answer must match one of the "
                "answer columns exactly.",
            )
    return True, None


def parse(text: str) -> tuple[list[Question], list[str]]:
    """Parse CSV text into questions. Returns (questions, errors).

    Blank lines are skipped. Parsing continues after an invalid row so the
    user sees every problem at once instead of one per attempt.
    """
    questions: list[Question] = []
    errors: list[str] = []

    reader = csv.reader(io.StringIO(text), delimiter=DELIMITER)
    for number, raw in enumerate(reader, start=1):
        if not raw or all(not cell.strip() for cell in raw):
            continue
        row = list(raw)
        ok, error = validate_row(row, number)
        if not ok:
            errors.append(error or f"Row {number}: invalid.")
            continue
        questions.append(
            Question(
                text=row[0],
                answers=[a for a in row[1:5] if a.strip()],
                correct=[
                    c.strip() for c in row[5].split(CORRECT_SEPARATOR) if c.strip()
                ],
            )
        )

    if not questions and not errors:
        errors.append("The file contains no questions.")
    return questions, errors


def serialise(questions: list[Question]) -> str:
    """Questions back to CSV text, in the exact format the app expects."""
    out = io.StringIO()
    # QUOTE_MINIMAL keeps the file readable and only quotes cells that need it
    # (e.g. a question containing a semicolon).
    writer = csv.writer(
        out, delimiter=DELIMITER, quoting=csv.QUOTE_MINIMAL, lineterminator="\n"
    )
    for question in questions:
        writer.writerow(question.as_row())
    return out.getvalue()
