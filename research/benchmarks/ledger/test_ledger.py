import pytest
from ledger.money import Money
from ledger.account import Account


def test_money_requires_currency():
    m = Money(10, "PLN")
    assert m.amount == 10
    assert m.currency == "PLN"


def test_same_currency_adds():
    assert Money(10, "PLN") + Money(5, "PLN") == Money(15, "PLN")


def test_mixed_currency_rejected():
    with pytest.raises(ValueError):
        Money(10, "PLN") + Money(5, "EUR")


def test_equality_is_currency_aware():
    assert Money(10, "PLN") != Money(10, "EUR")


def test_account_tracks_currency():
    a = Account("PLN")
    a.deposit(10)
    a.deposit(5)
    assert a.balance() == Money(15, "PLN")


def test_account_rejects_foreign_deposit():
    a = Account("PLN")
    with pytest.raises(ValueError):
        a.deposit(Money(5, "EUR"))


def test_cents_do_not_drift():
    a = Account("PLN")
    for _ in range(10):
        a.deposit(0.1)
    assert a.balance() == Money(1.00, "PLN")
