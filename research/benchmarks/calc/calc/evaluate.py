from calc.tokenize import tokenize


def evaluate(expr):
    """Evaluate a simple arithmetic expression containing + and *."""
    tokens = tokenize(expr)
    result = tokens[0]
    i = 1
    while i < len(tokens):
        op = tokens[i]
        rhs = tokens[i + 1]
        if op == "+":
            result = result + rhs
        elif op == "*":
            result = result * rhs
        i += 2
    return result
