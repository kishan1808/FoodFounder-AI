"""Builds the downloadable product development summary (Markdown + PDF).

Pure Python — no Streamlit — so it can be unit-tested and reused.
"""

import html
import re
from datetime import datetime
from pathlib import Path

from services import guidance

MONEY_FORMAT = "₹{:,.2f}"

_WINDOWS_FONTS = Path("C:/Windows/Fonts")

# Typography hierarchy (points)
BODY_PT = 9
TABLE_BODY_PT = 9.5
TABLE_HEADER_PT = 10
CHAT_LABEL_PT = 10.5

# Table layout
TABLE_HEADER_FILL = (233, 236, 240)
TABLE_SPACE_BEFORE = 4
TABLE_SPACE_AFTER = 5
TABLE_PADDING = 1.6
TABLE_LINE_HEIGHT = 5

# Chat turn divider
DIVIDER_COLOR = (205, 205, 205)
DIVIDER_WIDTH = 0.25


def money(value):
    return MONEY_FORMAT.format(value)


def _sanitize_text(text):
    """Remove control characters (except tab/newline) without shortening text."""
    cleaned = "".join(
        ch for ch in str(text) if ch in ("\n", "\t") or (ord(ch) >= 32 and ord(ch) != 127)
    )
    return cleaned


def _product_section(product):
    lines = ["## 1. Product details", ""]
    if product:
        lines.append(f"- **Product name:** {product.get('name', 'Not set')}")
        lines.append(f"- **Category:** {product.get('category', 'Not set')}")
        lines.append(
            f"- **Batch size:** {product.get('batch_size', 'Not set')} {product.get('batch_unit', '')}".rstrip()
        )
        budget = product.get("budget")
        if budget:
            lines.append(f"- **Approximate budget:** {money(budget)}")
    else:
        lines.append("- No product set on the Home page.")
    return "\n".join(lines)


def _ingredients_section(result):
    lines = ["## 2. Batch and ingredients", ""]
    if not result:
        lines.append("- No batch calculated yet.")
        return "\n".join(lines)

    lines.append(f"Batch: {result.batch_size:g} {result.batch_unit} → {result.saleable_packets} saleable packets")
    lines.append("")
    lines.append("| Ingredient | Quantity | Unit | Price/unit | Cost |")
    lines.append("|---|---:|---|---:|---:|")
    for ingredient in result.ingredients:
        lines.append(
            f"| {ingredient.name} | {ingredient.quantity:g} | {ingredient.unit} | "
            f"{money(ingredient.price_per_unit)} | {money(ingredient.cost)} |"
        )
    lines.append(f"| **Total ingredients** | | | | **{money(result.total_ingredient_cost)}** |")
    return "\n".join(lines)


def _cost_section(result):
    lines = ["## 3. Cost breakdown", ""]
    if not result:
        lines.append("- No batch calculated yet.")
        return "\n".join(lines)

    lines.append("| Item | Amount |")
    lines.append("|---|---:|")
    for name, cost in result.ingredient_costs:
        lines.append(f"| {name} | {money(cost)} |")
    lines.append(f"| Packaging | {money(result.packaging_cost)} |")
    lines.append(f"| Labour | {money(result.labour_cost)} |")
    lines.append(f"| Energy | {money(result.energy_cost)} |")
    lines.append(f"| Other expenses | {money(result.other_cost)} |")
    lines.append(f"| **TOTAL production cost** | **{money(result.total_production_cost)}** |")
    return "\n".join(lines)


def _economics_section(result):
    lines = ["## 4. Per-packet economics (estimates)", ""]
    if not result:
        lines.append("- No batch calculated yet.")
        return "\n".join(lines)

    margin = (
        f"{result.profit_margin_pct:.1f}%"
        if result.profit_margin_pct is not None
        else "Not applicable (selling price is 0)"
    )
    lines.append(f"- **Cost per packet:** {money(result.cost_per_packet)}")
    lines.append(f"- **Proposed selling price:** {money(result.selling_price)}")
    lines.append(f"- **Estimated profit per packet:** {money(result.profit_per_packet)}")
    lines.append(f"- **Estimated profit margin:** {margin}")
    lines.append(f"- **Estimated batch profit:** {money(result.batch_profit)}")
    return "\n".join(lines)


