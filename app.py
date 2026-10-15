import pandas as pd
import streamlit as st

from services import ai_assistant, guidance, persistence, report
from services.ai_assistant import AssistantError
from services.calculator import CalculatorError, Ingredient, calculate_batch

st.set_page_config(
    page_title="FoodFounder AI",
    page_icon="🍽️",
    layout="centered",
)

# --- Session identity -------------------------------------------------------
# Each browser tab session carries a stable id in the URL `sid` query param.
# On a genuinely new session (no/invalid sid) a tiny inline script runs in the
# MAIN document via st.html(..., unsafe_allow_javascript=True). This matters:
# st.iframe content is sandboxed without `allow-top-navigation`, so Chrome
# blocks the iframe's attempt to navigate the top window — the old approach
# never added the sid and persistence never engaged. The script reads or
# creates the id in the tab's sessionStorage and calls location.replace() once
# with the sid added (replace, not assign, so the pre-sid URL stays out of the
# history). Existing query params — including `page` — are preserved. A
# redirect loop is impossible: the script only renders when the URL has no
# valid sid, and after the replace the URL always has one (Python re-checks
# with persistence.valid_session_id). A refresh keeps the URL (same sid ->
# same saved data); a new tab has empty sessionStorage -> fresh sid -> fresh
# data. Note: duplicating a tab clones sessionStorage, so a duplicate shares
# the session's sid (browser behavior, documented rather than "fixed").
SID_BOOTSTRAP_HTML = """
<script>
(function () {
  var loc = window.location;
  var params = new URLSearchParams(loc.search);
  var current = params.get("sid");
  if (current && /^[A-Za-z0-9_-]{16,64}$/.test(current)) { return; }
  var sid = null;
  try { sid = window.sessionStorage.getItem("ff_sid"); } catch (err) {}
  if (!sid || !/^[A-Za-z0-9_-]{16,64}$/.test(sid)) {
    sid = (window.crypto && window.crypto.randomUUID)
      ? window.crypto.randomUUID()
      : "s" + Date.now().toString(36) + Math.random().toString(36).slice(1, 12);
    try { window.sessionStorage.setItem("ff_sid", sid); } catch (err) {}
  }
  params.set("sid", sid);
  loc.replace(loc.pathname + "?" + params.toString() + loc.hash);
})();
</script>
"""

SESSION_ID = persistence.valid_session_id(st.query_params.get("sid"))
if SESSION_ID is None:
    # Pre-session render: no restore, no save. The script above navigates
    # once with a fresh sid, after which this branch is not taken again.
    st.html(SID_BOOTSTRAP_HTML, unsafe_allow_javascript=True)
else:
    # Restore this session's persisted data (only fills missing keys).
    try:
        persistence.restore_session_state(st.session_state, SESSION_ID)
    except Exception:
        pass

# --- Light / Dark theme ------------------------------------------------------
# The sidebar toggle writes st.session_state["theme_dark"]; every rerun
# rebuilds one CSS block from the matching palette below. Overriding
# Streamlit's own theme CSS variables (background/secondary/primary/text)
# retints widgets, inputs, and buttons consistently, with extra selectors
# for cards, chat bubbles, metrics, tables, and expanders. The choice lives
# in session_state, so it survives navigation and ordinary reruns without
# touching product data, calculations, or chat; a toggle rerun never changes
# the page, so the scroll-to-top gate never fires.
THEME_PALETTES = {
    "light": {
        "bg": "#f4f8f4",
        "secondary": "#ffffff",
        "text": "#17251a",
        "muted": "#4a5d4e",
        "primary": "#2e7d32",
        "primary_text": "#ffffff",
        "border": "#d5e3d7",
        "card": "#ffffff",
        "chat": "#eef6ef",
        "hover": "#e6f1e7",
    },
    "dark": {
        "bg": "#0d1410",
        "secondary": "#152019",
        "text": "#e4f0e6",
        "muted": "#9db8a3",
        "primary": "#66bb6a",
        "primary_text": "#0d1410",
        "border": "#2b3d31",
        "card": "#152019",
        "chat": "#1c2a20",
        "hover": "#24382a",
    },
}

