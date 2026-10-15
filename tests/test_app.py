"""Automated UI smoke tests for app.py using Streamlit's AppTest framework."""

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")

# A valid session id (>=16 chars, [A-Za-z0-9_-]) used by default so AppTest
# sessions behave like real post-bootstrap browser sessions.
TEST_SID = "apptest-session-000001"
OTHER_SID = "apptest-session-000002"


def isolate_sessions_dir():
    """Point the app's persistence at a fresh (empty) temp sessions dir."""
    path = tempfile.mkdtemp(prefix="ff_test_sessions_")
    os.environ["FOODFOUNDER_SESSIONS_DIR"] = path
    return path


def build_app_test(sid=TEST_SID, isolate=True):
    """Build and run an AppTest, with a valid sid by default.

    ``isolate=False`` keeps the previously configured FOODFOUNDER_SESSIONS_DIR
    so multiple AppTest instances can share files (refresh simulation).
    """
    if isolate:
        isolate_sessions_dir()
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    if sid is not None:
        app.query_params["sid"] = sid
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
        # The product development summary now lives on its own page, not
        # nested inside AI Guidance.
        self.assertNotIn("Product development summary", markdown_text)

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

        set_radio(app, "Product Development")
        self.assertEqual(len(app.exception), 0)
        titles = [element.value for element in app.title]
        self.assertTrue(any("Product Development" in title for title in titles))
        markdown_text = " ".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("Product development summary", markdown_text)
        self.assertIn("Banana Chips", markdown_text)
        download_labels = [button.label for button in app.download_button]
        self.assertTrue(any("Download" in label for label in download_labels))


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
        set_radio(app, "Home")
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
        set_radio(app, "Home")
        self.assertEqual(app.session_state["product"]["batch_size"], 7.5)
        self.assertEqual(app.session_state["product"]["name"], "Chili Pickle")

    def test_ingredient_rows_survive_navigation_via_session(self):
        app = build_app_test()
        self._save_product(app)
        set_radio(app, "Cost Calculator")
        # The data editor's current state is captured into session_state.
        self.assertIn("ingredients_df", app.session_state)
        rows_before = app.session_state["ingredients_df"].copy()
        set_radio(app, "Home")
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
        set_radio(app, "Home")
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

    def test_state_restored_in_fresh_session_same_sid(self):
        """Simulate a browser refresh: new AppTest, same sid, same files."""
        isolate_sessions_dir()
        app = build_app_test(sid=TEST_SID, isolate=False)
        self._save_product(app)
        set_radio(app, "Cost Calculator")
        click_button(app, "Calculate costs")
        expected_total = app.session_state["cost_result"].total_production_cost
        expected_name = app.session_state["product"]["name"]

        # New AppTest instance, same sid = browser refresh of the same tab.
        app2 = build_app_test(sid=TEST_SID, isolate=False)
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

        isolate_sessions_dir()
        app = build_app_test(sid=TEST_SID, isolate=False)
        set_radio(app, "AI Guidance")
        calls = []
        with mock.patch("services.ai_assistant.chat", ok_chat_factory(calls, "Use foil pouches.")):
            app.chat_input[0].set_value("How do I store chips?")
            app.run()
        history_before = list(app.session_state["chat_history"])
        self.assertGreaterEqual(len(history_before), 2)

        app2 = build_app_test(sid=TEST_SID, isolate=False)
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

    def test_malformed_session_file_ignored_safely(self):
        sessions_dir = isolate_sessions_dir()
        bad_path = Path(sessions_dir) / f"{TEST_SID}.json"
        bad_path.write_text("{this is not valid json", encoding="utf-8")
        app = build_app_test(sid=TEST_SID, isolate=False)
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn("product", app.session_state)

    def test_empty_startup_without_saved_session(self):
        isolate_sessions_dir()
        app = build_app_test()
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn("product", app.session_state)
        self.assertNotIn("cost_result", app.session_state)


