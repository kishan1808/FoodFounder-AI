"""Unit tests for services/persistence.py (local JSON state save/restore)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from services.calculator import CostResult, Ingredient
from services.persistence import (
    SCHEMA_VERSION,
    capture_session_state,
    has_content,
    load_state,
    restore_session_state,
    save_state,
)


class _TempStatePath(unittest.TestCase):
    """Base: each test gets its own temp state file path (deleted on teardown)."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json", prefix="ff_persist_test_")
        os.close(fd)
        os.unlink(self.path)  # start with no file

    def tearDown(self):
        for p in (self.path, self.path + ".tmp"):
            if os.path.exists(p):
                os.unlink(p)


class TestLoadState(_TempStatePath):
    def test_missing_file_returns_empty_defaults(self):
        state = load_state(self.path)
        self.assertEqual(state["version"], SCHEMA_VERSION)
        self.assertIsNone(state["product"])
        self.assertIsNone(state["ingredients"])
        self.assertIsNone(state["calculator_inputs"])
        self.assertIsNone(state["cost_result"])
        self.assertIsNone(state["chat_history"])

    def test_empty_file_returns_empty_defaults(self):
        Path(self.path).write_text("", encoding="utf-8")
        state = load_state(self.path)
        self.assertIsNone(state["product"])

    def test_malformed_json_returns_empty_defaults(self):
        Path(self.path).write_text("{not valid json", encoding="utf-8")
        state = load_state(self.path)
        self.assertIsNone(state["product"])
        self.assertIsNone(state["chat_history"])

    def test_non_dict_json_returns_empty_defaults(self):
        Path(self.path).write_text("[1, 2, 3]", encoding="utf-8")
        state = load_state(self.path)
        self.assertIsNone(state["product"])

    def test_wrong_version_returns_empty_defaults(self):
        payload = {"version": 999, "product": {"name": "X", "batch_size": 1}}
        Path(self.path).write_text(json.dumps(payload), encoding="utf-8")
        state = load_state(self.path)
        self.assertIsNone(state["product"])

    def test_valid_product_roundtrip(self):
        product = {
            "name": "Banana Chips",
            "category": "Snacks",
            "batch_size": 10.0,
            "batch_unit": "kg",
            "budget": 5000.0,
        }
        self.assertTrue(save_state({"product": product}, self.path))
        state = load_state(self.path)
        self.assertEqual(state["product"], product)

    def test_invalid_product_dropped(self):
        payload = {
            "version": SCHEMA_VERSION,
            "product": {"name": "", "batch_size": 10},  # empty name -> invalid
        }
        Path(self.path).write_text(json.dumps(payload), encoding="utf-8")
        state = load_state(self.path)
        self.assertIsNone(state["product"])

    def test_product_with_bad_batch_dropped(self):
        payload = {
            "version": SCHEMA_VERSION,
            "product": {"name": "X", "batch_size": -5},
        }
        Path(self.path).write_text(json.dumps(payload), encoding="utf-8")
        state = load_state(self.path)
        self.assertIsNone(state["product"])

    def test_chat_history_order_preserved_and_invalid_dropped(self):
        history = [
            {"role": "user", "text": "q1"},
            {"role": "model", "text": "a1"},
            "not-a-dict",
            {"role": "user", "text": "   "},  # blank -> dropped
            {"role": "model", "text": "a2"},
            {"role": "weird", "text": "a3"},  # role normalized to model
        ]
        self.assertTrue(save_state({"chat_history": history}, self.path))
        state = load_state(self.path)
        self.assertEqual(
            state["chat_history"],
            [
                {"role": "user", "text": "q1"},
                {"role": "model", "text": "a1"},
                {"role": "model", "text": "a2"},
                {"role": "model", "text": "a3"},
            ],
        )

    def test_calculator_inputs_validated(self):
        inputs = {
            "packaging_cost": 150.0,
            "labour_cost": -1.0,  # negative -> dropped
            "energy_cost": "abc",  # invalid -> dropped
            "other_cost": 50.0,
            "saleable_packets": 40.5,  # not whole -> dropped
            "selling_price": 50.0,
        }
        self.assertTrue(save_state({"calculator_inputs": inputs}, self.path))
        state = load_state(self.path)
        self.assertEqual(
            state["calculator_inputs"],
            {"packaging_cost": 150.0, "other_cost": 50.0, "selling_price": 50.0},
        )

    def test_cost_result_roundtrip_preserves_fields(self):
        result = CostResult(
            product_name="Chips",
            product_category="Snacks",
            batch_size=10.0,
            batch_unit="kg",
            ingredients=(Ingredient("Banana", 10.0, "kg", 40.0),),
            ingredient_costs=(("Banana", 400.0),),
            total_ingredient_cost=400.0,
            packaging_cost=150.0,
            labour_cost=200.0,
            energy_cost=100.0,
            other_cost=50.0,
            total_production_cost=900.0,
            saleable_packets=40,
            cost_per_packet=22.5,
            selling_price=50.0,
            profit_per_packet=27.5,
            profit_margin_pct=55.0,
            batch_profit=1100.0,
        )
        self.assertTrue(save_state({"cost_result": result}, self.path))
        state = load_state(self.path)
        restored = state["cost_result"]
        self.assertIsInstance(restored, CostResult)
        self.assertEqual(restored.product_name, "Chips")
        self.assertEqual(restored.total_production_cost, 900.0)
        self.assertEqual(restored.saleable_packets, 40)
        self.assertEqual(restored.profit_margin_pct, 55.0)
        self.assertEqual(restored.ingredients[0].name, "Banana")

    def test_cost_result_none_margin_preserved(self):
        result = CostResult(
            product_name="Chips",
            product_category="Snacks",
            batch_size=10.0,
            batch_unit="kg",
            ingredients=(),
            ingredient_costs=(),
            total_ingredient_cost=0.0,
            packaging_cost=0.0,
            labour_cost=0.0,
            energy_cost=0.0,
            other_cost=0.0,
            total_production_cost=0.0,
            saleable_packets=1,
            cost_per_packet=0.0,
            selling_price=0.0,
            profit_per_packet=0.0,
            profit_margin_pct=None,
            batch_profit=0.0,
        )
        self.assertTrue(save_state({"cost_result": result}, self.path))
        state = load_state(self.path)
        self.assertIsNone(state["cost_result"].profit_margin_pct)

    def test_malformed_cost_result_dropped(self):
        payload = {"version": SCHEMA_VERSION, "cost_result": {"product_name": "X"}}
        Path(self.path).write_text(json.dumps(payload), encoding="utf-8")
        state = load_state(self.path)
        self.assertIsNone(state["cost_result"])