THEME_CSS_TEMPLATE = """
<style id="ff-theme" data-mode="__MODE__">
:root {{
  --background-color: {bg};
  --secondary-background-color: {secondary};
  --primary-color: {primary};
  --text-color: {text};
}}
html, body,
[data-testid="stAppViewContainer"],
.main .block-container,
section.stMain {{
  background-color: {bg} !important;
  color: {text};
}}
[data-testid="stSidebar"] {{
  background-color: {secondary} !important;
  border-right: 1px solid {border};
}}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2 {{ color: {text}; }}
h1, h2, h3, h4, h5, h6,
p, li, label, .stMarkdown, .stCaption {{ color: {text}; }}
div[data-testid="stButton"] > button {{
  background-color: {secondary};
  color: {text};
  border: 1px solid {border};
  border-radius: 8px;
  transition: border-color 0.15s ease, color 0.15s ease;
}}
div[data-testid="stButton"] > button:hover {{
  border-color: {primary};
  color: {primary};
  background-color: {hover};
}}
div[data-testid="stButton"] > button[kind="primary"] {{
  background-color: {primary};
  color: {primary_text};
  border: 1px solid {primary};
}}
div[data-testid="stButton"] > button[kind="primary"]:hover {{
  background-color: {primary};
  color: {primary_text};
  opacity: 0.92;
}}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stDateInput"] input,
[data-testid="stChatInput"] {{
  background-color: {secondary};
  color: {text};
  border: 1px solid {border};
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
  border-color: {primary};
  color: {text};
}}
[data-testid="stChatInput"] textarea {{ background: transparent; color: {text}; }}
[data-testid="stChatInput"] button {{ color: {muted}; }}
[data-testid="stChatInput"] button:hover {{ color: {primary}; }}
div[data-testid="stExpander"] {{
  background-color: {card};
  border: 1px solid {border};
  border-radius: 10px;
}}
[data-testid="stChatMessage"] {{
  background-color: {chat};
  border: 1px solid {border};
  border-radius: 12px;
  padding: 10px 14px;
}}
[data-testid="stChatMessage"] * {{ color: {text}; }}
[data-testid="stMetric"] {{
  background-color: {card};
  border: 1px solid {border};
  border-radius: 10px;
  padding: 12px 16px;
}}
[data-testid="stMetricLabel"] {{ color: {muted}; }}
[data-testid="stMetricValue"] {{ color: {text}; }}
[data-testid="stMetricDelta"] {{ color: {primary}; }}
[data-testid="stDataFrame"],
div[data-testid="st.data_editor"],
div[data-testid="st.dataframe"] {{
  background-color: {secondary};
  border: 1px solid {border};
  border-radius: 10px;
}}
[data-testid="stPlotlyChart"],
[data-testid="stAltairChart"] {{
  background-color: {secondary};
  border: 1px solid {border};
  border-radius: 10px;
}}
[data-baseweb="tab"] {{ color: {muted}; }}
[data-baseweb="tab"][aria-selected="true"] {{
  color: {primary};
  border-bottom-color: {primary};
}}
[data-baseweb="tab-list"] {{ background-color: {secondary}; border-radius: 8px; }}
.stRadio label, .stToggle label {{ color: {text}; }}
[data-testid="stDivider"] hr {{ border-color: {border}; }}
</style>
"""


def build_theme_css(mode):
    """Return the themed CSS block for 'light' or 'dark'."""
    palette = THEME_PALETTES["dark" if mode == "dark" else "light"]
    return THEME_CSS_TEMPLATE.replace("__MODE__", mode).format(**palette)


st.session_state.setdefault("theme_dark", False)
st.markdown(
    build_theme_css("dark" if st.session_state["theme_dark"] else "light"),
    unsafe_allow_html=True,
)

PAGES = ["Home", "Cost Calculator", "AI Guidance", "Product Development"]

PRODUCT_CATEGORIES = [
    "Snacks",
    "Beverages",
    "Bakery",
    "Confectionery",
    "Pickles & Preserves",
    "Dairy",
    "Spices & Masala",
    "Ready-to-eat",
    "Other",
]

UNITS = ["kg", "g", "L", "ml", "pieces", "packs"]

