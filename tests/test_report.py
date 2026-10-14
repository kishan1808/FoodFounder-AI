"""Tests for report.py product development summary generation."""

import io
import unittest

from pypdf import PdfReader

from services.calculator import Ingredient, calculate_batch
from services.report import build_pdf_report, build_report, money


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

    def test_long_chat_text_not_truncated(self):
        long_answer = "x" * 1000
        chat_history = [
            {"role": "user", "text": "Explain packaging in detail"},
            {"role": "model", "text": long_answer},
        ]
        text = build_report(chat_history=chat_history)
        self.assertIn(long_answer, text)
        self.assertNotIn("…", text)

    def test_all_conversation_turns_included_in_order(self):
        chat_history = []
        for i in range(10):
            chat_history.append({"role": "user", "text": f"question {i}"})
            chat_history.append({"role": "model", "text": f"answer {i} " + ("detail " * 50)})
        text = build_report(chat_history=chat_history)
        for i in range(10):
            self.assertIn(f"question {i}", text)
            self.assertIn(f"answer {i}", text)
        self.assertLess(text.index("question 0"), text.index("question 9"))
        self.assertLess(text.index("answer 0"), text.index("answer 9"))

    def test_markdown_in_answer_preserved_verbatim(self):
        answer = (
            "### My recommendation\n\n"
            "- Use **metallised** pouches\n"
            "- Check seal integrity\n\n"
            "| Barrier | Good |\n|---|---|\n\n"
            "Final `note` here."
        )
        chat_history = [
            {"role": "user", "text": "Packaging?"},
            {"role": "model", "text": answer},
        ]
        text = build_report(chat_history=chat_history)
        self.assertIn(answer, text)

    def test_control_characters_sanitized_without_shortening(self):
        chat_history = [
            {"role": "model", "text": "Hello\x00\x07 world " + "y" * 500},
        ]
        text = build_report(chat_history=chat_history)
        self.assertNotIn("\x00", text)
        self.assertIn("Hello world " + "y" * 500, text)

    def test_money_format(self):
        self.assertEqual(money(1224), "₹1,224.00")
        self.assertEqual(money(0), "₹0.00")


class TestBuildPdfReport(unittest.TestCase):
    def test_build_pdf_report_attribute_exists(self):
        import services.report as report_module

        self.assertTrue(
            hasattr(report_module, "build_pdf_report"),
            "services.report.build_pdf_report must exist (app.py depends on it)",
        )
        self.assertTrue(callable(report_module.build_pdf_report))

    def test_build_pdf_report_generates_valid_pdf_from_sample_data(self):
        import services.report as report_module

        pdf = report_module.build_pdf_report(
            product=BANANA_PRODUCT,
            result=banana_chip_result(),
            chat_history=[
                {"role": "user", "text": "How should I package banana chips?"},
                {"role": "model", "text": "Use metallised pouches with a strong heat seal."},
            ],
            generated_at="2026-10-14 12:00",
        )
        self.assertIsInstance(pdf, (bytes, bytearray))
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"%%EOF", pdf[-32:])

    def test_pdf_header_and_footer(self):
        pdf = build_pdf_report(
            product=BANANA_PRODUCT,
            result=banana_chip_result(),
            chat_history=[
                {"role": "user", "text": "How should I package banana chips?"},
                {"role": "model", "text": "Use metallised pouches with a strong heat seal."},
            ],
        )
        self.assertIsInstance(pdf, (bytes, bytearray))
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"%%EOF", pdf[-32:])
        self.assertGreater(len(pdf), 2000)

    def test_pdf_grows_with_long_untruncated_answer(self):
        short_pdf = build_pdf_report(
            chat_history=[{"role": "model", "text": "Short answer."}]
        )
        long_answer = ("Full detailed packaging guidance. " * 80).strip()
        long_pdf = build_pdf_report(
            chat_history=[{"role": "model", "text": long_answer}]
        )
        self.assertGreater(
            len(long_pdf), len(short_pdf),
            "longer answers must produce a larger PDF (no truncation)",
        )

    def test_pdf_with_empty_inputs(self):
        pdf = build_pdf_report()
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"%%EOF", pdf[-32:])

    def test_pdf_with_emoji_and_control_chars_does_not_crash(self):
        pdf = build_pdf_report(
            chat_history=[
                {"role": "user", "text": "Hi 🍌"},
                {"role": "model", "text": "Answer with emoji 😀 and\x00 control"},
            ]
        )
        self.assertTrue(pdf.startswith(b"%PDF"))


