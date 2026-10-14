"""Unit tests for calculator.py using Python's built-in unittest."""

import unittest

from services.calculator import (
    CalculatorError,
    Ingredient,
    calculate_batch,
    calculate_ingredient_cost,
)


def banana_chip_ingredients():
    return [
        Ingredient("Bananas", 10.0, "kg", 40.0),
        Ingredient("Refined oil", 2.0, "L", 150.0),
        Ingredient("Salt", 0.2, "kg", 20.0),
        Ingredient("Spice mix", 0.1, "kg", 200.0),
    ]


def banana_chip_batch(**overrides):
    params = dict(
        product_name="Banana Chips",
        product_category="Snacks",
        batch_size=10.0,
        batch_unit="kg",
        ingredients=banana_chip_ingredients(),
        packaging_cost=150.0,
        labour_cost=200.0,
        energy_cost=100.0,
        other_cost=50.0,
        saleable_packets=40,
        selling_price=50.0,
    )
    params.update(overrides)
    return calculate_batch(**params)


class TestIngredientCost(unittest.TestCase):
    def test_simple_multiplication(self):
        self.assertAlmostEqual(calculate_ingredient_cost(10, 40), 400.0)

    def test_zero_quantity_is_allowed(self):
        self.assertAlmostEqual(calculate_ingredient_cost(0, 40), 0.0)

    def test_negative_quantity_rejected(self):
        with self.assertRaises(CalculatorError):
            calculate_ingredient_cost(-1, 40)

    def test_negative_price_rejected(self):
        with self.assertRaises(CalculatorError):
            calculate_ingredient_cost(10, -40)

    def test_non_numeric_rejected(self):
        with self.assertRaises(CalculatorError):
            calculate_ingredient_cost("ten", 40)


class TestBatchCalculation(unittest.TestCase):
    def test_banana_chips_known_values(self):
        result = banana_chip_batch()

        self.assertAlmostEqual(result.total_ingredient_cost, 724.0)
        self.assertAlmostEqual(result.total_production_cost, 1224.0)
        self.assertAlmostEqual(result.cost_per_packet, 30.60)
        self.assertAlmostEqual(result.profit_per_packet, 19.40)
        self.assertAlmostEqual(result.profit_margin_pct, 38.8)
        self.assertAlmostEqual(result.batch_profit, 776.0)

    def test_ingredient_cost_list(self):
        result = banana_chip_batch()
        costs = dict(result.ingredient_costs)

        self.assertAlmostEqual(costs["Bananas"], 400.0)
        self.assertAlmostEqual(costs["Refined oil"], 300.0)
        self.assertAlmostEqual(costs["Salt"], 4.0)
        self.assertAlmostEqual(costs["Spice mix"], 20.0)

    def test_zero_selling_price_gives_no_margin(self):
        result = banana_chip_batch(selling_price=0.0)

        self.assertIsNone(result.profit_margin_pct)
        self.assertAlmostEqual(result.profit_per_packet, -30.60)
        self.assertAlmostEqual(result.batch_profit, -1224.0)

    def test_zero_packets_rejected(self):
        with self.assertRaises(CalculatorError):
            banana_chip_batch(saleable_packets=0)

    def test_fractional_packets_rejected(self):
        with self.assertRaises(CalculatorError):
            banana_chip_batch(saleable_packets=10.5)

    def test_negative_expense_rejected(self):
        with self.assertRaises(CalculatorError):
            banana_chip_batch(packaging_cost=-10)

    def test_negative_labour_rejected(self):
        with self.assertRaises(CalculatorError):
            banana_chip_batch(labour_cost=-1)

    def test_empty_ingredients_rejected(self):
        with self.assertRaises(CalculatorError):
            banana_chip_batch(ingredients=[])

    def test_blank_ingredient_name_rejected(self):
        ingredients = [Ingredient("", 1.0, "kg", 10.0)]
        with self.assertRaises(CalculatorError):
            banana_chip_batch(ingredients=ingredients)

    def test_all_zero_quantities_rejected(self):
        ingredients = [Ingredient("Bananas", 0.0, "kg", 40.0)]
        with self.assertRaises(CalculatorError):
            banana_chip_batch(ingredients=ingredients)

    def test_blank_product_name_rejected(self):
        with self.assertRaises(CalculatorError):
            banana_chip_batch(product_name="   ")

    def test_zero_batch_size_rejected(self):
        with self.assertRaises(CalculatorError):
            banana_chip_batch(batch_size=0)

    def test_loss_making_batch(self):
        result = banana_chip_batch(selling_price=20.0)

        self.assertLess(result.profit_per_packet, 0)
        self.assertLess(result.batch_profit, 0)
        self.assertLess(result.profit_margin_pct, 0)

    def test_exact_break_even(self):
        result = banana_chip_batch(selling_price=30.60)

        self.assertAlmostEqual(result.profit_per_packet, 0.0)
        self.assertAlmostEqual(result.batch_profit, 0.0)


