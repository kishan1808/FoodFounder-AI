"""Pure-Python cost calculation logic for FoodFounder AI.

This module has no Streamlit imports so it can be tested independently
and reused by the app, the report generator, or anything else.
"""

import math
from dataclasses import dataclass


class CalculatorError(ValueError):
    """Raised when calculator inputs are missing or invalid."""


@dataclass(frozen=True)
class Ingredient:
    name: str
    quantity: float
    unit: str
    price_per_unit: float

    @property
    def cost(self) -> float:
        return self.quantity * self.price_per_unit


@dataclass(frozen=True)
class CostResult:
    product_name: str
    product_category: str
    batch_size: float
    batch_unit: str
    ingredients: tuple
    ingredient_costs: tuple
    total_ingredient_cost: float
    packaging_cost: float
    labour_cost: float
    energy_cost: float
    other_cost: float
    total_production_cost: float
    saleable_packets: int
    cost_per_packet: float
    selling_price: float
    profit_per_packet: float
    profit_margin_pct: object
    batch_profit: float


def _require_finite_number(value, label, minimum=0.0, allow_zero=True):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CalculatorError(f"{label} must be a number (got {value!r}).")

    if math.isnan(number) or math.isinf(number):
        raise CalculatorError(f"{label} must be a finite number (got {number}).")

    if number < minimum or (number == minimum and not allow_zero):
        raise CalculatorError(f"{label} must be greater than {minimum} (got {number}).")

    return number


def calculate_ingredient_cost(quantity, price_per_unit):
    quantity = _require_finite_number(quantity, "Ingredient quantity")
    price = _require_finite_number(price_per_unit, "Ingredient price per unit")
    return quantity * price


def _build_ingredients(ingredients):
    if not ingredients:
        raise CalculatorError("Add at least one ingredient before calculating.")

    built = []
    for index, item in enumerate(ingredients, start=1):
        name = str(item.name or "").strip()
        if not name:
            raise CalculatorError(f"Ingredient row {index} is missing a name.")

        quantity = _require_finite_number(item.quantity, f"Quantity for '{name}'")
        price = _require_finite_number(item.price_per_unit, f"Price for '{name}'")
        unit = str(item.unit or "").strip() or "unit"

        built.append(Ingredient(name=name, quantity=quantity, unit=unit, price_per_unit=price))

    if not any(ing.quantity > 0 for ing in built):
        raise CalculatorError("At least one ingredient must have a quantity greater than zero.")

    return built


def calculate_batch(
    product_name,
    product_category,
    batch_size,
    batch_unit,
    ingredients,
    packaging_cost,
    labour_cost,
    energy_cost,
    other_cost,
    saleable_packets,
    selling_price,
):
    """Calculate the full cost and profit breakdown for one production batch."""

    name = str(product_name or "").strip()
    if not name:
        raise CalculatorError("Product name is required.")

    category = str(product_category or "").strip() or "Other"
    batch_size_value = _require_finite_number(batch_size, "Batch size", minimum=0.0, allow_zero=False)
    batch_unit_value = str(batch_unit or "").strip() or "unit"

    built_ingredients = _build_ingredients(ingredients)

    packaging = _require_finite_number(packaging_cost, "Packaging cost")
    labour = _require_finite_number(labour_cost, "Labour cost")
    energy = _require_finite_number(energy_cost, "Energy cost")
    other = _require_finite_number(other_cost, "Other production cost")

    if isinstance(saleable_packets, bool):
        raise CalculatorError(
            f"Saleable packets must be a whole number, not a True/False value (got {saleable_packets!r})."
        )

    try:
        packets = int(saleable_packets)
    except (TypeError, ValueError, OverflowError):
        raise CalculatorError(f"Saleable packets must be a whole number (got {saleable_packets!r}).")

    if float(saleable_packets) != packets:
        raise CalculatorError(f"Saleable packets must be a whole number (got {saleable_packets!r}).")

    if packets <= 0:
        raise CalculatorError(f"Saleable packets must be at least 1 to avoid division by zero (got {packets}).")

    price = _require_finite_number(selling_price, "Selling price per packet")

    ingredient_costs = tuple((ing.name, ing.cost) for ing in built_ingredients)
    total_ingredient_cost = sum(cost for _, cost in ingredient_costs)
    total_production_cost = total_ingredient_cost + packaging + labour + energy + other
    cost_per_packet = total_production_cost / packets
    profit_per_packet = price - cost_per_packet

    if price > 0:
        profit_margin_pct = (profit_per_packet / price) * 100
    else:
        profit_margin_pct = None

    batch_profit = (price * packets) - total_production_cost

    return CostResult(
        product_name=name,
        product_category=category,
        batch_size=batch_size_value,
        batch_unit=batch_unit_value,
        ingredients=tuple(built_ingredients),
        ingredient_costs=ingredient_costs,
        total_ingredient_cost=total_ingredient_cost,
        packaging_cost=packaging,
        labour_cost=labour,
        energy_cost=energy,
        other_cost=other,
        total_production_cost=total_production_cost,
        saleable_packets=packets,
        cost_per_packet=cost_per_packet,
        selling_price=price,
        profit_per_packet=profit_per_packet,
        profit_margin_pct=profit_margin_pct,
        batch_profit=batch_profit,
    )
