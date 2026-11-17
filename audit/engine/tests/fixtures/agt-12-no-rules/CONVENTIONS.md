# Code conventions

These rules cover what the tools do not enforce. The formatter and linter settings live in `pyproject.toml`.

## Naming

Modules, functions and variables use `snake_case`. Classes use `PascalCase`.

## Layering

Application code lives in `src/`. Tests import from `src/`, and `src/` does not import from `tests/`.

## Errors and logging

Raise a `ValueError` that names the bad input. Log through the `logging` module, not with `print`.

## Testing

Each test lives in `tests/`, in a file named `test_<module>.py`, and touches no network.
