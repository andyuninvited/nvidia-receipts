"""
Pytest wrapper over the golden cases. Same assertions the eval badge runs.

    pytest
"""

from __future__ import annotations

import tempfile

import pytest

from tests.eval_cases import CASES, confidence_is_deterministic, run_case


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_golden_case(case):
    with tempfile.TemporaryDirectory() as tmp:
        passed, detail, _ = run_case(case, tmp)
    assert passed, detail


def test_confidence_is_deterministic():
    with tempfile.TemporaryDirectory() as tmp:
        passed, detail = confidence_is_deterministic(tmp)
    assert passed, detail