EXAMPLE_INGREDIENTS = pd.DataFrame(
    [
        {"Ingredient": "Bananas", "Quantity": 10.0, "Unit": "kg", "Price per unit (INR)": 40.0},
        {"Ingredient": "Refined oil", "Quantity": 2.0, "Unit": "L", "Price per unit (INR)": 150.0},
        {"Ingredient": "Salt", "Quantity": 0.2, "Unit": "kg", "Price per unit (INR)": 20.0},
        {"Ingredient": "Spice mix", "Quantity": 0.1, "Unit": "kg", "Price per unit (INR)": 200.0},
    ]
)


def money(value):
    return f"₹{value:,.2f}"


def load_example():
    st.session_state["ingredients_seed"] = EXAMPLE_INGREDIENTS.copy()
    st.session_state["product"] = {
        "name": "Banana Chips",
        "category": "Snacks",
        "batch_size": 10.0,
        "batch_unit": "kg",
        "budget": 5000.0,
    }


def build_pdf_summary(product, result):
    """Return PDF bytes for the summary, or None if PDF generation is unavailable."""
    builder = getattr(report, "build_pdf_report", None)
    if builder is None:
        return None
    try:
        return builder(
            product=product,
            result=result,
            chat_history=st.session_state.get("chat_history"),
        )
    except Exception:
        return None


def render_summary_section(product, result, key_prefix, heading=None, with_preview=False):
    """Shared Product Development summary block (Markdown + optional PDF).

    Used by the Cost Calculator (after a run) and by the Product Development
    page so the implementation lives in one place.
    """
    if heading:
        st.markdown(heading)
    summary_text = report.build_report(
        product=product,
        result=result,
        chat_history=st.session_state.get("chat_history"),
    )
    summary_pdf = build_pdf_summary(product, result)
    if summary_pdf is not None:
        st.download_button(
            "📄 Download product development summary (PDF)",
            data=summary_pdf,
            file_name="foodfounder_summary.pdf",
            mime="application/pdf",
            key=f"download_report_pdf_{key_prefix}",
            type="primary",
            width="stretch",
        )
    else:
        st.caption("PDF export is unavailable in this session; Markdown download is below.")
    st.download_button(
        "📥 Download product development summary (Markdown)",
        data=summary_text,
        file_name="foodfounder_summary.md",
        mime="text/markdown",
        key=f"download_report_{key_prefix}",
        width="stretch",
    )
    if with_preview:
        with st.expander("Preview summary"):
            st.markdown(summary_text)
    return summary_text


def page_home():
    st.title("🍽️ FoodFounder AI")
    st.subheader("An AI Assistant for Small-Scale Food Entrepreneurs")

    st.markdown(
        """
        FoodFounder AI helps small-scale food entrepreneurs move from a product idea
        to preliminary formulation guidance, production cost estimation,
        packaging considerations, and food-processing guidance.

        **What you can do here:**
        - 💰 Estimate production cost, cost per packet, and profit margins
        - 🤖 Ask the AI assistant about formulation, packaging, and processing
        - 📦 View packaging and process checklists
        - 📄 Generate a product development summary
        """
    )

    st.divider()
    st.markdown("### Step 1 — Set up your product")

    saved_product = st.session_state.get("product") or {}
    desired_name = str(saved_product.get("name") or "")
    saved_category = saved_product.get("category")
    category_index = (
        PRODUCT_CATEGORIES.index(saved_category)
        if saved_category in PRODUCT_CATEGORIES
        else 0
    )
    saved_batch_size = saved_product.get("batch_size")
    if not isinstance(saved_batch_size, (int, float)) or saved_batch_size <= 0:
        saved_batch_size = 10.0
    saved_batch_unit = saved_product.get("batch_unit")
    unit_index = UNITS.index(saved_batch_unit) if saved_batch_unit in UNITS else 0
    saved_budget = saved_product.get("budget")
    if not isinstance(saved_budget, (int, float)) or saved_budget < 0:
        saved_budget = 5000.0

    # Re-key the form whenever the saved product name changes so the widgets
    # re-initialize from the saved values (avoids stale widget state).
    if st.session_state.get("_product_form_name") != desired_name:
        st.session_state["_product_form_name"] = desired_name
        st.session_state["_product_form_version"] = (
            st.session_state.get("_product_form_version", 0) + 1
        )
    form_key = f"product_setup_{st.session_state.get('_product_form_version', 0)}"

    with st.form(form_key):
        name = st.text_input(
            "Product name",
            value=desired_name,
            placeholder="e.g. Banana Chips",
        )
        category = st.selectbox(
            "Product category", PRODUCT_CATEGORIES, index=category_index
        )
        col1, col2 = st.columns(2)
        with col1:
            batch_size = st.number_input(
                "Batch size", min_value=0.0, value=float(saved_batch_size), step=1.0
            )
        with col2:
            batch_unit = st.selectbox("Batch unit", UNITS, index=unit_index)
        budget = st.number_input(
            "Approximate budget for this batch (INR, optional)",
            min_value=0.0,
            value=float(saved_budget),
            step=100.0,
        )
        submitted = st.form_submit_button("Start", type="primary")

    if submitted:
        if not name.strip():
            st.error("Please enter a product name.")
        elif batch_size <= 0:
            st.error("Batch size must be greater than zero.")
        else:
            st.session_state["product"] = {
                "name": name.strip(),
                "category": category,
                "batch_size": batch_size,
                "batch_unit": batch_unit,
                "budget": budget,
            }
            st.success(
                f"Product **{name.strip()}** saved. "
                "Now open **Cost Calculator** in the sidebar."
            )

    product = st.session_state.get("product")
    if product:
        st.info(
            f"Current product: **{product['name']}** "
            f"({product['category']}, batch {product['batch_size']:g} {product['batch_unit']})"
        )