class TestSessionBootstrap(unittest.TestCase):
    """New browser sessions get a sid via one inline st.html script + replace()."""

    @staticmethod
    def bootstrap_html(app):
        """st.html nodes that contain the sid bootstrap script."""
        return [
            node
            for node in app.get("html")
            if "ff_sid" in str(node.value) and "sessionStorage" in str(node.value)
        ]

    def test_bootstrap_emitted_when_sid_missing(self):
        app = build_app_test(sid=None)  # fresh session, no ?sid= in URL
        self.assertEqual(len(app.exception), 0)
        nodes = self.bootstrap_html(app)
        self.assertEqual(len(nodes), 1)
        body = str(nodes[0].value)
        self.assertIn('sessionStorage.getItem("ff_sid")', body)
        self.assertIn("crypto.randomUUID", body)
        self.assertIn("loc.replace", body)
        self.assertIn('params.set("sid", sid)', body)
        # Must run in the main document, not a sandboxed iframe (which
        # blocks top-level navigation in Chrome).
        self.assertIn("<script>", body)
        self.assertEqual(len(app.get("iframe")), 0)

    def test_bootstrap_emitted_when_sid_invalid(self):
        for bad_sid in ("short", "bad sid!", "a" * 65, "../evil"):
            app = build_app_test(sid=bad_sid)
            self.assertEqual(len(app.exception), 0, f"sid={bad_sid!r}")
            self.assertEqual(len(self.bootstrap_html(app)), 1, f"sid={bad_sid!r}")

    def test_no_bootstrap_for_valid_sid(self):
        app = build_app_test(sid=TEST_SID)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.bootstrap_html(app), [])

    def test_pre_bootstrap_run_does_not_save_anything(self):
        sessions_dir = isolate_sessions_dir()
        app = build_app_test(sid=None)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(list(Path(sessions_dir).glob("*.json")), [])

    def test_sid_preserved_when_navigating(self):
        app = build_app_test(sid=TEST_SID)
        set_radio(app, "Cost Calculator")
        self.assertEqual(app.query_params.get("sid"), TEST_SID)
        set_radio(app, "AI Guidance")
        self.assertEqual(app.query_params.get("sid"), TEST_SID)


class TestSessionIsolation(unittest.TestCase):
    """Two different sids never read or overwrite each other's data."""

    def _save_product(self, app, name):
        app.text_input[0].set_value(name)
        for button in app.button:
            if button.label == "Start":
                button.click()
                app.run()
                break

    def test_second_session_starts_fresh(self):
        sessions_dir = isolate_sessions_dir()
        app_a = build_app_test(sid=TEST_SID, isolate=False)
        self._save_product(app_a, "SessionA Product")
        self.assertEqual(app_a.session_state["product"]["name"], "SessionA Product")

        # Different sid = a genuinely different browser session (new tab).
        app_b = build_app_test(sid=OTHER_SID, isolate=False)
        self.assertEqual(len(app_b.exception), 0)
        self.assertNotIn("product", app_b.session_state)
        # Session A's file is still on disk, written under its own sid.
        self.assertTrue((Path(sessions_dir) / f"{TEST_SID}.json").exists())

    def test_sessions_do_not_overwrite_each_other(self):
        isolate_sessions_dir()
        app_a = build_app_test(sid=TEST_SID, isolate=False)
        self._save_product(app_a, "SessionA Product")

        app_b = build_app_test(sid=OTHER_SID, isolate=False)
        self._save_product(app_b, "SessionB Product")
        self.assertEqual(app_b.session_state["product"]["name"], "SessionB Product")

        # Reload session A: still its own data, not B's.
        app_a2 = build_app_test(sid=TEST_SID, isolate=False)
        self.assertEqual(app_a2.session_state["product"]["name"], "SessionA Product")

        app_b2 = build_app_test(sid=OTHER_SID, isolate=False)
        self.assertEqual(app_b2.session_state["product"]["name"], "SessionB Product")

    def test_invalid_sid_session_cannot_read_other_sessions(self):
        isolate_sessions_dir()
        app_a = build_app_test(sid=TEST_SID, isolate=False)
        self._save_product(app_a, "SessionA Product")

        app_bad = build_app_test(sid="short")
        self.assertNotIn("product", app_bad.session_state)


