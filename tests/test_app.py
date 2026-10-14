"""Automated UI smoke tests for app.py using Streamlit's AppTest framework."""

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def isolate_state_file():
    """Point the app's persistence at a fresh (nonexistent) temp file."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="ff_test_state_")
    os.close(fd)
    os.unlink(path)
    os.environ["FOODFOUNDER_STATE_FILE"] = path
    return path


def build_app_test(state_path=None):
    if state_path is not None:
        os.environ["FOODFOUNDER_STATE_FILE"] = str(state_path)
    else:
        isolate_state_file()
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    app.run()
    return app


def click_button(app, label):
    for button in app.button:
        if button.label == label:
            button.click()
            app.run()
            return True
    return False


def set_radio(app, label):
    app.sidebar.radio[0].set_value(label)
    app.run()


class TestApp(unittest.TestCase):
    def test_home_page_renders_without_exception(self):
        app = build_app_test()

        self.assertEqual(len(app.exception), 0)
        titles = [element.value for element in app.title]
        self.assertTrue(any("FoodFounder" in title for title in titles))

    def test_home_page_saves_product(self):
        app = build_app_test()
        app.text_input[0].set_value("Banana Chips")
        app.number_input[0].set_value(10.0)

        clicked = False
        for button in app.button:
            if button.label == "Start":
                button.click()
                app.run()
                clicked = True
                break

        self.assertTrue(clicked)
        self.assertEqual(len(app.exception), 0)
        self.assertIn("product", app.session_state)
        self.assertEqual(app.session_state["product"]["name"], "Banana Chips")

    def test_calculator_default_calculation(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(app.exception), 0)

        clicked = click_button(app, "Calculate costs")
        self.assertTrue(clicked, "Calculate costs button not found")
        self.assertEqual(len(app.exception), 0)

        result = app.session_state["cost_result"]
        self.assertAlmostEqual(result.total_production_cost, 1224.0)
        self.assertAlmostEqual(result.cost_per_packet, 30.60)
        self.assertAlmostEqual(result.profit_per_packet, 19.40)
        self.assertAlmostEqual(result.batch_profit, 776.0)

        metric_labels = [metric.label for metric in app.metric]
        self.assertIn("Cost / packet", metric_labels)
        self.assertIn("Batch profit", metric_labels)

        download_labels = [button.label for button in app.download_button]
        self.assertTrue(any("Download" in label for label in download_labels))

    def test_calculator_example_button(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")

        clicked = click_button(app, "Load banana chips example")
        self.assertTrue(clicked, "Example button not found")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["product"]["name"], "Banana Chips")

        clicked = click_button(app, "Calculate costs")
        self.assertTrue(clicked)
        self.assertEqual(len(app.exception), 0)
        self.assertAlmostEqual(app.session_state["cost_result"].total_production_cost, 1224.0)

    def test_calculator_error_path_blank_product_name(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(app.exception), 0)

        name_inputs = [
            text_input
            for text_input in app.text_input
            if "product name" in str(text_input.label).lower()
        ]
        self.assertTrue(name_inputs, "Product name input not found")
        name_inputs[0].set_value("   ")

        click_button(app, "Calculate costs")
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn("cost_result", app.session_state)
        self.assertTrue(any("Cannot calculate" in error.value for error in app.error))

    def test_ai_page_renders(self):
        app = build_app_test()
        set_radio(app, "AI Guidance")

        self.assertEqual(len(app.exception), 0)
        titles = [element.value for element in app.title]
        self.assertTrue(any("AI Guidance" in title for title in titles))
        captions = " ".join(str(caption.value) for caption in app.caption)
        self.assertIn("FSSAI", captions)
        markdown_text = " ".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("Barrier against moisture", markdown_text)
        self.assertIn("foscos.fssai.gov.in", markdown_text)
        self.assertIn("Product development summary", markdown_text)
        download_labels = [button.label for button in app.download_button]
        self.assertTrue(any("Download" in label for label in download_labels))

    def test_full_demo_flow_end_to_end(self):
        app = build_app_test()

        app.text_input[0].set_value("Banana Chips")
        for button in app.button:
            if button.label == "Start":
                button.click()
                app.run()
                break
        self.assertEqual(app.session_state["product"]["name"], "Banana Chips")

        set_radio(app, "Cost Calculator")
        click_button(app, "Calculate costs")
        result = app.session_state["cost_result"]
        self.assertAlmostEqual(result.cost_per_packet, 30.60)
        self.assertAlmostEqual(result.batch_profit, 776.0)

        set_radio(app, "AI Guidance")
        self.assertEqual(len(app.exception), 0)
        markdown_text = " ".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("Product development summary", markdown_text)
        self.assertIn("Banana Chips", markdown_text)


class TestStatePersistence(unittest.TestCase):
    """Regression tests for state surviving navigation and simulated refresh."""

    def _save_product(self, app, name="Masala Chips", batch=12.0):
        app.text_input[0].set_value(name)
        app.number_input[0].set_value(batch)
        for button in app.button:
            if button.label == "Start":
                button.click()
                app.run()
                break

    def test_product_name_survives_navigation(self):
        app = build_app_test()
        self._save_product(app)
        self.assertEqual(app.session_state["product"]["name"], "Masala Chips")

        set_radio(app, "Cost Calculator")
        set_radio(app, "Home / Product Setup")
        self.assertEqual(len(app.exception), 0)

        # The form field must show the saved name, not an empty string.
        name_inputs = [
            ti for ti in app.text_input if "product name" in str(ti.label).lower()
        ]
        self.assertTrue(name_inputs, "product name input not found on Home")
        self.assertEqual(name_inputs[0].value, "Masala Chips")

        # Session product and sidebar info stay consistent.
        self.assertEqual(app.session_state["product"]["name"], "Masala Chips")
        info_text = " ".join(str(i.value) for i in app.info)
        self.assertIn("Masala Chips", info_text)

    def test_product_batch_size_survives_navigation(self):
        app = build_app_test()
        self._save_product(app, name="Chili Pickle", batch=7.5)
        set_radio(app, "Cost Calculator")
        set_radio(app, "Home / Product Setup")
        self.assertEqual(app.session_state["product"]["batch_size"], 7.5)
        self.assertEqual(app.session_state["product"]["name"], "Chili Pickle")

    def test_ingredient_rows_survive_navigation_via_session(self):
        app = build_app_test()
        self._save_product(app)
        set_radio(app, "Cost Calculator")
        # The data editor's current state is captured into session_state.
        self.assertIn("ingredients_df", app.session_state)
        rows_before = app.session_state["ingredients_df"].copy()
        set_radio(app, "Home / Product Setup")
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(app.session_state["ingredients_df"]), len(rows_before))

    def test_calculator_inputs_survive_navigation(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        for nb in app.number_input:
            if nb.label == "Packaging cost (₹)":
                nb.set_value(300.0)
                app.run()
                break
        self.assertEqual(app.session_state["packaging_cost"], 300.0)
        set_radio(app, "Home / Product Setup")
        set_radio(app, "Cost Calculator")
        self.assertEqual(app.session_state["packaging_cost"], 300.0)

    def test_cost_result_survives_navigation(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        click_button(app, "Calculate costs")
        total = app.session_state["cost_result"].total_production_cost
        set_radio(app, "AI Guidance")
        set_radio(app, "Cost Calculator")
        self.assertAlmostEqual(
            app.session_state["cost_result"].total_production_cost, total
        )

    def test_state_restored_in_fresh_session(self):
        """Simulate a browser refresh: a brand-new AppTest reading the same file."""
        state_path = isolate_state_file()
        app = build_app_test(state_path)
        self._save_product(app)
        set_radio(app, "Cost Calculator")
        click_button(app, "Calculate costs")
        expected_total = app.session_state["cost_result"].total_production_cost
        expected_name = app.session_state["product"]["name"]

        # New AppTest instance = fresh session (like a browser refresh).
        app2 = build_app_test(state_path)
        self.assertEqual(len(app2.exception), 0)
        self.assertEqual(app2.session_state["product"]["name"], expected_name)
        self.assertAlmostEqual(
            app2.session_state["cost_result"].total_production_cost, expected_total
        )
        # Calculator input restored too.
        self.assertIn("packaging_cost", app2.session_state)

    def test_chat_history_restored_in_fresh_session(self):
        from unittest import mock

        from tests.test_app_chat import ok_chat_factory

        state_path = isolate_state_file()
        app = build_app_test(state_path)
        set_radio(app, "AI Guidance")
        calls = []
        with mock.patch("services.ai_assistant.chat", ok_chat_factory(calls, "Use foil pouches.")):
            app.chat_input[0].set_value("How do I store chips?")
            app.run()
        history_before = list(app.session_state["chat_history"])
        self.assertGreaterEqual(len(history_before), 2)

        app2 = build_app_test(state_path)
        set_radio(app2, "AI Guidance")
        history_after = app2.session_state["chat_history"]
        self.assertEqual(
            [t["text"] for t in history_after],
            [t["text"] for t in history_before],
        )
        # Order is chronological: user question before model answer.
        roles = [t["role"] for t in history_after]
        self.assertEqual(roles[0], "user")
        self.assertIn("model", roles)

    def test_malformed_state_file_ignored_safely(self):
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".json", prefix="ff_bad_state_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{this is not valid json")
        try:
            app = build_app_test(path)
            self.assertEqual(len(app.exception), 0)
            self.assertNotIn("product", app.session_state)
        finally:
            os.unlink(path)

    def test_empty_startup_without_state_file(self):
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".json", prefix="ff_no_state_")
        os.close(fd)
        os.unlink(path)
        os.environ["FOODFOUNDER_STATE_FILE"] = path
        app = AppTest.from_file(APP_PATH, default_timeout=30)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn("product", app.session_state)
        self.assertNotIn("cost_result", app.session_state)


class TestNavigation(unittest.TestCase):
    """Page selection via URL query parameter."""

    def test_page_restored_from_query_params(self):
        isolate_state_file()
        app = AppTest.from_file(APP_PATH, default_timeout=30)
        app.query_params["page"] = "Cost Calculator"
        app.run()
        self.assertEqual(len(app.exception), 0)
        titles = [t.value for t in app.title]
        self.assertTrue(any("Cost Calculator" in t for t in titles))

    def test_page_defaults_to_home_without_query_params(self):
        app = build_app_test()
        titles = [t.value for t in app.title]
        self.assertTrue(any("FoodFounder" in t for t in titles))

    def test_page_synced_to_url_on_click(self):
        app = build_app_test()
        app.sidebar.radio[0].set_value("Cost Calculator")
        app.run()
        self.assertEqual(app.query_params.get("page"), "Cost Calculator")

    def test_invalid_query_param_falls_back_to_home(self):
        isolate_state_file()
        app = AppTest.from_file(APP_PATH, default_timeout=30)
        app.query_params["page"] = "Not A Real Page"
        app.run()
        self.assertEqual(len(app.exception), 0)
        # Falls back to Home; URL is corrected.
        titles = [t.value for t in app.title]
        self.assertTrue(any("FoodFounder" in t for t in titles))


class TestScrollReset(unittest.TestCase):
    """One-shot scroll-to-top script emitted only on real page changes."""

    @staticmethod
    def scroll_html(app):
        return [node for node in app.get("html") if "window.scrollTo" in node.proto.body]

    def test_no_scroll_script_on_first_load(self):
        app = build_app_test()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.scroll_html(app), [])

    def test_scroll_script_emitted_on_page_change(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(app.exception), 0)

        nodes = self.scroll_html(app)
        self.assertEqual(len(nodes), 1)
        self.assertIn("window.scrollTo(0, 0)", nodes[0].proto.body)
        self.assertTrue(nodes[0].proto.unsafe_allow_javascript)

    def test_scroll_script_body_targets_new_page(self):
        app = build_app_test()
        set_radio(app, "AI Guidance")
        nodes = self.scroll_html(app)
        self.assertEqual(len(nodes), 1)
        self.assertIn("nav:AI Guidance", nodes[0].proto.body)

    def test_scroll_script_not_emitted_on_followup_rerun(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(self.scroll_html(app)), 1)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.scroll_html(app), [])

    def test_scroll_script_not_emitted_on_mid_task_reruns(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        app.run()
        self.assertEqual(self.scroll_html(app), [])

        self.assertTrue(click_button(app, "Load banana chips example"))
        self.assertEqual(self.scroll_html(app), [])

        self.assertTrue(click_button(app, "Calculate costs"))
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.scroll_html(app), [])

    def test_scroll_script_emitted_again_on_second_page_change(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(self.scroll_html(app)), 1)
        app.run()
        self.assertEqual(self.scroll_html(app), [])

        set_radio(app, "AI Guidance")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(self.scroll_html(app)), 1)


if __name__ == "__main__":
    unittest.main()
