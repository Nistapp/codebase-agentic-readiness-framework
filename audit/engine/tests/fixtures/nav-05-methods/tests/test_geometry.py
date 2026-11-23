from shapes.geometry import Shape


class TestShape:
    def test_area(self) -> None:
        assert Shape().area() == 0.0
