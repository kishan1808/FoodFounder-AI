"""LLM-backed food business assistant using the Groq API.

Kept separate from Streamlit so it can be unit-tested with a fake client.
"""

import os

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

REQUEST_TIMEOUT_SECONDS = 30

MAX_RETRIES = 2
MAX_OUTPUT_TOKENS = 2048

MISSING_KEY_MESSAGE = (
    "No API key configured. Get a free key at https://console.groq.com/keys "
    "then either:\n"
    "1) PowerShell (current session): `$env:GROQ_API_KEY='your-key'` then restart the app, or\n"
    "2) Add `GROQ_API_KEY = 'your-key'` to `.streamlit/secrets.toml` "
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
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st

        if "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"]).strip()
    except Exception:
        pass
    return None


def build_message_history(history, message):
    """Return the trimmed [(role, text), ...] turns, including the new user message.

    Malformed history is tolerated: non-list history is treated as empty, and
    entries that are not dicts or have no usable text are skipped.
    """
    user_text = str(message or "").strip()
    if not user_text:
        raise AssistantError("Please type a message before sending.")

    recent = history[-12:] if isinstance(history, (list, tuple)) else []

    turns = []
    for turn in recent:
        if not isinstance(turn, dict):
            continue
        role = "user" if turn.get("role") == "user" else "model"
        text = str(turn.get("text") or "").strip()
        if text:
            turns.append((role, text))

    turns.append(("user", user_text))
    return turns


def _retry_after_seconds(exc):
    """Return the Retry-After header (seconds) from an API error, if present."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get("retry-after")
    except Exception:
        return None
    if value in (None, ""):
        return None
    try:
        seconds = int(str(value).strip())
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _friendly_error(exc):
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    message = str(exc)
    lowered = message.lower()

    if code == 429 or "429" in message or "rate limit" in lowered:
        retry_after = _retry_after_seconds(exc)
        if retry_after is not None:
            wait_hint = (
                f"about {retry_after} seconds"
                if retry_after < 120
                else f"about {retry_after // 60} minutes"
            )
            return AssistantError(
                "The AI service is rate-limited right now. "
                f"The service suggests waiting {wait_hint} before trying again."
            )
        return AssistantError(
            "The AI service is rate-limited right now. "
            "Wait about a minute and try again."
        )
    if "quota" in lowered:
        return AssistantError(
            "The AI service reported a quota limit. Try again later, or check your "
            "usage and limits in the Groq console (https://console.groq.com)."
        )
    if code == 503 or "overloaded" in lowered or "unavailable" in lowered:
        return AssistantError(
            "The AI service is temporarily overloaded because of high demand. "
            "This usually clears within a few minutes — please try again shortly."
        )
    if (
        code in (401, 403)
        or "invalid api key" in lowered
        or "api key" in lowered
        or "unauthenticated" in lowered
        or "permission" in lowered
    ):
        return AssistantError(
            "The AI service rejected the request. Check that your GROQ_API_KEY is "
            "correct and active (get a key at https://console.groq.com/keys)."
        )
    if "timeout" in lowered or "timed out" in lowered or "deadline" in lowered:
        return AssistantError(
            f"The AI service did not respond within {REQUEST_TIMEOUT_SECONDS} seconds. "
            "Check your internet connection and try again."
        )
    if (
        "unreachable" in lowered
        or "connection" in lowered
        or "temporary failure" in lowered
        or "name or service not known" in lowered
        or "getaddrinfo" in lowered
    ):
        return AssistantError(
            "Network problem while contacting the AI service. "
            "Check your internet connection and try again."
        )
    if (
        code == 404
        or "not found" in lowered
        or "model_decommissioned" in lowered
        or "decommissioned" in lowered
    ):
        return AssistantError(
            f"The requested AI model was not found. Check the GROQ_MODEL setting "
            f"(current default: {DEFAULT_MODEL}) and pick a current model from "
            "https://console.groq.com/docs/models."
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
            from groq import Groq
        except ImportError:
            raise AssistantError(
                "The 'groq' package is not installed. "
                "Run: .\\venv\\Scripts\\pip.exe install groq"
            )
        try:
            client = Groq(
                api_key=key,
                timeout=REQUEST_TIMEOUT_SECONDS,
                max_retries=MAX_RETRIES,
            )
        except Exception as exc:
            raise AssistantError(f"Could not start the AI client: {exc}") from exc

    system_instruction = SYSTEM_PROMPT
    if product_context:
        system_instruction += f"\n\nThe user's current product setup: {product_context}"

    messages = [{"role": "system", "content": system_instruction}]
    messages.extend(
        {"role": "user" if role == "user" else "assistant", "content": text}
        for role, text in turns
    )

    try:
        response = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=messages,
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
    except AssistantError:
        raise
    except Exception as exc:
        raise _friendly_error(exc) from exc

    text = None
    choices = getattr(response, "choices", None)
    if choices:
        text = getattr(getattr(choices[0], "message", None), "content", None)
    if not text or not str(text).strip():
        raise AssistantError("The AI returned an empty response. Please try again.")
    return str(text).strip()
