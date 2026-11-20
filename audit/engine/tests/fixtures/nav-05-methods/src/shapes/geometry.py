"""Plane shapes."""


class Shape:
    """A plane shape."""

    def area(self) -> float:
        """Return the area."""
        return 0.0

    def perimeter(self) -> float:
        return 0.0

    def scale(
        self,
        factor: float,
    ) -> "Shape":
        """Return a scaled copy."""
        return self

    def _cache_key(self) -> str:
        return "shape"

    def __repr__(self) -> str:
        return "Shape()"

    class Unit:
        """A length unit."""

        def label(self) -> str:
            return "m"


class _Registry:
    def register(self) -> None:
        pass


def make_shape(
    kind: str,
) -> Shape:
    """Build a shape by kind."""

    def helper() -> None:
        pass

    helper()
    return Shape()
