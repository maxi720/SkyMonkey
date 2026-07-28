"""Turning a weighted set of quizzes into a test's question set.

Pure functions (no Supabase, no FastAPI) so they are easy to test and could be
reused by the mobile side later. A "question" here is a quiz_csv.Question.
"""

from __future__ import annotations

import random

import quiz_csv


def allocate(weights: list[int], total: int) -> list[int]:
    """Split `total` questions across sources by percentage `weights`.

    Uses the largest-remainder method so the parts always add up to exactly
    `total` even when the percentages don't divide evenly (e.g. 50/30/20 % of
    10 -> 5/3/2, of 7 -> 4/2/1).
    """
    if total <= 0 or not weights:
        return [0] * len(weights)
    weight_sum = sum(weights) or 1
    raw = [w / weight_sum * total for w in weights]
    floors = [int(x) for x in raw]
    remainder = total - sum(floors)
    # Hand the leftover questions to the largest fractional parts first.
    order = sorted(range(len(weights)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in range(remainder):
        floors[order[i]] += 1
    return floors


def question_to_row(q: quiz_csv.Question) -> dict:
    """A question as it is stored in test_questions / test_pool / an attempt.

    Correct answers are joined with the CSV separator so the (text) columns
    hold one value; a multiple-choice question just lists several.
    """
    return {
        "prompt": q.text,
        "options": list(q.answers),
        "correct": quiz_csv.CORRECT_SEPARATOR.join(q.correct),
    }


def draw(questions: list[quiz_csv.Question], count: int) -> list[quiz_csv.Question]:
    """Pick `count` questions at random, without repeats."""
    if count >= len(questions):
        picked = list(questions)
        random.shuffle(picked)
        return picked
    return random.sample(questions, count)