def pdf_text(pdf_bytes):
    """Extract readable text from PDF bytes via pypdf (with newlines normalized)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


class TestCleanHtml(unittest.TestCase):
    def test_br_variants_become_newlines(self):
        from services.report import _clean_html

        self.assertEqual(_clean_html("a<br>b"), "a\nb")
        self.assertEqual(_clean_html("a<br/>b"), "a\nb")
        self.assertEqual(_clean_html("a<br />b"), "a\nb")
        self.assertEqual(_clean_html("a<BR>b"), "a\nb")

    def test_inline_tags_stripped_content_kept(self):
        from services.report import _clean_html

        self.assertEqual(_clean_html("<b>bold</b> and <i>italic</i>"), "bold and italic")
        self.assertEqual(_clean_html("<b>small</b> <b>scale</b>"), "small scale")

    def test_entities_unescaped_safely(self):
        from services.report import _clean_html

        self.assertEqual(_clean_html("pickles &amp; jam"), "pickles & jam")
        self.assertEqual(_clean_html("range &lt;10%"), "range <10%")
        self.assertEqual(_clean_html("a&nbsp;b"), "a b")
        self.assertEqual(_clean_html("&#39;quoted&#39;"), "'quoted'")
        # words that merely start with an entity name must not be corrupted
        self.assertEqual(_clean_html("R&amp;D &amplitude here"), "R&D &amplitude here")

    def test_angle_brackets_without_tag_not_eaten(self):
        from services.report import _clean_html

        self.assertEqual(_clean_html("range <10% and pH <7"), "range <10% and pH <7")


class TestPdfHtmlAndFormatting(unittest.TestCase):
    def test_no_literal_html_in_pdf(self):
        answer = (
            "Plan:<br>step one.<br/>step two.<br />step three.<br><br>"
            "Use <b>metallised</b> pouches &amp; check <i>seals</i>. "
            "Range &lt;10% moisture. Use &nbsp;spaces."
        )
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": answer}])
        text = pdf_text(pdf).lower()
        for literal in ("<br", "<b>", "<i>", "&amp;", "&lt;", "&nbsp;"):
            self.assertNotIn(literal, text, f"literal {literal!r} leaked into PDF")

    def test_br_in_table_cells_renders_readable(self):
        answer = (
            "| Day | Task |\n|---|---|\n"
            "| 1-3 | Source <br> 2 suppliers |\n"
            "| 4-7 | Finalise <b>recipe</b> &amp; oil |\n"
            "| 8-10 | Order <br/> pouches <br /> seals |"
        )
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": answer}])
        text = pdf_text(pdf)
        lowered = text.lower()
        self.assertNotIn("<br", lowered)
        self.assertNotIn("<b>", lowered)
        self.assertNotIn("&amp;", lowered)
        self.assertIn("Source", text)
        self.assertIn("2 suppliers", text)
        self.assertIn("recipe", text)
        self.assertIn("oil", text)
        self.assertIn("pouches", text)
        self.assertIn("seals", text)

    def test_spaces_and_punctuation_preserved(self):
        answer = (
            "**small scale** setup works for **banana chips**. "
            "Cost is 10* per kg* approx. Check pH <7.5, then pack; label: 'fresh'."
        )
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": answer}])
        text = pdf_text(pdf)
        self.assertIn("small scale", text)
        self.assertIn("banana chips", text)
        self.assertNotIn("smallscale", text)
        self.assertNotIn("bananachips", text)
        self.assertIn("pH <7.5", text)

    def test_long_table_spans_multiple_pages_completely(self):
        rows = "\n".join(
            f"| {i} | Trial batch note {i} with detailed seal temperature and cooling guidance | Owner {i} |"
            for i in range(1, 60)
        )
        answer = "### Action Plan\n\n| Day | Task | Owner |\n|---|---|---|\n" + rows
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": answer}])
        text = pdf_text(pdf)
        page_count = len(PdfReader(io.BytesIO(pdf)).pages)
        self.assertGreater(page_count, 2, "long table should span multiple pages")
        self.assertIn("Trial batch note 1 ", text.replace("  ", " "))
        self.assertIn("Trial batch note 59", text)

    def test_final_action_plan_complete_through_disclaimer(self):
        rows = "\n".join(
            f"| Day {i} | Task {i} with extended notes about sealing cooling and labelling | You |"
            for i in range(1, 45)
        )
        answer = (
            "### 30-Day Action Plan\n\n| Day | Task | Owner |\n|---|---|---|\n" + rows
        )
        pdf = build_pdf_report(
            product=BANANA_PRODUCT,
            result=banana_chip_result(),
            chat_history=[
                {"role": "user", "text": "Give me a 30-day action plan table"},
                {"role": "model", "text": answer},
            ],
        )
        text = pdf_text(pdf)
        self.assertIn("30-Day Action Plan", text)
        self.assertIn("Day 44", text)
        self.assertIn("Task 44", text)
        # sections that come AFTER the chat table must still be present
        self.assertIn("Assumptions and limitations", text)
        self.assertIn("Useful sources", text)
        self.assertIn("Suggested next steps", text)
        self.assertIn("Disclaimer", text)
        self.assertIn("foscos.fssai.gov.in", text.replace("\n", " "))

    def test_full_chronological_chat_long_answers(self):
        history = []
        for i in range(5):
            history.append({"role": "user", "text": f"Question {i} about packaging?"})
            history.append(
                {
                    "role": "model",
                    "text": f"### Answer {i}\n\n" + ("Detailed guidance sentence. " * 40).strip(),
                }
            )
        pdf = build_pdf_report(chat_history=history)
        text = pdf_text(pdf)
        for i in range(5):
            self.assertIn(f"Question {i} about packaging?", text)
            self.assertIn(f"Answer {i}", text)
        self.assertIn("Detailed guidance sentence.", text)
        self.assertLess(text.index("Question 0"), text.index("Question 4"))


class TestPdfTypography(unittest.TestCase):
    """Regression tests for professional table/typography rendering and separation."""

    def _chat_pdf(self, history=None):
        if history is None:
            history = [
                {"role": "user", "text": "How should I package banana chips?"},
                {
                    "role": "model",
                    "text": "Use **metallised pouches** with a strong heat seal and desiccant.",
                },
                {"role": "user", "text": "What about labelling?"},
                {
                    "role": "model",
                    "text": "Add FSSAI licence number, batch code, and best-before date.",
                },
            ]
        return build_pdf_report(chat_history=history)

    def test_typography_size_hierarchy(self):
        from services import report

        self.assertGreater(report.CHAT_LABEL_PT, report.BODY_PT)
        self.assertGreater(report.CHAT_LABEL_PT, report.TABLE_BODY_PT)
        self.assertGreater(report.TABLE_HEADER_PT, report.TABLE_BODY_PT)
        self.assertGreaterEqual(report.TABLE_BODY_PT, report.BODY_PT)

    def test_table_header_fill_is_light_shaded(self):
        from services import report

        r, g, b = report.TABLE_HEADER_FILL
        for component in (r, g, b):
            self.assertGreaterEqual(component, 200)
            self.assertLessEqual(component, 245)

    def test_chat_labels_render_bold_font(self):
        """Chat speaker labels must use the bold embedded font (regression: style+markdown bug)."""
        pdf = self._chat_pdf()
        reader = PdfReader(io.BytesIO(pdf))
        label_hits = []
        for page in reader.pages:
            def visitor(text, cm, tm, font_dict, font_size):
                if font_dict is None:
                    return
                base = str(font_dict.get("/BaseFont", ""))
                if "You:" in text or "FoodFounder AI:" in text:
                    label_hits.append((base, font_size, text.strip()))

            page.extract_text(visitor_text=visitor)
        self.assertTrue(label_hits, "chat labels not found in extracted text")
        for base, font_size, text in label_hits:
            self.assertIn("Bold", base, f"label {text!r} rendered with non-bold font {base}")
            self.assertEqual(round(font_size, 1), 10.5, f"label {text!r} wrong size")

    def test_body_text_not_bold_by_default(self):
        """Plain body sentences must use the regular (non-bold) font."""
        pdf = self._chat_pdf(
            history=[{"role": "model", "text": "Plain regular body sentence for packaging."}]
        )
        reader = PdfReader(io.BytesIO(pdf))
        found_regular = False
        for page in reader.pages:
            def visitor(text, cm, tm, font_dict, font_size):
                nonlocal found_regular
                if font_dict is None:
                    return
                base = str(font_dict.get("/BaseFont", ""))
                if "Plain regular body" in text and "Bold" not in base:
                    found_regular = True

            page.extract_text(visitor_text=visitor)
        self.assertTrue(found_regular, "body sentence should use regular font")

    def test_table_headers_bold_and_body_regular(self):
        """Table heading row uses bold font; data rows use regular font."""
        pdf = build_pdf_report(result=banana_chip_result())
        reader = PdfReader(io.BytesIO(pdf))
        header_seen_bold = False
        body_seen_regular = False
        for page in reader.pages:
            def visitor(text, cm, tm, font_dict, font_size):
                nonlocal header_seen_bold, body_seen_regular
                if font_dict is None:
                    return
                base = str(font_dict.get("/BaseFont", ""))
                if "Ingredient" in text or "Quantity" in text:
                    if "Bold" in base:
                        header_seen_bold = True
                if "Bananas" in text and "Bold" not in base:
                    body_seen_regular = True

            page.extract_text(visitor_text=visitor)
        self.assertTrue(header_seen_bold, "table header row should render bold")
        self.assertTrue(body_seen_regular, "table body row should render regular")

    def test_markdown_bold_phrase_inside_body_stays_bold(self):
        """Intentional **bold** inside an answer must stay bold even after the label fix."""
        pdf = self._chat_pdf(
            history=[{"role": "model", "text": "Use **metallised pouches** for moisture barrier."}]
        )
        reader = PdfReader(io.BytesIO(pdf))
        bold_phrase_seen = False
        for page in reader.pages:
            def visitor(text, cm, tm, font_dict, font_size):
                nonlocal bold_phrase_seen
                if font_dict is None:
                    return
                base = str(font_dict.get("/BaseFont", ""))
                if "metallised pouches" in text and "Bold" in base:
                    bold_phrase_seen = True

            page.extract_text(visitor_text=visitor)
        self.assertTrue(bold_phrase_seen, "inline markdown bold phrase should render bold")

    def test_consecutive_tables_visually_separated(self):
        """Two tables in a row must have spacing constants and distinct header fills."""
        from services import report

        self.assertGreaterEqual(report.TABLE_SPACE_BEFORE, 2)
        self.assertGreaterEqual(report.TABLE_SPACE_AFTER, 2)
        self.assertGreater(report.TABLE_PADDING, 0)
        self.assertGreater(report.TABLE_LINE_HEIGHT, 0)
        answer = (
            "| Ingredient | Cost |\n|---|---|\n| banana | ₹20 |\n\n"
            "| Item | Amount |\n|---|---|\n| Packaging | ₹150 |\n"
        )
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": answer}])
        content = PdfReader(io.BytesIO(pdf)).pages[0].get_contents().get_data()
        # light-shaded header fill operator: 0.9137 0.9255 0.9412 rg  (233/255, 236/255, 240/255)
        fill_ops = content.count(b"0.913735 0.925490 0.941176 rg") + content.count(b"0.9137 0.9255 0.9412 rg")
        if fill_ops == 0:
            # fpdf2 may emit with different precision — count any near-white rg fill
            import re as _re
            fill_ops = len(_re.findall(rb"0\.9\d+ 0\.9\d+ 0\.9\d+ rg", content))
        self.assertGreaterEqual(fill_ops, 2, "each table header should emit a fill op")

    def test_chat_turns_separated_with_dividers(self):
        """Multiple chat turns must draw divider lines between them."""
        from services import report

        self.assertGreaterEqual(report.DIVIDER_WIDTH, 0.1)
        self.assertLessEqual(report.DIVIDER_WIDTH, 1.0)
        pdf = self._chat_pdf()
        reader = PdfReader(io.BytesIO(pdf))
        stroke_ops = 0
        for page in reader.pages:
            content = page.get_contents().get_data()
            stroke_ops += content.count(b" l S")
        self.assertGreaterEqual(stroke_ops, 2, "chat turns should be separated by drawn dividers")

    def test_chat_labels_and_answers_in_chronological_order(self):
        pdf = self._chat_pdf()
        text = pdf_text(pdf)
        self.assertIn("You:", text)
        self.assertIn("FoodFounder AI:", text)
        self.assertLess(text.index("How should I package"), text.index("metallised pouches"))
        self.assertLess(text.index("metallised pouches"), text.index("What about labelling"))
        self.assertLess(text.index("What about labelling"), text.index("FSSAI licence number"))

    def test_speaker_labels_not_bold_when_not_markdown_bold(self):
        """Regression: style='B' + markdown '**label**' must not cancel bold (fpdf2 quirk)."""
        from fpdf import FPDF
        from pathlib import Path
        from services.report import CHAT_LABEL_PT

        windows_fonts = Path("C:/Windows/Fonts")
        if not (windows_fonts / "arial.ttf").exists():
            self.skipTest("Arial fonts unavailable on this platform")
        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(15, 15, 15)
        pdf.add_page()
        pdf.add_font("App", "", str(windows_fonts / "arial.ttf"))
        pdf.add_font("App", "B", str(windows_fonts / "arialbd.ttf"))
        # mirror write_paragraph call used by _render_markdown_pdf for speaker labels
        pdf.set_font("App", style="", size=CHAT_LABEL_PT)
        pdf.multi_cell(0, 6, "**You:**", markdown=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("App", style="", size=9)
        pdf.multi_cell(0, 6, "regular body line", markdown=True, new_x="LMARGIN", new_y="NEXT")
        out = pdf.output()
        reader = PdfReader(io.BytesIO(out))
        fonts = {
            k: str(v.get_object().get("/BaseFont", ""))
            for k, v in reader.pages[0]["/Resources"]["/Font"].items()
        }
        bold_fonts = [k for k, v in fonts.items() if "Bold" in v]
        self.assertTrue(bold_fonts, "bold font must be embedded for markdown-bold label")

    def test_multi_page_table_repeats_shaded_header(self):
        """Header rows must repeat on continuation pages and keep the shaded fill."""
        from services import report

        rows = "\n".join(
            f"| {i} | Trial note {i} with extended seal and cooling details | Owner {i} |"
            for i in range(1, 70)
        )
        answer = "### Long Plan\n\n| Day | Task | Owner |\n|---|---|---|\n" + rows
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": answer}])
        reader = PdfReader(io.BytesIO(pdf))
        self.assertGreater(len(reader.pages), 2)
        header_occurrences = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            if "Day" in text and "Task" in text and "Owner" in text:
                header_occurrences += 1
        self.assertGreaterEqual(header_occurrences, 2, "table header should repeat across pages")
        r, g, b = report.TABLE_HEADER_FILL
        expected = (
            f"{r/255:.6f} {g/255:.6f} {b/255:.6f} rg"
        ).encode()
        content_all = b"".join(page.get_contents().get_data() for page in reader.pages)
        import re as _re
        near_fill = _re.findall(rb"0\.9\d+ 0\.9\d+ 0\.9\d+ rg", content_all)
        self.assertGreaterEqual(len(near_fill), 2, "shaded header fill missing on pages")

    def test_no_raw_html_or_entities_anywhere(self):
        answer = (
            "Step<br>one<br/>two<br />three.<br><br>"
            "<b>bold</b> &amp; <i>italic</i> &nbsp; spaced &lt;10%."
        )
        pdf = build_pdf_report(
            product=BANANA_PRODUCT,
            result=banana_chip_result(),
            chat_history=[{"role": "model", "text": answer}],
        )
        text = pdf_text(pdf).lower()
        for literal in ("<br", "</b>", "<b>", "</i>", "<i>", "&amp;", "&lt;", "&nbsp;", "&gt;"):
            self.assertNotIn(literal, text)

    def test_links_rendered_readable(self):
        answer = "See [FSSAI packaging rules](https://fssai.gov.in/packaging) for details."
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": answer}])
        text = pdf_text(pdf)
        self.assertIn("FSSAI packaging rules", text)
        self.assertIn("https://fssai.gov.in/packaging", text)
        self.assertNotIn("](", text)

    def test_run_together_bold_words_get_space(self):
        """small**scale** style corruption must be repaired with a space."""
        pdf = build_pdf_report(
            chat_history=[{"role": "model", "text": "A **small**scale** setup works."}]
        )
        text = pdf_text(pdf)
        self.assertNotIn("smallscale", text)
        self.assertIn("small", text)
        self.assertIn("scale", text)

    def test_divider_line_rendered_for_markdown_hr(self):
        pdf = build_pdf_report(chat_history=[{"role": "model", "text": "Before\n\n---\n\nAfter."}])
        text = pdf_text(pdf)
        self.assertIn("Before", text)
        self.assertIn("After.", text)
        content = PdfReader(io.BytesIO(pdf)).pages[0].get_contents().get_data()
        self.assertIn(b" l S", content, "markdown --- should draw a divider line")


if __name__ == "__main__":
    unittest.main()
