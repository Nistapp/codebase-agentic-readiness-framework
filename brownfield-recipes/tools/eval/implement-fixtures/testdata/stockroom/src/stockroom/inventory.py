"""The inventory: item counts by name."""

from __future__ import annotations


class Inventory:
    """Counts of items by name. Counts never go below zero."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def add(self, name: str, count: int = 1) -> int:
        """Add `count` of `name` and return the new count; a count below one is refused with a ValueError."""
        if count < 1:
            raise ValueError("count must be at least one")
        self._counts[name] = self._counts.get(name, 0) + count
        return self._counts[name]

    def take(self, name: str, count: int = 1) -> int:
        """Take `count` of `name` out and return what is left; taking more than there is raises a ValueError."""
        have = self._counts.get(name, 0)
        if count > have:
            raise ValueError(f"only {have} of {name} in stock, cannot take {count}")
        self._counts[name] = have - count
        return self._counts[name]

    def low(self, threshold: int = 2) -> list[str]:
        """The names whose count is at or below `threshold`, in alphabetical order, for the weekly reorder list."""
        return sorted(name for name, count in self._counts.items() if count <= threshold)
