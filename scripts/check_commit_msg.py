"""Reject commit messages that are not flat conventional commits."""

import re
import sys

TYPES = {
    "feat": "new feature",
    "fix": "bug fix",
    "refactor": "code change, same behavior",
    "perf": "faster or lighter code",
    "test": "add or fix tests",
    "docs": "documentation only",
    "style": "formatting only",
    "chore": "tooling, config, dependencies",
}
PATTERN = re.compile(rf"^({'|'.join(TYPES)}): \S.*")

# Messages git writes itself
GIT_GENERATED = ("Merge ", 'Revert "')

TYPE_LIST = "\n".join(f"  {name:<9}{use}" for name, use in TYPES.items())
HELP = f"""
Format: "type: description" (lowercase type, no scope in parens)

Types:
{TYPE_LIST}
"""


def first_line(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                return line.rstrip("\n")
    return ""


def main():
    subject = first_line(sys.argv[1])
    if subject.startswith(GIT_GENERATED) or PATTERN.match(subject):
        return 0
    print(f"Bad commit message: {subject!r}", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