class TestNavigation(unittest.TestCase):
    """Page selection via URL query parameter."""

    def test_page_restored_from_query_params(self):
        isolate_sessions_dir()
        app = AppTest.from_file(APP_PATH, default_timeout=30)
        app.query_params["sid"] = TEST_SID
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
        isolate_sessions_dir()
        app = AppTest.from_file(APP_PATH, default_timeout=30)
        app.query_params["sid"] = TEST_SID
        app.query_params["page"] = "Not A Real Page"
        app.run()
        self.assertEqual(len(app.exception), 0)
        # Falls back to Home; URL is corrected.
        titles = [t.value for t in app.title]
        self.assertTrue(any("FoodFounder" in t for t in titles))

    def test_sidebar_radio_lists_four_pages_in_order(self):
        app = build_app_test()
        self.assertEqual(len(app.sidebar.radio), 1)
        self.assertEqual(
            app.sidebar.radio[0].options,
            ["Home", "Cost Calculator", "AI Guidance", "Product Development"],
        )

    def test_product_development_is_a_separate_page(self):
        app = build_app_test()
        set_radio(app, "AI Guidance")
        self.assertEqual(app.query_params.get("page"), "AI Guidance")
        set_radio(app, "Product Development")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.query_params.get("page"), "Product Development")
        titles = [t.value for t in app.title]
        self.assertTrue(any("Product Development" in t for t in titles))
        self.assertFalse(any("AI Guidance" in t for t in titles))


class TestProductDevelopmentPage(unittest.TestCase):
    """The Product Development page owns the summary block."""

    def test_page_renders_with_downloads_without_any_data(self):
        app = build_app_test()
        set_radio(app, "Product Development")
        self.assertEqual(len(app.exception), 0)
        titles = [element.value for element in app.title]
        self.assertTrue(any("Product Development" in title for title in titles))
        markdown_text = " ".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("Product development summary", markdown_text)
        download_labels = [button.label for button in app.download_button]
        self.assertTrue(any("Download" in label for label in download_labels))
        # Guidance prompts when data is missing.
        info_text = " ".join(str(info.value) for info in app.info)
        self.assertIn("Home page", info_text)
        self.assertIn("Cost Calculator", info_text)

    def test_summary_includes_product_and_cost(self):
        app = build_app_test()
        app.text_input[0].set_value("Banana Chips")
        for button in app.button:
            if button.label == "Start":
                button.click()
                app.run()
                break
        set_radio(app, "Cost Calculator")
        click_button(app, "Calculate costs")
        set_radio(app, "Product Development")
        markdown_text = " ".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("Banana Chips", markdown_text)

    def test_sid_preserved_when_navigating_to_product_development(self):
        app = build_app_test(sid=TEST_SID)
        set_radio(app, "Product Development")
        self.assertEqual(app.query_params.get("sid"), TEST_SID)
        self.assertEqual(app.query_params.get("page"), "Product Development")

    def test_summary_downloads_still_available_on_calculator(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        click_button(app, "Calculate costs")
        download_labels = [button.label for button in app.download_button]
        self.assertTrue(any("Download" in label for label in download_labels))


class TestThemeToggle(unittest.TestCase):
    """Sidebar Light/Dark toggle drives a per-run CSS block; data survives."""

    @staticmethod
    def theme_mode(app):
        for node in app.markdown:
            body = str(node.value)
            if 'id="ff-theme"' in body:
                if 'data-mode="dark"' in body:
                    return "dark"
                if 'data-mode="light"' in body:
                    return "light"
        return None

    @staticmethod
    def theme_css(app):
        return " ".join(
            str(node.value) for node in app.markdown
            if 'id="ff-theme"' in str(node.value)
        )

    def test_toggle_present_below_nav_options(self):
        app = build_app_test()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.sidebar.toggle), 1)
        self.assertEqual(app.sidebar.toggle[0].label, "🌙 Dark mode")
        self.assertEqual(
            app.sidebar.radio[0].options,
            ["Home", "Cost Calculator", "AI Guidance", "Product Development"],
        )

    def test_default_theme_is_light(self):
        app = build_app_test()
        self.assertEqual(self.theme_mode(app), "light")

    def test_dark_mode_css_applied_and_data_preserved(self):
        app = build_app_test()
        app.text_input[0].set_value("Theme Test Chips")
        for button in app.button:
            if button.label == "Start":
                button.click()
                app.run()
                break
        app.sidebar.toggle[0].set_value(True)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.theme_mode(app), "dark")
        self.assertEqual(app.session_state["product"]["name"], "Theme Test Chips")
        css = self.theme_css(app)
        for marker in (
            "--background-color", "--primary-color", "--secondary-background-color",
            "stChatMessage", "stMetric", "stDataFrame", "stExpander",
            "stChatInput", "stButton",
        ):
            self.assertIn(marker, css)
        # Green accent: lighter green in dark mode, deeper green in light.
        self.assertIn("#66bb6a", css)
        light_app = build_app_test()
        self.assertIn("#2e7d32", self.theme_css(light_app))

    def test_theme_survives_navigation(self):
        app = build_app_test()
        app.sidebar.toggle[0].set_value(True)
        app.run()
        set_radio(app, "AI Guidance")
        self.assertEqual(self.theme_mode(app), "dark")
        set_radio(app, "Cost Calculator")
        self.assertEqual(self.theme_mode(app), "dark")
        set_radio(app, "Home")
        self.assertEqual(self.theme_mode(app), "dark")

    def test_theme_toggle_does_not_emit_scroll_iframe(self):
        """Toggling the theme must not trigger the page-change scroll script."""
        app = build_app_test()
        set_radio(app, "AI Guidance")
        app.sidebar.toggle[0].set_value(True)
        app.run()
        self.assertEqual(len(app.exception), 0)
        scroll_iframes = [
            node for node in app.get("iframe")
            if "section.stMain" in node.proto.srcdoc
        ]
        self.assertEqual(scroll_iframes, [])

    def test_light_mode_restored_when_toggled_back(self):
        app = build_app_test()
        app.sidebar.toggle[0].set_value(True)
        app.run()
        self.assertEqual(self.theme_mode(app), "dark")
        app.sidebar.toggle[0].set_value(False)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.theme_mode(app), "light")