def _chat_section(chat_history):
    lines = ["## 6. AI recommendations (full chat)", ""]
    turns = [
        turn
        for turn in (chat_history or [])
        if isinstance(turn, dict) and str(turn.get("text") or "").strip()
    ]
    if not turns:
        lines.append("- No chat yet. Ask the assistant about packaging or processing.")
        return "\n".join(lines)

    for turn in turns:
        speaker = "You" if turn.get("role") == "user" else "FoodFounder AI"
        text = _sanitize_text(str(turn.get("text", "")).strip())
        lines.append(f"**{speaker}:**")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def build_report(product=None, result=None, chat_history=None, generated_at=None):
    """Return the full product development summary as a Markdown string."""
    timestamp = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = [
        "# FoodFounder AI — Product Development Summary",
        f"Generated: {timestamp}",
        "",
        "> All figures are estimates for planning purposes only.",
        "",
        _product_section(product),
        "",
        _ingredients_section(result),
        "",
        _cost_section(result),
        "",
        _economics_section(result),
        "",
        "## 5. Packaging and process reminders",
        "",
        "- [ ] Moisture and oxygen barrier packaging discussed with a supplier",
        "- [ ] Seals tested for leaks; product cooled fully before packing",
        "- [ ] Batch records started (dates, settings, checks)",
        "- [ ] At least one documented trial batch before scaling up",
        "",
        "Full checklists are in the app under **AI Guidance**.",
        "",
        _chat_section(chat_history),
        "",
        "## 7. Assumptions and limitations",
        "",
        "- Ingredient cost = quantity used × price per unit, exactly as entered.",
        "- Included costs: ingredients, packaging, labour, energy, other (as entered).",
        "- Not included unless entered above: wastage/spoilage, GST/taxes, transport,",
        "  storage, marketplace commissions, retailer margins, marketing, licence fees,",
        "  and equipment depreciation.",
        "- AI-generated formulation ideas are preliminary starting points only;",
        "  they are not scientifically validated or lab-tested.",
        "- Verify prices, yields, labelling, and shelf life with suppliers, trials,",
        "  qualified experts, and official sources before selling.",
        "",
        "## 8. Useful sources",
        "",
        guidance.resources_as_markdown(),
        "",
        "## 9. Suggested next steps",
        "",
        "1. Run one small trial batch using the quantities in this summary.",
        "2. Record process settings, observations, and any waste.",
        "3. Re-check ingredient prices from at least two suppliers.",
        "4. Review FSSAI licensing, labelling, and hygiene requirements for your product.",
        "5. Adjust the selling price and re-calculate until the margin works for you.",
        "6. Consider lab testing before making safety, nutrition, or shelf-life claims.",
        "",
        "---",
        f"Disclaimer: {guidance.DISCLAIMER}",
    ]
    return "\n".join(sections)


_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_TABLE_SEPARATOR = re.compile(r"^\|[\s:\-|]+\|$")
_BR_PATTERN = re.compile(r"<br\b[^>]*>", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(
    r"</?(?:b|strong|i|em|u|p|div|span|ul|ol|li|tr|td|th|a|h[1-6]|code|pre|table)"
    r"(?:\s[^<>]*)?/?>",
    re.IGNORECASE,
)
_HTML_ENTITY_PATTERN = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]{1,9}|#\d{1,7}|#x[0-9a-fA-F]{1,6});")
_ADJACENT_TAG_PATTERN = re.compile(
    r"</(?:b|strong|i|em|u)>\s*<(?:b|strong|i|em|u)>", re.IGNORECASE
)
_ADJACENT_BOLD_PATTERN = re.compile(r"(?<=\w)\*\*(?=\w)")
_SPEAKER_LINE_PATTERN = re.compile(r"^\*\*(You|FoodFounder AI):\*\*$")


def _pdf_safe(text):
    """Drop characters the embedded fonts cannot render (emoji, etc.)."""
    return "".join(ch for ch in text if ord(ch) < 0x10000)


def _clean_html(text):
    """Convert <br> to newlines, drop harmless inline HTML tags, unescape entities."""
    text = _BR_PATTERN.sub("\n", text)
    text = _ADJACENT_TAG_PATTERN.sub(" ", text)
    text = _HTML_TAG_PATTERN.sub("", text)
    text = _HTML_ENTITY_PATTERN.sub(lambda m: html.unescape(m.group(0)), text)
    return text.replace("\xa0", " ")


def _fix_run_together_bold(text):
    """Insert a space where bold markers split words: small**scale** -> small **scale**."""
    return _ADJACENT_BOLD_PATTERN.sub(" **", text)


def _strip_inline_markers(text):
    return text.replace("**", "").replace("__", "")


def _column_widths(rows, total_width):
    """Distribute table width across columns, weighted by content length."""
    column_count = max(len(row) for row in rows)
    weights = []
    for col in range(column_count):
        longest = max(
            (len(row[col]) if col < len(row) else 0 for row in rows),
            default=1,
        )
        weights.append(min(max(longest, 6), 40))
    weight_total = sum(weights)
    widths = [total_width * w / weight_total for w in weights]
    floor = total_width * 0.08
    return [max(w, floor) for w in widths]


