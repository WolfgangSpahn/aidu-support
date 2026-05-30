from pathlib import Path

from aidu.support.filesystem.search import find_up


def test_find_up_returns_none_for_missing_file(tmp_path):

    result = find_up(
        "missing.txt",
        start=tmp_path,
    )

    assert result is None