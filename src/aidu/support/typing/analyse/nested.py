from __future__ import annotations

import json
from typing import Any


def infer_schema(obj: Any, depth: int | None = None) -> Any:

    def merge(types: list[str]) -> str:
        types = sorted(set(types))

        if len(types) == 1:
            return types[0]

        return " | ".join(types)

    def walk(x: Any, level: int) -> Any:

        if depth is not None and level >= depth:
            return type(x).__name__

        if isinstance(x, dict):
            result = {}

            for key, value in x.items():
                result[str(key)] = walk(value, level + 1)

            return result

        if isinstance(x, list):
            if not x:
                return "list[Any]"

            item_types = [walk(v, level + 1) for v in x if not isinstance(v, dict)]

            if item_types:
                return f"list[{merge(item_types)}]"

            return "list[dict]"

        if isinstance(x, tuple):
            return "tuple[" + ", ".join(walk(v, level + 1) for v in x) + "]"

        if isinstance(x, set):
            if not x:
                return "set[Any]"

            return "set[" + merge(walk(v, level + 1) for v in x) + "]"

        return type(x).__name__

    return walk(obj, 0)


if __name__ == "__main__":
    data = {
        "name": "Wolfgang",
        "scores": [1, 2, 3],
        "meta": {
            "active": True,
            "value": 3.14,
        },
        "mixed": [1, "abc", 3.14],
    }

    print(json.dumps(infer_schema(data), indent=2))
