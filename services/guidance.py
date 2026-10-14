"""Structured packaging, process, and trial guidance for FoodFounder AI.

Content is conservative checklist guidance for small entrepreneurs.
It is not legal advice and does not claim regulatory compliance.
All external links were verified reachable (HTTP 200) before inclusion.
"""

PACKAGING_CHECKLIST = [
    (
        "Barrier against moisture",
        "Moisture softens crisp products. Discuss moisture-barrier films "
        "(for example metallised or foil-lined pouches) with your packaging supplier.",
    ),
    (
        "Barrier against oxygen",
        "Oxygen can speed staling and oil spoilage. Ask suppliers about low-transmission "
        "films, nitrogen flushing, or oxygen absorbers for oil-rich snacks.",
    ),
    (
        "Protection from light",
        "Light can degrade oils and colours. Opaque or metallised packaging helps "
        "for oil-rich or colour-sensitive products.",
    ),
    (
        "Sealing quality",
        "Use a reliable heat sealer (impulse or continuous band sealer). "
        "Squeeze-test sealed packs for leaks before packing full batches.",
    ),
    (
        "Food-grade material",
        "Buy food-contact-grade packaging from traceable suppliers. "
        "Do not use industrial-grade material for food products.",
    ),
    (
        "Pack size and fill weight",
        "Match pack size to your target price point and customer. "
        "Use a calibrated scale so every pack has a consistent net weight.",
    ),
    (
        "Labelling basics",
        "Plan for product name, net quantity, ingredient list, batch/lot details, "
        "date marking, and manufacturer details. Confirm current FSSAI labelling "
        "rules before printing — rules change over time.",
    ),
    (
        "Storage guidance on pack",
        "Add storage statements (for example 'store in a cool, dry place') "
        "only after checking that they match the product's actual behaviour.",
    ),
]

PROCESS_CHECKLIST = [
    (
        "Raw material checks",
        "Accept materials only if fresh, undamaged, and within date. "
        "Record supplier name and purchase date for each batch.",
    ),
    (
        "Washing and preparation",
        "Wash produce with clean potable water. Trim and cut uniformly "
        "so pieces cook or dry evenly.",
    ),
    (
        "Record process settings",
        "Write down times, temperatures, and machine settings for every batch "
        "(frying temperature, drying time, and so on) so results are repeatable.",
    ),
    (
        "Cooling before packing",
        "Cool products fully before packing. Packing warm product causes "
        "condensation inside the pack, which ruins crispness.",
    ),
    (
        "Quality checks each batch",
        "Check colour, texture, taste, and foreign objects against a simple "
        "written standard. Reject or rework batches that miss the standard.",
    ),
    (
        "Hygiene and personal care",
        "Clean work surfaces, wash hands regularly, and use hairnets, gloves, "
        "and aprons as appropriate. Keep the area pest-free.",
    ),
    (
        "Potable water and clean equipment",
        "Use clean potable water for washing and processing. "
        "Clean and dry equipment between batches.",
    ),
    (
        "Batch traceability",
        "Keep one page per batch: date, ingredient lots used, quantity produced, "
        "checks performed, and where the batch was sold.",
    ),
]

TRIAL_CHECKLIST = [
    (
        "Define the trial goal",
        "Write down exactly what this trial tests, for example: "
        "'Does the product stay crisp for 7 days in pouch X?'",
    ),
    (
        "Make one small batch",
        "Use the cost calculator to plan a trial-sized batch and note every quantity.",
    ),
    (
        "Change only one thing",
        "If you change recipe, temperature, or pack material, change only one variable "
        "per trial so you know what caused the result.",
    ),
    (
        "Record measurements immediately",
        "Note weights, times, temperatures, and sensory observations right away, "
        "not from memory later.",
    ),
    (
        "Taste and inspect",
        "Evaluate with two or three honest testers against your written criteria.",
    ),
    (
        "Pack and observe over time",
        "Pack some units and check them at planned intervals for crispness, "
        "colour, aroma, and clumping.",
    ),
    (
        "Decide the next step",
        "Keep the winner, adjust one variable, or repeat the trial. "
        "Document the decision.",
    ),
    (
        "Use a lab when needed",
        "Before making safety, nutrition, or shelf-life claims, or for wider sale, "
        "consult a food technologist and a competent food laboratory.",
    ),
]

FSSAI_RESOURCES = [
    (
        "FSSAI official website",
        "https://www.fssai.gov.in/",
        "Home of the Food Safety and Standards Authority of India — "
        "regulations, announcements, and guidance.",
    ),
    (
        "Licensing and Registration",
        "https://www.fssai.gov.in/cms/licensing-registration.php",
        "Official FSSAI page explaining licensing and registration for food businesses.",
    ),
    (
        "FoSCoS licensing portal",
        "https://foscos.fssai.gov.in/",
        "The official online portal (FoSCoS) where food business operators "
        "apply for licences and registration.",
    ),
    (
        "Food Safety Connect",
        "https://www.fssai.gov.in/food-safety-connect",
        "FSSAI's consumer and business connect portal with resources and grievance options.",
    ),
]

DISCLAIMER = (
    "These checklists are practical starting points for small entrepreneurs. "
    "They are not legal advice and do not certify compliance with any regulation. "
    "Verify current FSSAI rules and consult qualified experts before selling."
)


def checklist_as_markdown(items):
    lines = []
    for title, detail in items:
        lines.append(f"- [ ] **{title}** — {detail}")
    return "\n".join(lines)


def resources_as_markdown():
    lines = []
    for title, url, detail in FSSAI_RESOURCES:
        lines.append(f"- **[{title}]({url})** — {detail}")
    return "\n".join(lines)