def page_calculator():
    st.title("💰 Cost Calculator")
    st.caption("Estimates only — actual costs may vary with wastage, taxes, transport, and retailer margins.")

    # Ensure calculator input widget keys exist (restored values win; these
    # defaults only apply on the very first run). Keys are set before the
    # widgets are created so no default/value conflict warning is raised.
    _input_defaults = {
        "packaging_cost": 150.0,
        "labour_cost": 200.0,
        "energy_cost": 100.0,
        "other_cost": 50.0,
        "saleable_packets": 40,
        "selling_price": 50.0,
    }
    for _key, _default in _input_defaults.items():
        if _key not in st.session_state:
            st.session_state[_key] = _default

    product = st.session_state.get("product")

    st.markdown("### Product details")
    if product:
        col1, col2, col3 = st.columns(3)
        col1.metric("Product", product["name"])
        col2.metric("Category", product["category"])
        col3.metric("Batch", f"{product['batch_size']:g} {product['batch_unit']}")
        product_name = product["name"]
        product_category = product["category"]
        batch_size = product["batch_size"]
        batch_unit = product["batch_unit"]
    else:
        st.warning("No product set on the Home page — enter the basics below.")
        product_name = st.text_input("Product name", value="Banana Chips")
        product_category = st.selectbox("Product category", PRODUCT_CATEGORIES)
        col1, col2 = st.columns(2)
        with col1:
            batch_size = st.number_input("Batch size", min_value=0.0, value=10.0, step=1.0)
        with col2:
            batch_unit = st.selectbox("Batch unit", UNITS, index=0)

    st.markdown("### Ingredients")
    st.caption("Edit the rows below. Use the + button to add rows and × to remove them.")

    seed = st.session_state.pop("ingredients_seed", None)
    if seed is not None:
        new_version = st.session_state.get("ingredients_version", 0) + 1
        st.session_state["ingredients_version"] = new_version
        editor_default = seed
    else:
        editor_default = EXAMPLE_INGREDIENTS.copy()
    editor_key = f"ingredients_editor_{st.session_state.get('ingredients_version', 0)}"

    edited = st.data_editor(
        editor_default,
        num_rows="dynamic",
        width="stretch",
        key=editor_key,
        column_config={
            "Ingredient": st.column_config.TextColumn("Ingredient", required=True),
            "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, format="%.3f"),
            "Unit": st.column_config.SelectboxColumn("Unit", options=UNITS),
            "Price per unit (INR)": st.column_config.NumberColumn(
                "Price per unit (₹)", min_value=0.0, format="₹%.2f"
            ),
        },
    )
    st.session_state["ingredients_df"] = edited

    st.markdown("### Other production expenses")
    col1, col2 = st.columns(2)
    with col1:
        packaging_cost = st.number_input(
            "Packaging cost (₹)", key="packaging_cost", min_value=0.0, step=10.0
        )
        labour_cost = st.number_input(
            "Labour cost (₹)", key="labour_cost", min_value=0.0, step=10.0
        )
    with col2:
        energy_cost = st.number_input(
            "Energy cost (₹)", key="energy_cost", min_value=0.0, step=10.0
        )
        other_cost = st.number_input(
            "Other expenses (₹)", key="other_cost", min_value=0.0, step=10.0
        )

    st.markdown("### Sales assumptions")
    col1, col2 = st.columns(2)
    with col1:
        saleable_packets = st.number_input(
            "Number of saleable packets", key="saleable_packets", min_value=1, step=1
        )
    with col2:
        selling_price = st.number_input(
            "Selling price per packet (₹)", key="selling_price", min_value=0.0, step=1.0
        )

    col1, col2 = st.columns([1, 1])
    calculate_clicked = col1.button("Calculate costs", type="primary")
    col2.button("Load banana chips example", on_click=load_example)

    if calculate_clicked:
        rows = edited.to_dict("records")
        ingredients = []
        for row in rows:
            name = str(row.get("Ingredient") or "").strip()
            if not name:
                continue
            ingredients.append(
                Ingredient(
                    name=name,
                    quantity=row.get("Quantity") if row.get("Quantity") is not None else 0.0,
                    unit=str(row.get("Unit") or "unit"),
                    price_per_unit=(
                        row.get("Price per unit (INR)")
                        if row.get("Price per unit (INR)") is not None
                        else 0.0
                    ),
                )
            )

        try:
            st.session_state["cost_result"] = calculate_batch(
                product_name=product_name,
                product_category=product_category,
                batch_size=batch_size,
                batch_unit=batch_unit,
                ingredients=ingredients,
                packaging_cost=packaging_cost,
                labour_cost=labour_cost,
                energy_cost=energy_cost,
                other_cost=other_cost,
                saleable_packets=saleable_packets,
                selling_price=selling_price,
            )
        except CalculatorError as error:
            st.session_state.pop("cost_result", None)
            st.error(f"Cannot calculate: {error}")

    result = st.session_state.get("cost_result")
    if result:
        st.divider()
        st.markdown(f"### Estimated results — {result.product_name}")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Cost / packet", money(result.cost_per_packet))
        if result.profit_margin_pct is None:
            col2.metric("Profit / packet", money(result.profit_per_packet))
            col3.metric("Margin", "n/a (price is 0)")
        else:
            col2.metric("Profit / packet", money(result.profit_per_packet))
            col3.metric("Margin", f"{result.profit_margin_pct:.1f}%")
        col4.metric("Batch profit", money(result.batch_profit))

        st.markdown("#### Cost breakdown")
        breakdown_rows = [
            {"Item": name, "Cost (₹)": cost} for name, cost in result.ingredient_costs
        ]
        breakdown_rows.append({"Item": "Total ingredients", "Cost (₹)": result.total_ingredient_cost})
        breakdown_rows.append({"Item": "Packaging", "Cost (₹)": result.packaging_cost})
        breakdown_rows.append({"Item": "Labour", "Cost (₹)": result.labour_cost})
        breakdown_rows.append({"Item": "Energy", "Cost (₹)": result.energy_cost})
        breakdown_rows.append({"Item": "Other expenses", "Cost (₹)": result.other_cost})
        breakdown_rows.append(
            {"Item": "TOTAL production cost", "Cost (₹)": result.total_production_cost}
        )
        st.dataframe(pd.DataFrame(breakdown_rows), width="stretch", hide_index=True)

        with st.expander("Assumptions and limitations"):
            st.markdown(
                """
                - All figures are **estimates** for planning, not accounting-grade results.
                - Ingredient cost = quantity used × price per unit, as you entered them.
                - Costs currently included: ingredients, packaging, labour, energy, other (as entered).
                - Costs **not** included unless you add them above: wastage/spoilage, GST/taxes,
                  transport, storage, shop or marketplace commissions, retailer margins,
                  marketing, licence fees, and equipment depreciation.
                - Profit margin is shown only when selling price is greater than zero.
                - Verify ingredient prices, yields, and shelf life with suppliers and trials.
                - For Indian food businesses, check FSSAI licensing and labelling rules
                  before selling: https://www.fssai.gov.in/
                """
            )

        render_summary_section(product, result, key_prefix="calculator")


