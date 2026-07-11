# Copyright (C) 2026 Dr. Wolfgang Spahn, PHBern
#
# MIT License — see LICENSE file for details.
# If you use this software in academic work, citation of the original author is requested.
import re

VALID_TOP_LEVEL_CALL = re.compile(r"^\s*(diff|integrate|solve|simplify|expand|factor)\s*\(.*\)\s*$")


def assert_valid_sympy_problem(problem: str) -> None:
    if not VALID_TOP_LEVEL_CALL.match(problem):
        raise ValueError(f"Invalid symbolic syntax. Expected SymPy-style call like diff(4*x**3, x), integrate(sin(x), x), solve(x**2 - 4, x), simplify(...). Got: {problem!r}")
