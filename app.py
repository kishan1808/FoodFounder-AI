import pandas as pd
import streamlit as st

from services import ai_assistant, guidance, report
from services.ai_assistant import AssistantError
from services.calculator import CalculatorError, Ingredient, calculate_batch

st.set_page_config(
    page_title="FoodFounder AI",
    page_icon="🍽️",
    layout="centered",
)

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

    with st.form("product_setup"):
        name = st.text_input("Product name", placeholder="e.g. Banana Chips")
        category = st.selectbox("Product category", PRODUCT_CATEGORIES)
        col1, col2 = st.columns(2)
        with col1:
            batch_size = st.number_input("Batch size", min_value=0.0, value=10.0, step=1.0)
        with col2:
            batch_unit = st.selectbox("Batch unit", UNITS, index=0)
        budget = st.number_input(
            "Approximate budget for this batch (INR, optional)",
            min_value=0.0,
            value=5000.0,
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

    st.markdown("### Other production expenses")
    col1, col2 = st.columns(2)
    with col1:
        packaging_cost = st.number_input("Packaging cost (₹)", min_value=0.0, value=150.0, step=10.0)
        labour_cost = st.number_input("Labour cost (₹)", min_value=0.0, value=200.0, step=10.0)
    with col2:
        energy_cost = st.number_input("Energy cost (₹)", min_value=0.0, value=100.0, step=10.0)
        other_cost = st.number_input("Other expenses (₹)", min_value=0.0, value=50.0, step=10.0)

    st.markdown("### Sales assumptions")
    col1, col2 = st.columns(2)
    with col1:
        saleable_packets = st.number_input("Number of saleable packets", min_value=1, value=40, step=1)
    with col2:
        selling_price = st.number_input("Selling price per packet (₹)", min_value=0.0, value=50.0, step=1.0)

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

        summary_text = report.build_report(
            product=product,
            result=result,
            chat_history=st.session_state.get("chat_history"),
        )
        st.download_button(
            "📥 Download product development summary (Markdown)",
            data=summary_text,
            file_name="foodfounder_summary.md",
            mime="text/markdown",
            key="download_report_calculator",
            width="stretch",
        )


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
            FoodFounder AI uses the **Google Gemini API free tier** (no credit card needed).

            1. Get a free key: https://aistudio.google.com/apikey
            2. Either add it to `.streamlit/secrets.toml` (already ignored by Git):
               ```toml
               GEMINI_API_KEY = "paste-your-key-here"
               ```
               or set it in PowerShell for the current session only:
               ```powershell
               $env:GEMINI_API_KEY = "paste-your-key-here"
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
    if question is None:
        question = st.chat_input("Ask about formulation, packaging, processing, costing...")

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

    st.divider()
    st.markdown("### 📄 Product development summary")
    summary_text = report.build_report(
        product=product,
        result=result,
        chat_history=st.session_state.get("chat_history"),
    )
    st.download_button(
        "📥 Download summary (Markdown)",
        data=summary_text,
        file_name="foodfounder_summary.md",
        mime="text/markdown",
        key="download_report_ai",
        width="stretch",
    )
    with st.expander("Preview summary"):
        st.markdown(summary_text)


st.sidebar.title("🍽️ FoodFounder AI")
st.sidebar.caption("AI assistant for small-scale food entrepreneurs")
page = st.sidebar.radio(
    "Go to",
    ["Home / Product Setup", "Cost Calculator", "AI Guidance"],
    label_visibility="collapsed",
)
st.sidebar.divider()
product = st.session_state.get("product")
if product:
    st.sidebar.markdown(f"**Current product**\n\n{product['name']} ({product['category']})")

if page == "Home / Product Setup":
    page_home()
elif page == "Cost Calculator":
    page_calculator()
else:
    page_ai()
