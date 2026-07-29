import pytest
from calc.evaluate import evaluate


def test_single_number():
    assert evaluate("7") == 7


def test_addition():
    assert evaluate("2 + 3") == 5


def test_multiplication():
    assert evaluate("4 * 5") == 20


def test_precedence():
    assert evaluate("2 + 3 * 4") == 14


def test_left_to_right_same_precedence():
    assert evaluate("10 + 2 + 3") == 15


def test_empty_raises():
    with pytest.raises(ValueError):
        evaluate("")