def page_ai():
    st.title("🤖 AI Guidance")
    st.caption(
        "Chat with FoodFounder AI about preliminary formulation, packaging, "
        "processing, costing concepts, and food safety."
    )
    st.caption(
        "AI suggestions are preliminary starting points — not lab-validated. "
        "Confirm safety, labelling, and licensing with experts and FSSAI (https://www.fssai.gov.in/)."
    )

    api_key = ai_assistant.get_api_key()
    with st.expander("API setup help (open this if the chat shows a key error)"):
        if api_key:
            st.success("API key detected — chat is ready.")
        else:
            st.warning("No API key found yet. Follow the steps below.")
        st.markdown(
            """
            FoodFounder AI uses the **Groq API** (free developer tier available).

            1. Get a free key: https://console.groq.com/keys
            2. Either add it to `.streamlit/secrets.toml` (already ignored by Git):
               ```toml
               GROQ_API_KEY = "paste-your-key-here"
               ```
               or set it in PowerShell for the current session only:
               ```powershell
               $env:GROQ_API_KEY = "paste-your-key-here"
               ```
            3. Fully restart the app (`Ctrl+C`, then `streamlit run app.py`).
            """
        )

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    product = st.session_state.get("product")
    context_parts = []
    if product:
        context_parts.append(
            f"{product['name']} ({product['category']}), "
            f"batch {product['batch_size']:g} {product['batch_unit']}"
        )
    result = st.session_state.get("cost_result")
    if result:
        margin = (
            f"{result.profit_margin_pct:.1f}%"
            if result.profit_margin_pct is not None
            else "n/a"
        )
        context_parts.append(
            f"latest batch estimate: total production cost INR {result.total_production_cost:,.2f}, "
            f"cost per packet INR {result.cost_per_packet:,.2f}, "
            f"proposed selling price INR {result.selling_price:,.2f}, margin {margin}"
        )
    product_context = "; ".join(context_parts) if context_parts else None

    quick_prompts = [
        "How should I package banana chips to keep them crisp?",
        "Suggest cheaper ingredient alternatives for my product",
        "What are the FSSAI basics for selling packaged food in India?",
        "Give me a simple trial-batch plan to test my product",
    ]
    quick_cols = st.columns(2)
    for col, prompt in zip(quick_cols, quick_prompts):
        if col.button(prompt, key=f"quick_{prompt}", width="stretch"):
            st.session_state["pending_question"] = prompt
            st.rerun()

    if st.button("Clear chat"):
        st.session_state["chat_history"] = []
        st.rerun()

    question = st.session_state.pop("pending_question", None)
    typed_question = st.chat_input("Ask about formulation, packaging, processing, costing...")
    if question is None:
        question = typed_question

    if question:
        history = st.session_state["chat_history"]
        if (
            len(history) >= 2
            and history[-1]["role"] == "model"
            and history[-2]["role"] == "user"
            and history[-2]["text"] == question
        ):
            question = None

    if question:
        st.session_state["chat_history"].append({"role": "user", "text": question})

    for turn in st.session_state["chat_history"]:
        with st.chat_message(turn["role"]):
            st.markdown(turn["text"])

    if question:
        with st.spinner("FoodFounder AI is thinking..."):
            try:
                answer = ai_assistant.chat(
                    question,
                    history=st.session_state["chat_history"][:-1],
                    product_context=product_context,
                )
            except AssistantError as error:
                st.error(str(error))
            else:
                st.session_state["chat_history"].append({"role": "model", "text": answer})
                with st.chat_message("assistant"):
                    st.markdown(answer)

    st.divider()
    st.markdown("### 📦 Packaging, process, and trial checklists")
    st.caption(guidance.DISCLAIMER)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Packaging", "Processing", "Product trials", "FSSAI resources"]
    )
    with tab1:
        st.markdown(guidance.checklist_as_markdown(guidance.PACKAGING_CHECKLIST))
    with tab2:
        st.markdown(guidance.checklist_as_markdown(guidance.PROCESS_CHECKLIST))
    with tab3:
        st.markdown(guidance.checklist_as_markdown(guidance.TRIAL_CHECKLIST))
    with tab4:
        st.markdown(
            "Official FSSAI links (verified reachable). "
            "Always confirm current requirements on these sites:"
        )
        st.markdown(guidance.resources_as_markdown())


