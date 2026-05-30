# AIDu Support

`aidu.support` provides small reusable infrastructural utilities shared across the AIDu ecosystem.

The package contains:

* text utilities
* regex helpers
* filesystem helpers
* runtime helpers
* serialization utilities
* environment helpers
* typing support

The design intentionally avoids:

* large `utils.py` modules
* miscellaneous helper dumping grounds
* framework-heavy abstractions

Instead, functionality is organized into small semantic namespaces inspired by Haskell-style modularity.

---

# Source Structure

```text id="7m4q2x"
src/aidu/support
├── text/
├── regex/
├── filesystem/
├── runtime/
├── serialization/
├── environment/
└── typing/
```

---

# Architectural Position

```text id="3n8v5k"
aidu.support
    generic infrastructural primitives

aidu.ai.core
    AI runtime contracts

aidu.ai.llm
    conversational intelligence

aidu.ai.controller
    orchestration runtime
```

---

# Development

## Install

```bash
uv sync
```

## Lint

```bash
uv run ruff check .
```

## Format

```bash
uv run ruff format .
```

---

# License

MIT License.

Copyright (c) 2026 Wolfgang Spahn, PHBern.

Please follow standard academic practice when using this software in research or publications.
