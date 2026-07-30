"""Executable standalone example for entry-test scoring experts.

Run from the ``aidu-support`` directory with:

    uv run python -m scoring.entry_test
"""

from aidu.support.scoring.entry_test import _smoke_test


if __name__ == "__main__":
    _smoke_test()
