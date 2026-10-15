"""Local JSON persistence for FoodFounder AI, isolated per browser session.

Each browser tab session gets its own session id (carried in the URL ``sid``
query parameter, seeded from ``sessionStorage`` by app.py). State is stored
one file per session so a refresh restores that session's data while a new
tab/session starts fresh and can never read or overwrite another session.

File location: ``.foodfounder_sessions/<sid>.json`` next to ``app.py``.
Override the directory with the ``FOODFOUNDER_SESSIONS_DIR`` environment
variable (used by tests). The legacy global ``.foodfounder_state.json`` from
older builds is never read, written, or deleted.

Schema (version 1)::

    {
      "version": 1,
      "product": {name, category, batch_size, batch_unit, budget} | null,
      "ingredients": [{Ingredient, Quantity, Unit, "Price per unit (INR)"}, ...] | null,
      "calculator_inputs": {packaging_cost, labour_cost, energy_cost, other_cost,
                            saleable_packets, selling_price} | null,
      "cost_result": { ...serialized CostResult... } | null,
      "chat_history": [{role, text}, ...] | null
    }

Recovery behaviour: a missing, empty, malformed, or wrong-version file loads
as empty defaults (the session simply starts fresh). Saves are atomic and are
skipped when there is nothing meaningful to store, so a valid saved file is
never overwritten with empty defaults. Old session files are pruned to the
most recent MAX_SESSION_FILES. No API keys or secrets are ever stored.
"""

import json
import math
import os
import re
from pathlib import Path

from services.calculator import CostResult, Ingredient

SCHEMA_VERSION = 1

MAX_SESSION_FILES = 20

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

INGREDIENT_COLUMNS = ["Ingredient", "Quantity", "Unit", "Price per unit (INR)"]

_CALCULATOR_INPUT_KEYS = (
    "packaging_cost",
    "labour_cost",
    "energy_cost",
    "other_cost",
    "selling_price",
)


def is_valid_session_id(value):
    """Return True when ``value`` is a safe session id (no path traversal)."""
    return isinstance(value, str) and bool(SESSION_ID_RE.match(value))


def valid_session_id(value):
    """Return the session id when valid, else None."""
    if is_valid_session_id(value):
        return value
    return None


