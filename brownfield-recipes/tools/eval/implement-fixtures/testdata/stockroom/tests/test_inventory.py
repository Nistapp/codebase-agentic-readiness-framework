import unittest

from stockroom import Inventory


class InventoryTests(unittest.TestCase):
    def test_add_and_take(self) -> None:
        stock = Inventory()
        self.assertEqual(stock.add("bolt", 5), 5)
        self.assertEqual(stock.take("bolt", 2), 3)

    def test_take_too_many(self) -> None:
        stock = Inventory()
        stock.add("nut")
        with self.assertRaises(ValueError):
            stock.take("nut", 2)

    def test_low(self) -> None:
        stock = Inventory()
        stock.add("bolt", 5)
        stock.add("nut", 1)
        self.assertEqual(stock.low(), ["nut"])


if __name__ == "__main__":
    unittest.main()