class TestScrollReset(unittest.TestCase):
    """One-shot scroll-to-top iframe emitted only on real page changes.

    The script scrolls section[data-testid="stMain"] in the parent document
    (the element that actually has overflow:auto in Streamlit 1.65; the
    window itself never scrolls, which is why window.scrollTo alone failed
    in the browser).
    """

    @staticmethod
    def scroll_iframes(app):
        return [node for node in app.get("iframe") if "section.stMain" in node.proto.srcdoc]

    def test_no_scroll_iframe_on_first_load(self):
        app = build_app_test()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.scroll_iframes(app), [])

    def test_first_load_on_ai_guidance_emits_mount_guard(self):
        """A first run landing directly on AI Guidance (?page= URL, browser
        refresh) must emit the AI mount guard: the page-change gate never
        fires for it, so Streamlit's chat-input scroll would otherwise
        land the page at the bottom, unopposed."""
        isolate_sessions_dir()
        app = AppTest.from_file(APP_PATH, default_timeout=30)
        app.query_params["sid"] = TEST_SID
        app.query_params["page"] = "AI Guidance"
        app.run()
        self.assertEqual(len(app.exception), 0)
        nodes = self.scroll_iframes(app)
        self.assertEqual(len(nodes), 1)
        srcdoc = nodes[0].proto.srcdoc
        self.assertIn("ff-nav: AI Guidance", srcdoc)
        self.assertIn("pointerdown", srcdoc)
        self.assertIn("requestAnimationFrame", srcdoc)
        # One-shot: a plain rerun on the same page must not re-emit.
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.scroll_iframes(app), [])

    def test_scroll_iframe_emitted_on_page_change(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(app.exception), 0)

        nodes = self.scroll_iframes(app)
        self.assertEqual(len(nodes), 1)
        srcdoc = nodes[0].proto.srcdoc
        self.assertIn("w = window.parent", srcdoc)
        self.assertIn("w.scrollTo(0, 0)", srcdoc)
        # Stable selector first: Streamlit swaps the section's data-testid to
        # stAppScrollToBottomContainer when a bottom chat_input is present
        # (AI Guidance), so class-based selection must lead, with both
        # data-testid values as fallbacks.
        self.assertIn("section.stMain", srcdoc)
        self.assertIn('[data-testid="stMain"]', srcdoc)
        self.assertIn('[data-testid="stAppScrollToBottomContainer"]', srcdoc)
        self.assertIn("scrollTop = 0", srcdoc)
        # One-shot reset only: no interval loop that would fight the user's
        # scrolling on ordinary pages.
        self.assertIn("reset();", srcdoc)
        self.assertNotIn("setInterval", srcdoc)
        self.assertNotIn("setTimeout", srcdoc)

    def test_ai_guidance_traps_mount_scroll_not_a_loop(self):
        """AI Guidance: Streamlit's bundle scrolls the section to the bottom
        at mount (chat-input reveal). The script intercepts the section's
        scrollTop setter during the mount window so the bottom is never
        painted (no flicker), then removes itself — a single cleanup timeout,
        never a repeating scroll loop."""
        app = build_app_test()
        set_radio(app, "AI Guidance")
        nodes = self.scroll_iframes(app)
        self.assertEqual(len(nodes), 1)
        srcdoc = nodes[0].proto.srcdoc
        self.assertIn("Object.defineProperty", srcdoc)
        self.assertIn("scrollTop", srcdoc)
        self.assertIn("touched", srcdoc)
        # Cancels Streamlit's mount-time rAF scroll loop via its own
        # pointerdown listener, so the bottom is never painted (no flicker).
        self.assertIn("pointerdown", srcdoc)
        # rAF-chain kill: cancels the loop's next frame after the first
        # intercepted set attempt, so the loop cannot resume later.
        self.assertIn("requestAnimationFrame", srcdoc)
        self.assertIn("cancelAnimationFrame", srcdoc)
        self.assertIn("setTimeout(untrap, 1500)", srcdoc)
        self.assertNotIn("setInterval", srcdoc)
        self.assertNotIn("clearInterval", srcdoc)
        self.assertNotIn("resetBottom", srcdoc)

    def test_scroll_iframe_marks_new_page(self):
        app = build_app_test()
        set_radio(app, "AI Guidance")
        nodes = self.scroll_iframes(app)
        self.assertEqual(len(nodes), 1)
        self.assertIn("ff-nav: AI Guidance", nodes[0].proto.srcdoc)

    def test_scroll_iframe_not_emitted_on_followup_rerun(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(self.scroll_iframes(app)), 1)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.scroll_iframes(app), [])

    def test_scroll_iframe_not_emitted_on_mid_task_reruns(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        app.run()
        self.assertEqual(self.scroll_iframes(app), [])

        self.assertTrue(click_button(app, "Load banana chips example"))
        self.assertEqual(self.scroll_iframes(app), [])

        self.assertTrue(click_button(app, "Calculate costs"))
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.scroll_iframes(app), [])

    def test_scroll_iframe_emitted_again_on_second_page_change(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(self.scroll_iframes(app)), 1)
        app.run()
        self.assertEqual(self.scroll_iframes(app), [])

        set_radio(app, "AI Guidance")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(self.scroll_iframes(app)), 1)

    def test_scroll_iframe_emitted_on_nav_to_ai_guidance(self):
        app = build_app_test()
        set_radio(app, "AI Guidance")
        self.assertEqual(len(app.exception), 0)
        nodes = self.scroll_iframes(app)
        self.assertEqual(len(nodes), 1)
        self.assertIn("ff-nav: AI Guidance", nodes[0].proto.srcdoc)

    def test_scroll_iframe_emitted_on_nav_to_product_development(self):
        app = build_app_test()
        set_radio(app, "Cost Calculator")
        app.run()
        self.assertEqual(self.scroll_iframes(app), [])

        set_radio(app, "Product Development")
        self.assertEqual(len(app.exception), 0)
        nodes = self.scroll_iframes(app)
        self.assertEqual(len(nodes), 1)
        self.assertIn("ff-nav: Product Development", nodes[0].proto.srcdoc)

    def test_page_change_after_refresh_only_scrolls_once_per_change(self):
        """Refresh (new AppTest, same sid) must not emit a scroll iframe."""
        isolate_sessions_dir()
        app = build_app_test(sid=TEST_SID, isolate=False)
        set_radio(app, "Cost Calculator")
        self.assertEqual(len(self.scroll_iframes(app)), 1)

        app2 = AppTest.from_file(APP_PATH, default_timeout=30)  # simulated refresh
        app2.query_params["sid"] = TEST_SID
        app2.query_params["page"] = "Cost Calculator"  # URL carried over
        app2.run()
        self.assertEqual(len(app2.exception), 0)
        self.assertEqual(self.scroll_iframes(app2), [])
        # Page was preserved via the ?page= URL param.
        titles = [t.value for t in app2.title]
        self.assertTrue(any("Cost Calculator" in t for t in titles))
        set_radio(app2, "AI Guidance")
        self.assertEqual(len(self.scroll_iframes(app2)), 1)


if __name__ == "__main__":
    unittest.main()