def page_product_development():
    st.title("📄 Product Development")
    st.caption(
        "Download a development summary built from your product setup, "
        "latest cost estimate, and AI guidance conversation."
    )
    product = st.session_state.get("product")
    result = st.session_state.get("cost_result")
    if not product:
        st.info("No product set yet — add your basics on the Home page for a fuller summary.")
    if not result:
        st.info("No cost estimate yet — run the Cost Calculator for a fuller summary.")
    st.divider()
    render_summary_section(
        product,
        result,
        key_prefix="product",
        heading="### 📄 Product development summary",
        with_preview=True,
    )


# --- Navigation (URL query param keeps the page across browser refresh) ---
# The URL is the source of truth: it survives a refresh and reflects
# back/forward. We only adopt a URL value that differs from the last one we
# observed, so a user click (handled by on_change) is never clobbered.
url_page = st.query_params.get("page")
_seen_url = st.session_state.get("_nav_url_seen")

if url_page in PAGES and url_page != _seen_url:
    # URL changed externally (refresh restored it, or back/forward) — adopt it.
    st.session_state["nav_page"] = url_page
    st.session_state["_nav_url_seen"] = url_page
elif "nav_page" not in st.session_state:
    # First run in this session with no usable URL param — default to Home.
    st.session_state["nav_page"] = PAGES[0]


