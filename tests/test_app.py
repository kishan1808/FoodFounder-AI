"""Automated UI smoke tests for app.py using Streamlit's AppTest framework."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def build_app_test():
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


if __name__ == "__main__":
    unittest.main()
