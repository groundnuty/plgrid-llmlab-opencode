"""Strip local paths and grant ids from a benchmark report or table, in place.

The report and the per-run table are meant to be committed, so they must not carry
the machine's temp directory, the checkout path, the home directory, or the grant a
run happened to use. Paths are replaced literally, longest first, so a temp
directory inside $HOME becomes <tmp> rather than ~/...

Usage: python3 redact.py <file> <tmp-dir> <repo-root> <home>
"""

import re
import sys


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__.strip().splitlines()[-1])
    path, tmp, root, home = sys.argv[1:]
    with open(path) as f:
        text = f.read()
    for literal, label in sorted([(tmp, "<tmp>"), (root, "<repo>"), (home, "~")],
                                 key=lambda pair: -len(pair[0])):
        literal = literal.rstrip("/")
        if literal:
            text = text.replace(literal, label)
            # macOS resolves /tmp and /var under /private; catch both spellings
            if literal.startswith("/private/"):
                text = text.replace(literal[len("/private"):], label)
            else:
                text = text.replace("/private" + literal, label)
    text = re.sub(r"(grant ')[^']+(')", r"\g<1><grant>\g<2>", text)
    with open(path, "w") as f:
        f.write(text)


if __name__ == "__main__":
    main()