def _sync_nav_to_url():
    new_page = st.session_state.get("nav_page")
    if new_page in PAGES:
        st.session_state["_nav_url_seen"] = new_page
        st.query_params["page"] = new_page


st.sidebar.title("🍽️ FoodFounder AI")
st.sidebar.caption("AI assistant for small-scale food entrepreneurs")
page = st.sidebar.radio(
    "Go to",
    PAGES,
    key="nav_page",
    label_visibility="collapsed",
    on_change=_sync_nav_to_url,
)
st.sidebar.toggle(
    "🌙 Dark mode",
    key="theme_dark",
    help="Switch the app between light and dark themes",
)
st.sidebar.divider()
product = st.session_state.get("product")
if product:
    st.sidebar.markdown(f"**Current product**\n\n{product['name']} ({product['category']})")

# Keep the URL in sync (covers first visit and any missed callback).
if st.query_params.get("page") != page:
    st.query_params["page"] = page
    st.session_state["_nav_url_seen"] = page

# One-shot scroll-to-top when (and only when) the page actually changes.
# Streamlit 1.65 does not scroll the browser window: the app content lives
# in an inner <section> with class="stMain" (height:100dvh, overflow:auto),
# so window.scrollTo() is a no-op there (the reason the earlier st.html fix
# failed in a real browser). The data-testid attribute of that <section>
# flips between "stMain" and "stAppScrollToBottomContainer" (when the page
# contains a bottom-anchored st.chat_input, as on AI Guidance), so we select
# by the stable CSS class "section.stMain" first and fall back to both
# data-testid values. On AI Guidance, Streamlit scrolls the chat input into
# view ~0.5s AFTER mount and would override an immediate reset, so that
# page's script schedules ONE extra reset 1s later (a single setTimeout —
# never a loop — so ordinary scrolling, chat, and calculations are never
# fought). The gate keeps mid-task reruns from ever emitting the script, and
# setdefault leaves the session's first run alone.
SCROLL_TO_TOP_TEMPLATE = (
    "<script>(function(){"
    "var w = window.parent;"
    "function target(){"
    "return w.document.querySelector("
    "'section.stMain, [data-testid=\"stMain\"], [data-testid=\"stAppScrollToBottomContainer\"]'"
    ");"
    "}"
    "function reset(){"
    "try { w.scrollTo(0, 0); } catch (e) {}"
    "var m = target();"
    "if (m) { m.scrollTop = 0; }"
    "}"
    "__ACTION__"
    "})();</script>"
    "<!-- ff-nav: __PAGE__ -->"
)


