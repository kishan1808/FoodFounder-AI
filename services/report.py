"""Builds the downloadable product development summary (Markdown).

Pure Python — no Streamlit — so it can be unit-tested and reused.
"""

from datetime import datetime

from services import guidance

MONEY_FORMAT = "₹{:,.2f}"


def money(value):
    return MONEY_FORMAT.format(value)


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
    lines = ["## 6. AI recommendations (chat excerpts)", ""]
    recent = [turn for turn in (chat_history or []) if turn.get("text")][-6:]
    if not recent:
        lines.append("- No chat yet. Ask the assistant about packaging or processing.")
        return "\n".join(lines)

    for turn in recent:
        speaker = "You" if turn.get("role") == "user" else "FoodFounder AI"
        text = str(turn.get("text", "")).strip()
        if len(text) > 400:
            text = text[:400] + "…"
        lines.append(f"**{speaker}:** {text}")
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
