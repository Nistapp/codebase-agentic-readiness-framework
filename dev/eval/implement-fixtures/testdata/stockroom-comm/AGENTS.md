# AGENTS.md

stockroom is a tiny stock-keeping library in standard-library Python. This file is read by any harness that reads
`AGENTS.md`.

## Commands

```bash
make lint        # the house style check
make typecheck   # compiles every module
make test        # the unit tests
```

## Documentation

- `docs/` holds the documentation; start at `docs/README.md`.
- `docs/STYLE_GUIDE.md` holds the writing rules for pages under `docs/`.

## Boundaries

- `src/stockroom/` holds the library; `tests/` holds the tests. Tests never import from `tools/`.
