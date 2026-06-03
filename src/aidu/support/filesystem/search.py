from pathlib import Path


def find_up(
    filename: str,
    start: str | Path | None = None,
) -> Path | None:
    """
    Search parent directories upwards until the file is found.

    Parameters
    ----------
    filename:
        Target filename to locate.

    start:
        Starting directory.
        Defaults to current working directory.

    Returns
    -------
    Path | None
        Resolved path if found, otherwise None.
    """

    current = Path(start or Path.cwd()).resolve()

    home = Path.home().resolve()

    while True:
        candidate = current / filename

        if candidate.exists():
            return candidate

        if current == home:
            return None

        if current.parent == current:
            return None

        current = current.parent