def _render_markdown_pdf(markdown_text):
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    family = "Helvetica"
    italic_style = "I"
    regular = _WINDOWS_FONTS / "arial.ttf"
    bold = _WINDOWS_FONTS / "arialbd.ttf"
    italic = _WINDOWS_FONTS / "ariali.ttf"
    if regular.exists() and bold.exists():
        pdf.add_font("App", "", str(regular))
        pdf.add_font("App", "B", str(bold))
        family = "App"
        if italic.exists():
            pdf.add_font("App", "I", str(italic))
        else:
            italic_style = ""

    def write_paragraph(text, size=BODY_PT, style="", new_x="LMARGIN", new_y="NEXT"):
        pdf.set_font(family, style=style, size=size)
        pdf.multi_cell(0, 6, _pdf_safe(text), markdown=True, new_x=new_x, new_y=new_y)

    def draw_divider():
        pdf.set_draw_color(*DIVIDER_COLOR)
        pdf.set_line_width(DIVIDER_WIDTH)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)

    headings_style = FontFace(
        emphasis="B", size_pt=TABLE_HEADER_PT, fill_color=TABLE_HEADER_FILL
    )
    chat_turn_count = 0

    lines = markdown_text.split("\n")
    index = 0
    while index < len(lines):
        cleaned = _LINK_PATTERN.sub(
            lambda m: f"{m.group(1)} ({m.group(2)})",
            _clean_html(lines[index]),
        )
        stripped = cleaned.strip()

        if stripped.startswith("|"):
            table_lines = []
            while index < len(lines):
                cleaned = _LINK_PATTERN.sub(
                    lambda m: f"{m.group(1)} ({m.group(2)})",
                    _clean_html(lines[index]),
                ).strip()
                if not cleaned.startswith("|"):
                    break
                table_lines.append(cleaned)
                index += 1
            rows = [
                [
                    _fix_run_together_bold(_pdf_safe(cell.strip()))
                    for cell in row.strip("|").split("|")
                ]
                for row in table_lines
                if not _TABLE_SEPARATOR.match(row)
            ]
            if rows:
                column_count = max(len(row) for row in rows)
                widths = _column_widths(rows, pdf.w - pdf.l_margin - pdf.r_margin)
                previous_font = pdf.font_family
                previous_size = pdf.font_size
                pdf.set_font(family, size=TABLE_BODY_PT)
                pdf.ln(TABLE_SPACE_BEFORE)
                with pdf.table(
                    col_widths=widths,
                    first_row_as_headings=True,
                    headings_style=headings_style,
                    text_align="LEFT",
                    padding=TABLE_PADDING,
                    line_height=TABLE_LINE_HEIGHT,
                    wrapmode="WORD",
                    repeat_headings=1,
                    markdown=True,
                ) as table:
                    for row in rows:
                        table_row = table.row()
                        for cell in row:
                            table_row.cell(cell)
                        for _ in range(column_count - len(row)):
                            table_row.cell("")
                pdf.set_font(previous_font, size=previous_size)
                pdf.ln(TABLE_SPACE_AFTER)
            continue

        speaker_match = _SPEAKER_LINE_PATTERN.match(stripped)
        if speaker_match:
            if chat_turn_count > 0:
                pdf.ln(2)
                draw_divider()
                pdf.ln(2)
            write_paragraph(
                f"**{speaker_match.group(1)}:**", size=CHAT_LABEL_PT
            )
            chat_turn_count += 1
            index += 1
            continue

        if not stripped:
            pdf.ln(2)
        elif stripped.startswith("# "):
            write_paragraph(_strip_inline_markers(stripped[2:]), size=16, style="B")
            pdf.ln(2)
        elif stripped.startswith("## "):
            pdf.ln(2)
            write_paragraph(_strip_inline_markers(stripped[3:]), size=13, style="B")
        elif stripped.startswith("### "):
            write_paragraph(_strip_inline_markers(stripped[4:]), size=11, style="B")
        elif stripped == "---":
            pdf.ln(2)
            draw_divider()
            pdf.ln(2)
        elif stripped.startswith("> "):
            write_paragraph(_strip_inline_markers(stripped[2:]), style=italic_style)
        elif stripped.startswith("- [ ]"):
            write_paragraph("[ ] " + _strip_inline_markers(stripped[5:].strip()))
        elif stripped.startswith(("- ", "* ")):
            write_paragraph("• " + _strip_inline_markers(stripped[2:]))
        elif re.match(r"^\d+\.\s", stripped):
            write_paragraph(_strip_inline_markers(stripped))
        else:
            write_paragraph(_fix_run_together_bold(stripped))
        index += 1

    return bytes(pdf.output())


def build_pdf_report(product=None, result=None, chat_history=None, generated_at=None):
    """Return the product development summary as PDF bytes (UTF-8 safe)."""
    markdown = build_report(
        product=product,
        result=result,
        chat_history=chat_history,
        generated_at=generated_at,
    )
    return _render_markdown_pdf(markdown)
