class Money:
    """An amount of money. Currently assumes a single implicit currency."""

    def __init__(self, amount):
        self.amount = amount

    def __add__(self, other):
        return Money(self.amount + other.amount)

    def __eq__(self, other):
        return self.amount == other.amount

    def __repr__(self):
        return f"Money({self.amount})"
