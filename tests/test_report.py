"""Tests for report.py product development summary generation."""

import unittest

from services.calculator import Ingredient, calculate_batch
from services.report import build_report, money


def banana_chip_result():
    return calculate_batch(
        product_name="Banana Chips",
        product_category="Snacks",
        batch_size=10.0,
        batch_unit="kg",
        ingredients=[
            Ingredient("Bananas", 10.0, "kg", 40.0),
            Ingredient("Refined oil", 2.0, "L", 150.0),
            Ingredient("Salt", 0.2, "kg", 20.0),
            Ingredient("Spice mix", 0.1, "kg", 200.0),
        ],
        packaging_cost=150.0,
        labour_cost=200.0,
        energy_cost=100.0,
        other_cost=50.0,
        saleable_packets=40,
        selling_price=50.0,
    )


BANANA_PRODUCT = {
    "name": "Banana Chips",
    "category": "Snacks",
    "batch_size": 10.0,
    "batch_unit": "kg",
    "budget": 5000.0,
}


class TestBuildReport(unittest.TestCase):
    def test_full_report_sections(self):
        text = build_report(
            product=BANANA_PRODUCT,
            result=banana_chip_result(),
            chat_history=[
                {"role": "user", "text": "How should I package banana chips?"},
                {"role": "model", "text": "Use metallised pouches with a strong heat seal."},
            ],
            generated_at="2026-10-14 12:00",
        )

        self.assertIn("# FoodFounder AI — Product Development Summary", text)
        self.assertIn("Generated: 2026-10-14 12:00", text)
        self.assertIn("## 1. Product details", text)
        self.assertIn("Banana Chips", text)
        self.assertIn("## 2. Batch and ingredients", text)
        self.assertIn("Bananas", text)
        self.assertIn("## 3. Cost breakdown", text)
        self.assertIn("₹1,224.00", text)
        self.assertIn("## 4. Per-packet economics", text)
        self.assertIn("₹30.60", text)
        self.assertIn("38.8%", text)
        self.assertIn("₹776.00", text)
        self.assertIn("## 5. Packaging and process reminders", text)
        self.assertIn("## 6. AI recommendations", text)
        self.assertIn("metallised pouches", text)
        self.assertIn("## 7. Assumptions and limitations", text)
        self.assertIn("not scientifically validated", text)
        self.assertIn("## 8. Useful sources", text)
        self.assertIn("foscos.fssai.gov.in", text)
        self.assertIn("## 9. Suggested next steps", text)
        self.assertIn("₹5,000.00", text)

    def test_ingredient_table_has_quantities(self):
        text = build_report(result=banana_chip_result())
        self.assertIn("| Bananas | 10 | kg | ₹40.00 | ₹400.00 |", text)

    def test_handles_missing_product_and_result(self):
        text = build_report()
        self.assertIn("No product set", text)
        self.assertIn("No batch calculated yet", text)
        self.assertIn("No chat yet", text)

    def test_zero_price_margin_note(self):
        result = calculate_batch(
            product_name="Test",
            product_category="Snacks",
            batch_size=1.0,
            batch_unit="kg",
            ingredients=[Ingredient("X", 1.0, "kg", 10.0)],
            packaging_cost=0.0,
            labour_cost=0.0,
            energy_cost=0.0,
            other_cost=0.0,
            saleable_packets=1,
            selling_price=0.0,
        )
        text = build_report(result=result)
        self.assertIn("Not applicable (selling price is 0)", text)

    def test_long_chat_text_truncated(self):
        chat_history = [
            {"role": "user", "text": "x" * 1000},
        ]
        text = build_report(chat_history=chat_history)
        self.assertIn("x" * 400 + "…", text)
        self.assertNotIn("x" * 401 + "…", text)

    def test_money_format(self):
        self.assertEqual(money(1224), "₹1,224.00")
        self.assertEqual(money(0), "₹0.00")


if __name__ == "__main__":
    unittest.main()