class TestEdgeCases(unittest.TestCase):
    """Edge cases uncovered by the original suite."""

    def base_batch(self, **overrides):
        params = dict(
            product_name="X",
            product_category="Snacks",
            batch_size=1.0,
            batch_unit="kg",
            ingredients=[Ingredient("A", 1.0, "kg", 10.0)],
            packaging_cost=0.0,
            labour_cost=0.0,
            energy_cost=0.0,
            other_cost=0.0,
            saleable_packets=1,
            selling_price=20.0,
        )
        params.update(overrides)
        return calculate_batch(**params)

    def test_infinite_packets_rejected_not_crash(self):
        """float('inf') must raise CalculatorError, not OverflowError."""
        with self.assertRaises(CalculatorError):
            self.base_batch(saleable_packets=float("inf"))

    def test_boolean_true_packets_rejected(self):
        """bool subclasses int in Python; True must not be accepted as 1 packet."""
        with self.assertRaises(CalculatorError):
            self.base_batch(saleable_packets=True)

    def test_boolean_false_packets_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(saleable_packets=False)

    def test_ordinary_int_packets_accepted(self):
        result = self.base_batch(saleable_packets=25)
        self.assertEqual(result.saleable_packets, 25)
        self.assertAlmostEqual(result.cost_per_packet, 10.0 / 25)

    def test_nan_packets_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(saleable_packets=float("nan"))

    def test_string_packets_whole_number_accepted(self):
        result = self.base_batch(saleable_packets="40")
        self.assertEqual(result.saleable_packets, 40)

    def test_string_packets_non_numeric_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(saleable_packets="abc")

    def test_whole_float_packets_accepted(self):
        result = self.base_batch(saleable_packets=40.0)
        self.assertEqual(result.saleable_packets, 40)

    def test_infinite_selling_price_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(selling_price=float("inf"))

    def test_infinite_ingredient_quantity_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(ingredients=[Ingredient("A", float("inf"), "kg", 10.0)])

    def test_nan_ingredient_price_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(ingredients=[Ingredient("A", 1.0, "kg", float("nan"))])

    def test_negative_batch_size_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(batch_size=-5)

    def test_infinite_batch_size_rejected(self):
        with self.assertRaises(CalculatorError):
            self.base_batch(batch_size=float("inf"))

    def test_huge_packet_count_still_divides(self):
        result = self.base_batch(saleable_packets=10**6)
        self.assertAlmostEqual(result.cost_per_packet, 10.0 / 10**6)

    def test_tiny_quantity_still_costs(self):
        result = self.base_batch(
            ingredients=[Ingredient("A", 0.001, "kg", 10.0)],
            saleable_packets=1,
        )
        self.assertAlmostEqual(result.total_ingredient_cost, 0.01)

    def test_unit_mismatch_is_not_converted(self):
        """Units are labels only; calculator does not convert kg to L."""
        result = self.base_batch(ingredients=[Ingredient("A", 2.0, "L", 50.0)])
        self.assertAlmostEqual(result.total_ingredient_cost, 100.0)

    def test_mixed_units_summed_as_entered(self):
        result = self.base_batch(
            ingredients=[
                Ingredient("A", 1.0, "kg", 10.0),
                Ingredient("B", 2.0, "L", 5.0),
                Ingredient("C", 3.0, "pieces", 1.0),
            ]
        )
        self.assertAlmostEqual(result.total_ingredient_cost, 10.0 + 10.0 + 3.0)

    def test_batch_size_does_not_affect_cost(self):
        """Batch size is informational; cost math uses quantities and packets."""
        small = self.base_batch(batch_size=1.0)
        large = self.base_batch(batch_size=100.0)
        self.assertAlmostEqual(small.total_production_cost, large.total_production_cost)
        self.assertAlmostEqual(small.cost_per_packet, large.cost_per_packet)

    def test_no_rounding_in_result(self):
        """Internal results keep full float precision; UI rounds for display."""
        result = self.base_batch(ingredients=[Ingredient("A", 0.1, "kg", 0.2)])
        self.assertAlmostEqual(result.total_ingredient_cost, 0.02, places=12)

    def test_margin_none_only_when_price_zero(self):
        zero = self.base_batch(selling_price=0.0)
        paid = self.base_batch(selling_price=0.01)
        self.assertIsNone(zero.profit_margin_pct)
        self.assertIsNotNone(paid.profit_margin_pct)


if __name__ == "__main__":
    unittest.main()