class TestSaveState(_TempStatePath):
    def test_save_skipped_when_empty(self):
        self.assertFalse(save_state({}, self.path))
        self.assertFalse(os.path.exists(self.path))

    def test_save_skipped_when_all_none(self):
        data = {
            "product": None,
            "ingredients": None,
            "calculator_inputs": None,
            "cost_result": None,
            "chat_history": None,
        }
        self.assertFalse(save_state(data, self.path))
        self.assertFalse(os.path.exists(self.path))

    def test_save_creates_file_atomically(self):
        self.assertTrue(save_state({"product": {"name": "X", "batch_size": 1}}, self.path))
        self.assertTrue(os.path.exists(self.path))
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_has_content(self):
        self.assertFalse(has_content({}))
        self.assertFalse(has_content({"product": None}))
        self.assertTrue(has_content({"product": {"name": "X"}}))
        self.assertTrue(has_content({"chat_history": [{"role": "user", "text": "hi"}]}))


class TestSessionBridge(_TempStatePath):
    def test_restore_populates_missing_keys(self):
        product = {"name": "Chips", "category": "Snacks", "batch_size": 5.0, "batch_unit": "kg", "budget": 100.0}
        chat = [{"role": "user", "text": "q"}, {"role": "model", "text": "a"}]
        save_state({"product": product, "chat_history": chat}, self.path)

        session = {}
        restore_session_state(session, self.path)
        self.assertEqual(session["product"], product)
        self.assertEqual(session["chat_history"], chat)

    def test_restore_does_not_overwrite_existing(self):
        save_state({"product": {"name": "FromFile", "batch_size": 5.0}}, self.path)
        session = {"product": {"name": "InSession", "batch_size": 9.0}}
        restore_session_state(session, self.path)
        self.assertEqual(session["product"]["name"], "InSession")

    def test_restore_seeds_ingredients_dataframe(self):
        rows = [
            {"Ingredient": "Banana", "Quantity": 10.0, "Unit": "kg", "Price per unit (INR)": 40.0},
            {"Ingredient": "Oil", "Quantity": 2.0, "Unit": "L", "Price per unit (INR)": 150.0},
        ]
        save_state({"ingredients": rows}, self.path)
        session = {}
        restore_session_state(session, self.path)
        self.assertIn("ingredients_df", session)
        self.assertIn("ingredients_seed", session)
        self.assertEqual(len(session["ingredients_df"]), 2)
        self.assertEqual(session["ingredients_df"].iloc[0]["Ingredient"], "Banana")

    def test_restore_sets_calculator_input_keys(self):
        inputs = {
            "packaging_cost": 250.0,
            "labour_cost": 180.0,
            "energy_cost": 90.0,
            "other_cost": 40.0,
            "saleable_packets": 30,
            "selling_price": 45.0,
        }
        save_state({"calculator_inputs": inputs}, self.path)
        session = {}
        restore_session_state(session, self.path)
        self.assertEqual(session["packaging_cost"], 250.0)
        self.assertEqual(session["saleable_packets"], 30)
        self.assertEqual(session["selling_price"], 45.0)

    def test_capture_and_restore_roundtrip(self):
        result = CostResult(
            product_name="Chips",
            product_category="Snacks",
            batch_size=10.0,
            batch_unit="kg",
            ingredients=(Ingredient("Banana", 10.0, "kg", 40.0),),
            ingredient_costs=(("Banana", 400.0),),
            total_ingredient_cost=400.0,
            packaging_cost=150.0,
            labour_cost=200.0,
            energy_cost=100.0,
            other_cost=50.0,
            total_production_cost=900.0,
            saleable_packets=40,
            cost_per_packet=22.5,
            selling_price=50.0,
            profit_per_packet=27.5,
            profit_margin_pct=55.0,
            batch_profit=1100.0,
        )
        session = {
            "product": {"name": "Chips", "category": "Snacks", "batch_size": 10.0, "batch_unit": "kg", "budget": 5000.0},
            "chat_history": [{"role": "user", "text": "q"}, {"role": "model", "text": "a"}],
            "cost_result": result,
            "packaging_cost": 150.0,
            "saleable_packets": 40,
        }
        data = capture_session_state(session)
        self.assertTrue(save_state(data, self.path))

        restored = {}
        restore_session_state(restored, self.path)
        self.assertEqual(restored["product"]["name"], "Chips")
        self.assertEqual(len(restored["chat_history"]), 2)
        self.assertEqual(restored["cost_result"].total_production_cost, 900.0)
        self.assertEqual(restored["packaging_cost"], 150.0)

    def test_capture_ignores_non_dataframe_ingredients(self):
        session = {"ingredients_df": "not-a-dataframe"}
        data = capture_session_state(session)
        self.assertIsNone(data["ingredients"])

    def test_restore_with_malformed_file_leaves_session_empty(self):
        Path(self.path).write_text("garbage", encoding="utf-8")
        session = {}
        restore_session_state(session, self.path)
        self.assertEqual(session, {})


if __name__ == "__main__":
    unittest.main()
