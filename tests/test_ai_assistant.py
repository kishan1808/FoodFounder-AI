"""Unit tests for ai_assistant.py using a fake client (no network calls)."""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from services import ai_assistant
from services.ai_assistant import AssistantError, build_message_history, chat

FRIENDLY_ERROR = ai_assistant._friendly_error


def make_response(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


class FakeCompletions:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.last_call = None

    def create(self, model=None, messages=None, max_completion_tokens=None):
        self.last_call = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_completion_tokens,
        }
        if self.error is not None:
            raise self.error
        return make_response(self.text)


class FakeClient:
    def __init__(self, text=None, error=None):
        self.chat = SimpleNamespace(completions=FakeCompletions(text=text, error=error))


class FakeAPIError(Exception):
    """Mimics groq.APIStatusError: carries status_code and an optional response."""

    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class TestBuildMessageHistory(unittest.TestCase):
    def test_appends_user_message(self):
        turns = build_message_history([], "How should I package banana chips?")
        self.assertEqual(turns, [("user", "How should I package banana chips?")])

    def test_keeps_prior_conversation(self):
        history = [
            {"role": "user", "text": "Hello"},
            {"role": "model", "text": "Hi!"},
        ]
        turns = build_message_history(history, "Packaging tips?")
        self.assertEqual(turns[0], ("user", "Hello"))
        self.assertEqual(turns[1], ("model", "Hi!"))
        self.assertEqual(turns[2], ("user", "Packaging tips?"))

    def test_trims_to_last_twelve_plus_new(self):
        history = [
            {"role": "user" if i % 2 == 0 else "model", "text": f"msg {i}"}
            for i in range(20)
        ]
        turns = build_message_history(history, "latest question")
        self.assertEqual(len(turns), 13)
        self.assertEqual(turns[-1], ("user", "latest question"))

    def test_empty_message_rejected(self):
        with self.assertRaises(AssistantError):
            build_message_history([], "   ")

    def test_blank_history_entries_skipped(self):
        history = [{"role": "user", "text": ""}, {"role": "model", "text": "ok"}]
        turns = build_message_history(history, "next")
        self.assertEqual(turns[0], ("model", "ok"))

    def test_non_dict_history_entries_skipped(self):
        """Malformed entries (strings, ints) must not crash the app."""
        history = ["just a string", 42, {"role": "user", "text": "real"}]
        turns = build_message_history(history, "next")
        self.assertEqual(turns[0], ("user", "real"))
        self.assertEqual(turns[1], ("user", "next"))

    def test_non_list_history_treated_as_empty(self):
        self.assertEqual(build_message_history("hello", "hi"), [("user", "hi")])
        self.assertEqual(build_message_history(123, "hi"), [("user", "hi")])

    def test_none_role_maps_to_model(self):
        turns = build_message_history([{"role": None, "text": "x"}], "hi")
        self.assertEqual(turns[0], ("model", "x"))

    def test_system_and_assistant_roles_map_to_model(self):
        turns = build_message_history(
            [{"role": "system", "text": "s"}, {"role": "assistant", "text": "a"}], "hi"
        )
        self.assertEqual(turns[0], ("model", "s"))
        self.assertEqual(turns[1], ("model", "a"))

    def test_non_string_text_coerced(self):
        turns = build_message_history([{"role": "user", "text": 123}], "hi")
        self.assertEqual(turns[0], ("user", "123"))