def _sessions_dir():
    env = os.environ.get("FOODFOUNDER_SESSIONS_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / ".foodfounder_sessions"


def _state_path(sid):
    return _sessions_dir() / f"{sid}.json"


def _prune_sessions():
    """Keep only the most recent MAX_SESSION_FILES session files."""
    sessions_dir = _sessions_dir()
    try:
        files = [
            entry
            for entry in sessions_dir.iterdir()
            if entry.is_file() and entry.suffix == ".json"
        ]
    except OSError:
        return
    if len(files) <= MAX_SESSION_FILES:
        return
    files.sort(key=lambda entry: entry.stat().st_mtime, reverse=True)
    for entry in files[MAX_SESSION_FILES:]:
        try:
            entry.unlink()
        except OSError:
            pass


def _is_finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def _empty_state():
    return {
        "version": SCHEMA_VERSION,
        "product": None,
        "ingredients": None,
        "calculator_inputs": None,
        "cost_result": None,
        "chat_history": None,
    }


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def _dump_product(product):
    if not isinstance(product, dict):
        return None
    name = str(product.get("name") or "").strip()
    if not name:
        return None
    category = str(product.get("category") or "").strip() or "Other"
    batch_size = product.get("batch_size")
    if not _is_finite_number(batch_size) or float(batch_size) <= 0:
        return None
    batch_unit = str(product.get("batch_unit") or "").strip() or "unit"
    budget = product.get("budget")
    if not _is_finite_number(budget) or float(budget) < 0:
        budget = 0.0
    return {
        "name": name,
        "category": category,
        "batch_size": float(batch_size),
        "batch_unit": batch_unit,
        "budget": float(budget),
    }


def _load_product(raw):
    return _dump_product(raw)


# ---------------------------------------------------------------------------
# Ingredients (records matching the data_editor columns)
# ---------------------------------------------------------------------------

def _dump_ingredients(rows):
    if not isinstance(rows, list):
        return None
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Ingredient") or "").strip()
        if not name:
            continue
        quantity = row.get("Quantity")
        if not _is_finite_number(quantity) or float(quantity) < 0:
            quantity = 0.0
        unit = str(row.get("Unit") or "unit").strip() or "unit"
        price = row.get("Price per unit (INR)")
        if not _is_finite_number(price) or float(price) < 0:
            price = 0.0
        cleaned.append(
            {
                "Ingredient": name,
                "Quantity": float(quantity),
                "Unit": unit,
                "Price per unit (INR)": float(price),
            }
        )
    return cleaned or None


def _load_ingredients(raw):
    return _dump_ingredients(raw)


# ---------------------------------------------------------------------------
# Calculator inputs
# ---------------------------------------------------------------------------

def _dump_calculator_inputs(inputs):
    if not isinstance(inputs, dict):
        return None
    cleaned = {}
    for key in _CALCULATOR_INPUT_KEYS:
        value = inputs.get(key)
        if _is_finite_number(value) and float(value) >= 0:
            cleaned[key] = float(value)
    packets = inputs.get("saleable_packets")
    try:
        packets_int = int(packets)
        if packets_int >= 1 and float(packets) == packets_int:
            cleaned["saleable_packets"] = packets_int
    except (TypeError, ValueError):
        pass
    return cleaned or None


def _load_calculator_inputs(raw):
    return _dump_calculator_inputs(raw)


# ---------------------------------------------------------------------------
# Cost result (serialized CostResult dataclass)
# ---------------------------------------------------------------------------

def _dump_cost_result(result):
    if not isinstance(result, CostResult):
        return None
    try:
        return {
            "product_name": str(result.product_name),
            "product_category": str(result.product_category),
            "batch_size": float(result.batch_size),
            "batch_unit": str(result.batch_unit),
            "ingredients": [
                {
                    "name": str(ing.name),
                    "quantity": float(ing.quantity),
                    "unit": str(ing.unit),
                    "price_per_unit": float(ing.price_per_unit),
                }
                for ing in (result.ingredients or ())
            ],
            "ingredient_costs": [
                {"name": str(name), "cost": float(cost)}
                for name, cost in (result.ingredient_costs or ())
            ],
            "total_ingredient_cost": float(result.total_ingredient_cost),
            "packaging_cost": float(result.packaging_cost),
            "labour_cost": float(result.labour_cost),
            "energy_cost": float(result.energy_cost),
            "other_cost": float(result.other_cost),
            "total_production_cost": float(result.total_production_cost),
            "saleable_packets": int(result.saleable_packets),
            "cost_per_packet": float(result.cost_per_packet),
            "selling_price": float(result.selling_price),
            "profit_per_packet": float(result.profit_per_packet),
            "profit_margin_pct": (
                float(result.profit_margin_pct)
                if result.profit_margin_pct is not None
                else None
            ),
            "batch_profit": float(result.batch_profit),
        }
    except (TypeError, ValueError):
        return None


def _load_cost_result(raw):
    if not isinstance(raw, dict):
        return None
    try:
        ingredients = tuple(
            Ingredient(
                name=str(item["name"]),
                quantity=float(item["quantity"]),
                unit=str(item.get("unit") or "unit"),
                price_per_unit=float(item["price_per_unit"]),
            )
            for item in raw.get("ingredients") or []
            if isinstance(item, dict)
        )
        ingredient_costs = tuple(
            (str(item["name"]), float(item["cost"]))
            for item in raw.get("ingredient_costs") or []
            if isinstance(item, dict)
        )
        margin = raw.get("profit_margin_pct")
        return CostResult(
            product_name=str(raw["product_name"]),
            product_category=str(raw["product_category"]),
            batch_size=float(raw["batch_size"]),
            batch_unit=str(raw["batch_unit"]),
            ingredients=ingredients,
            ingredient_costs=ingredient_costs,
            total_ingredient_cost=float(raw["total_ingredient_cost"]),
            packaging_cost=float(raw["packaging_cost"]),
            labour_cost=float(raw["labour_cost"]),
            energy_cost=float(raw["energy_cost"]),
            other_cost=float(raw["other_cost"]),
            total_production_cost=float(raw["total_production_cost"]),
            saleable_packets=int(raw["saleable_packets"]),
            cost_per_packet=float(raw["cost_per_packet"]),
            selling_price=float(raw["selling_price"]),
            profit_per_packet=float(raw["profit_per_packet"]),
            profit_margin_pct=float(margin) if margin is not None else None,
            batch_profit=float(raw["batch_profit"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def _dump_chat_history(history):
    if not isinstance(history, list):
        return None
    cleaned = []
    for turn in history:
        if not isinstance(turn, dict):
            continue
        role = "user" if turn.get("role") == "user" else "model"
        text = str(turn.get("text") or "").strip()
        if text:
            cleaned.append({"role": role, "text": text})
    return cleaned or None


def _load_chat_history(raw):
    return _dump_chat_history(raw)


# ---------------------------------------------------------------------------
# Public load / save
# ---------------------------------------------------------------------------

def load_state(sid):
    """Load and validate saved state for a session. Never raises.

    An invalid/missing session id, or a missing/malformed file, yields empty
    defaults so the session starts fresh.
    """
    if not is_valid_session_id(sid):
        return _empty_state()
    state_path = _state_path(sid)
    try:
        raw = state_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _empty_state()
    if not raw.strip():
        return _empty_state()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_state()
    if not isinstance(data, dict):
        return _empty_state()
    if data.get("version") != SCHEMA_VERSION:
        return _empty_state()
    return {
        "version": SCHEMA_VERSION,
        "product": _load_product(data.get("product")),
        "ingredients": _load_ingredients(data.get("ingredients")),
        "calculator_inputs": _load_calculator_inputs(data.get("calculator_inputs")),
        "cost_result": _load_cost_result(data.get("cost_result")),
        "chat_history": _load_chat_history(data.get("chat_history")),
    }


def has_content(data):
    if not isinstance(data, dict):
        return False
    return any(
        [
            data.get("product"),
            data.get("ingredients"),
            data.get("calculator_inputs"),
            data.get("cost_result"),
            data.get("chat_history"),
        ]
    )


def save_state(data, sid):
    """Atomically save state for a session. Returns True if written.

    Returns False (and writes nothing) when the session id is invalid or
    there is nothing meaningful to store.
    """
    if not is_valid_session_id(sid):
        return False
    if not has_content(data):
        return False
    state_path = _state_path(sid)
    payload = {
        "version": SCHEMA_VERSION,
        "product": _dump_product(data.get("product")),
        "ingredients": _dump_ingredients(data.get("ingredients")),
        "calculator_inputs": _dump_calculator_inputs(data.get("calculator_inputs")),
        "cost_result": _dump_cost_result(data.get("cost_result")),
        "chat_history": _dump_chat_history(data.get("chat_history")),
    }
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, state_path)
    except OSError:
        return False
    _prune_sessions()
    return True


# ---------------------------------------------------------------------------
# Session-state bridge (used by app.py)
# ---------------------------------------------------------------------------

def restore_session_state(session_state, sid):
    """Populate ``session_state`` from this session's saved file.

    Only missing keys are filled, so a live session's newer data always wins
    over an older file. An invalid session id is a no-op (fresh session).
    Returns the loaded state dict.
    """
    saved = load_state(sid)

    product = saved.get("product")
    if product and "product" not in session_state:
        session_state["product"] = product

    chat = saved.get("chat_history")
    if chat and "chat_history" not in session_state:
        session_state["chat_history"] = chat

    result = saved.get("cost_result")
    if result and "cost_result" not in session_state:
        session_state["cost_result"] = result

    ingredients = saved.get("ingredients")
    if ingredients and "ingredients_df" not in session_state:
        import pandas as pd

        df = pd.DataFrame(ingredients, columns=INGREDIENT_COLUMNS)
        session_state["ingredients_df"] = df
        session_state["ingredients_seed"] = df.copy()

    inputs = saved.get("calculator_inputs") or {}
    for key in list(_CALCULATOR_INPUT_KEYS) + ["saleable_packets"]:
        if key in inputs and key not in session_state:
            session_state[key] = inputs[key]

    return saved


def capture_session_state(session_state):
    """Build a saveable snapshot from the current Streamlit session."""
    df = session_state.get("ingredients_df")
    ingredients = None
    if df is not None and hasattr(df, "to_dict"):
        try:
            ingredients = df.to_dict("records")
        except Exception:
            ingredients = None

    inputs = {}
    for key in list(_CALCULATOR_INPUT_KEYS) + ["saleable_packets"]:
        value = session_state.get(key)
        if value is not None:
            inputs[key] = value

    return {
        "product": session_state.get("product"),
        "ingredients": ingredients,
        "calculator_inputs": inputs or None,
        "cost_result": session_state.get("cost_result"),
        "chat_history": session_state.get("chat_history"),
    }