def scroll_to_top_html(page):
    if page == "AI Guidance":
        # Root cause of the bottom-then-top flicker (verified in Chrome via
        # scrollTop-setter + stack instrumentation): at mount, Streamlit's
        # bundle starts a requestAnimationFrame easing loop that writes
        # section.scrollTop each frame to reveal the chat input
        # (index.CKCTizkM.js — cancelAnimationFrame chain, cancelled only by
        # real pointerdown/wheel on the section). Our iframe script runs a
        # frame after their loop starts, so we: (1) dispatch a synthetic
        # pointerdown on the section to trigger THEIR OWN cancel path
        # (listener is attached in the same layout effect that starts the
        # loop, so it is always in place before our script runs); (2) keep a
        # short scrollTop-setter trap as defense-in-depth during the mount
        # window so nothing can paint the page away from the top; (3) the
        # trap removes itself on user interaction or one cleanup timeout —
        # never a scroll loop; mid-task reruns never emit this script.
        action = (
            "var touched = false;"
            "var m = target();"
            "var untrap = function(){};"
            "if (m) {"
            "var proto = Object.getOwnPropertyDescriptor(w.Element.prototype, 'scrollTop');"
            "var origRAF = w.requestAnimationFrame;"
            "var origCAF = w.cancelAnimationFrame;"
            "var lastId = null, tried = false;"
            "w.requestAnimationFrame = function(cb){"
            "var id = origRAF.call(w, function(ts){"
            "tried = false;"
            "var r = cb(ts);"
            "if (tried && lastId !== null) { origCAF.call(w, lastId); lastId = null; }"
            "return r;"
            "});"
            "lastId = id;"
            "return id;"
            "};"
            "untrap = function(){"
            "try { delete m.scrollTop; } catch (e) {}"
            "w.requestAnimationFrame = origRAF;"
            "w.cancelAnimationFrame = origCAF;"
            "};"
            "Object.defineProperty(m, 'scrollTop', {"
            "get: function(){ return proto.get.call(this); },"
            "set: function(x){"
            "if (touched) { untrap(); return proto.set.call(this, x); }"
            "tried = true;"
            "return proto.set.call(this, 0);"
            "},"
            "configurable: true"
            "});"
            "try {"
            "m.dispatchEvent(new w.PointerEvent('pointerdown',"
            "{bubbles: true, cancelable: true, pointerId: 1}));"
            "} catch (e) {}"
            "}"
            "try {"
            "['wheel','touchmove','keydown'].forEach(function(ev){"
            "w.addEventListener(ev, function(){ touched = true; untrap(); }, {passive: true});"
            "});"
            "} catch (e) {}"
            "reset();"
            "setTimeout(untrap, 1500);"
        )
    else:
        action = "reset();"
    return SCROLL_TO_TOP_TEMPLATE.replace("__ACTION__", action).replace("__PAGE__", page)


# A session whose FIRST run lands directly on AI Guidance (?page= URL,
# browser refresh) never triggers the page-change gate below, leaving
# Streamlit's chat-input mount scroll unopposed (lands at the bottom).
# Emit the AI mount guard on that first run too; other pages' first runs
# stay untouched (they have no mount scroll).
_scrolled_first_run = "_scrolled_page" not in st.session_state
st.session_state.setdefault("_scrolled_page", page)
if st.session_state["_scrolled_page"] != page or (_scrolled_first_run and page == "AI Guidance"):
    st.iframe(scroll_to_top_html(page), height=1)
    st.session_state["_scrolled_page"] = page

if page == "Home":
    page_home()
elif page == "Cost Calculator":
    page_calculator()
elif page == "AI Guidance":
    page_ai()
else:
    page_product_development()

# --- Persist state so a browser refresh of this session can restore it ---
if SESSION_ID is not None:
    try:
        persistence.save_state(
            persistence.capture_session_state(st.session_state), SESSION_ID
        )
    except Exception:
        pass
