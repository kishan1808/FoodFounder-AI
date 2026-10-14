"""LLM-backed food business assistant using the Google Gemini API.

Kept separate from Streamlit so it can be unit-tested with a fake client.
"""

import os

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

MISSING_KEY_MESSAGE = (
    "No API key configured. Get a free key at https://aistudio.google.com/apikey "
    "then either:\n"
    "1) PowerShell (current session): `$env:GEMINI_API_KEY='your-key'` then restart the app, or\n"
    "2) Add `GEMINI_API_KEY = 'your-key'` to `.streamlit/secrets.toml` "
    "(this file is ignored by Git) and restart the app."
)

SYSTEM_PROMPT = """You are FoodFounder AI, a helpful assistant for small-scale food entrepreneurs, especially in India.

You help with:
- Preliminary food formulation ideas and ingredient alternatives
- Small-scale food business planning, costing concepts, and pricing thinking
- Packaging options for common food products (moisture, oxygen and light protection, sealing, storage)
- Basic food-processing workflows (washing, cutting, cooking, drying, frying, cooling, packing)
- General food-safety and hygiene guidance
- Pointing users to official FSSAI resources for licensing and labelling (https://www.fssai.gov.in/)

Rules you must follow:
- All formulation suggestions are PRELIMINARY STARTING POINTS only. They are not scientifically validated, not lab-tested, and not guaranteed safe or shelf-stable. Say this clearly when you give formulations or shelf-life ideas.
- Never invent legal requirements and never claim a user's product is compliant or licensed. Direct users to official FSSAI resources instead.
- Do not present unverified shelf-life, nutritional, or microbiological claims as established facts. Recommend trials and lab testing.
- Encourage small trial batches, written documentation, and review by a food technologist or lab before selling.
- Be practical, concise, and beginner-friendly. Use simple English. Use Indian context (rupees, FSSAI, commonly available local ingredients) where relevant.
- If asked for medical or nutrition claims, give general information only and recommend expert advice.
"""


class AssistantError(Exception):
    """Friendly, user-facing assistant failure."""


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st

        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return None


def build_message_history(history, message):
    """Return the trimmed [(role, text), ...] turns, including the new user message."""
    user_text = str(message or "").strip()
    if not user_text:
        raise AssistantError("Please type a message before sending.")

    turns = []
    for turn in (history or [])[-12:]:
        role = "user" if turn.get("role") == "user" else "model"
        text = str(turn.get("text") or "").strip()
        if text:
            turns.append((role, text))

    turns.append(("user", user_text))
    return turns


def _friendly_error(exc):
    code = getattr(exc, "code", None)
    message = str(exc)
    lowered = message.lower()

    if code == 429 or "429" in message or "resource_exhausted" in lowered or "rate limit" in lowered:
        return AssistantError(
            "The AI service is rate-limited right now (free-tier limits apply). "
            "Wait about a minute and try again."
        )
    if "quota" in lowered:
        return AssistantError(
            "Free-tier quota exceeded. Try again later, or check your limits in Google AI Studio."
        )
    if (
        code in (400, 401, 403)
        or "api key" in lowered
        or "api_key" in lowered
        or "unauthenticated" in lowered
        or "permission_denied" in lowered
        or "invalid argument" in lowered
    ):
        return AssistantError(
            "The AI service rejected the request. Check that your GEMINI_API_KEY is "
            "correct, active, and belongs to a Google AI Studio project."
        )
    if (
        "timeout" in lowered
        or "timed out" in lowered
        or "unreachable" in lowered
        or "connection" in lowered
        or "temporary failure" in lowered
    ):
        return AssistantError(
            "Network problem while contacting the AI service. "
            "Check your internet connection and try again."
        )
    return AssistantError(f"The AI service returned an error: {message[:200]}")


def chat(message, history=None, product_context=None, api_key=None, model=None, client=None):
    """Send one chat turn to the model and return the reply text."""
    key = api_key or get_api_key()
    if not key and client is None:
        raise AssistantError(MISSING_KEY_MESSAGE)

    turns = build_message_history(history, message)

    if client is None:
        try:
            from google import genai
        except ImportError:
            raise AssistantError(
                "The 'google-genai' package is not installed. "
                "Run: .\\venv\\Scripts\\pip.exe install google-genai"
            )
        try:
            client = genai.Client(api_key=key)
        except Exception as exc:
            raise AssistantError(f"Could not start the AI client: {exc}") from exc

    system_instruction = SYSTEM_PROMPT
    if product_context:
        system_instruction += f"\n\nThe user's current product setup: {product_context}"

    try:
        from google.genai import types

        contents = [
            types.Content(role=role, parts=[types.Part.from_text(text=text)])
            for role, text in turns
        ]
        response = client.models.generate_content(
            model=model or DEFAULT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )
    except AssistantError:
        raise
    except Exception as exc:
        raise _friendly_error(exc) from exc

    text = getattr(response, "text", None)
    if not text or not str(text).strip():
        raise AssistantError("The AI returned an empty response. Please try again.")
    return str(text).strip()