class TestChatWithFakeClient(unittest.TestCase):
    def test_returns_reply_text(self):
        client = FakeClient(text="Use metallised pouches with a strong heat seal.")
        reply = chat("How should I package banana chips?", client=client)
        self.assertEqual(reply, "Use metallised pouches with a strong heat seal.")

    def test_sends_history_and_system_prompt(self):
        client = FakeClient(text="reply")
        history = [
            {"role": "user", "text": "Hello"},
            {"role": "model", "text": "Hi!"},
        ]
        chat("What next?", history=history, client=client)

        call = client.chat.completions.last_call
        roles = [message["role"] for message in call["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertIn("not scientifically validated", call["messages"][0]["content"])
        self.assertEqual(call["messages"][1], {"role": "user", "content": "Hello"})
        self.assertEqual(call["messages"][2], {"role": "assistant", "content": "Hi!"})

    def test_product_context_included(self):
        client = FakeClient(text="reply")
        chat(
            "Any tips?",
            product_context="Banana Chips (Snacks), batch 10 kg",
            client=client,
        )
        system_message = client.chat.completions.last_call["messages"][0]["content"]
        self.assertIn("Banana Chips (Snacks)", system_message)

    def test_api_error_mapped_to_friendly_message(self):
        client = FakeClient(
            error=FakeAPIError("429 Rate limit reached", status_code=429)
        )
        with self.assertRaises(AssistantError) as ctx:
            chat("Hello", client=client)
        self.assertIn("rate-limited", str(ctx.exception))

    def test_empty_reply_raises(self):
        client = FakeClient(text="")
        with self.assertRaises(AssistantError):
            chat("Hello", client=client)

    def test_whitespace_only_reply_raises(self):
        client = FakeClient(text="   ")
        with self.assertRaises(AssistantError):
            chat("Hello", client=client)

    def test_missing_key_raises_with_instructions(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(ai_assistant, "get_api_key", return_value=None):
                with self.assertRaises(AssistantError) as ctx:
                    chat("Hello")
        self.assertIn("console.groq.com/keys", str(ctx.exception))

    def test_empty_question_raises(self):
        client = FakeClient(text="reply")
        with self.assertRaises(AssistantError):
            chat("  ", client=client)


class TestFriendlyError(unittest.TestCase):
    def test_rate_limit(self):
        message = str(FRIENDLY_ERROR(FakeAPIError("Rate limit reached", status_code=429)))
        self.assertIn("rate-limited", message)

    def test_rate_limit_with_retry_after_header(self):
        response = SimpleNamespace(headers={"retry-after": "25"})
        message = str(
            FRIENDLY_ERROR(
                FakeAPIError("Rate limit reached", status_code=429, response=response)
            )
        )
        self.assertIn("25 seconds", message)

    def test_bad_key(self):
        message = str(
            FRIENDLY_ERROR(FakeAPIError("Invalid API Key", status_code=401))
        )
        self.assertIn("GROQ_API_KEY", message)
        self.assertIn("console.groq.com/keys", message)

    def test_overload_503(self):
        message = str(
            FRIENDLY_ERROR(FakeAPIError("Server is currently overloaded", status_code=503))
        )
        self.assertIn("temporarily overloaded", message)

    def test_overload_not_confused_with_rate_limit(self):
        message = str(
            FRIENDLY_ERROR(FakeAPIError("Server is currently overloaded", status_code=503))
        )
        self.assertNotIn("rate-limited", message)

    def test_rate_limit_not_confused_with_overload(self):
        message = str(FRIENDLY_ERROR(FakeAPIError("Rate limit reached", status_code=429)))
        self.assertNotIn("temporarily overloaded", message)

    def test_timeout(self):
        message = str(FRIENDLY_ERROR(Exception("Request timed out")))
        self.assertIn("did not respond within", message)

    def test_network(self):
        message = str(FRIENDLY_ERROR(Exception("All connection attempts failed")))
        self.assertIn("Network problem", message)

    def test_model_not_found(self):
        message = str(
            FRIENDLY_ERROR(
                FakeAPIError("The model `old-model` does not exist", status_code=404)
            )
        )
        self.assertIn("GROQ_MODEL", message)
        self.assertIn(ai_assistant.DEFAULT_MODEL, message)

    def test_model_decommissioned(self):
        message = str(
            FRIENDLY_ERROR(
                FakeAPIError("model_decommissioned", status_code=400)
            )
        )
        self.assertIn("GROQ_MODEL", message)

    def test_quota(self):
        message = str(FRIENDLY_ERROR(Exception("Quota exceeded for the day")))
        self.assertIn("quota limit", message)

    def test_generic(self):
        message = str(FRIENDLY_ERROR(Exception("boom")))
        self.assertIn("boom", message)


class TestSystemPrompt(unittest.TestCase):
    def test_contains_required_disclaimers(self):
        prompt = ai_assistant.SYSTEM_PROMPT
        self.assertIn("not scientifically validated", prompt)
        self.assertIn("FSSAI", prompt)
        self.assertIn("PRELIMINARY", prompt)


class TestModelConfig(unittest.TestCase):
    def test_default_model_is_current_supported(self):
        """openai/gpt-oss-120b is a Groq production model (docs, Oct 2026)."""
        self.assertEqual(ai_assistant.DEFAULT_MODEL, "openai/gpt-oss-120b")

    def test_groq_model_env_var_is_respected(self):
        """GROQ_MODEL overrides the default (verified via subprocess)."""
        import subprocess
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from services import ai_assistant; print(ai_assistant.DEFAULT_MODEL)",
            ],
            cwd=str(project_root),
            env={**os.environ, "GROQ_MODEL": "groq-test-override-123"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "groq-test-override-123")

    def test_request_timeout_is_set(self):
        self.assertEqual(ai_assistant.REQUEST_TIMEOUT_SECONDS, 30)

    def test_retries_are_bounded(self):
        self.assertEqual(ai_assistant.MAX_RETRIES, 2)


class TestClientConfiguration(unittest.TestCase):
    def test_client_receives_timeout_retries_and_key(self):
        recorded = {}

        class RecordingGroq:
            def __init__(self, **kwargs):
                recorded.update(kwargs)
                self.chat = SimpleNamespace(
                    completions=FakeCompletions(text="ok")
                )

        import groq as groq_module

        with mock.patch.object(groq_module, "Groq", RecordingGroq):
            reply = chat("Hello", api_key="fake-test-key-not-real")

        self.assertEqual(reply, "ok")
        self.assertEqual(recorded["timeout"], 30)
        self.assertEqual(recorded["max_retries"], 2)
        self.assertEqual(recorded["api_key"], "fake-test-key-not-real")

    def test_request_sends_converted_roles_and_model(self):
        client = FakeClient(text="reply")
        history = [{"role": "model", "text": "Earlier answer"}]
        chat("Follow-up", history=history, client=client)
        call = client.chat.completions.last_call
        self.assertEqual(call["model"], ai_assistant.DEFAULT_MODEL)
        roles = [m["role"] for m in call["messages"]]
        self.assertIn("assistant", roles)
        self.assertNotIn("model", roles)
        self.assertEqual(call["max_completion_tokens"], ai_assistant.MAX_OUTPUT_TOKENS)


if __name__ == "__main__":
    unittest.main()
