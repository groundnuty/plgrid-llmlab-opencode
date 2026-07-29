from ledger.money import Money


class Account:
    def __init__(self):
        self.entries = []

    def deposit(self, amount):
        self.entries.append(Money(amount))

    def balance(self):
        total = Money(0)
        for e in self.entries:
            total = total + e
        return total
