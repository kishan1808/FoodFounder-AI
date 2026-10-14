"""Unit tests for ai_assistant.py using a fake client (no network calls)."""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from services import ai_assistant
from services.ai_assistant import AssistantError, build_message_history, chat

FRIENDLY_ERROR = ai_assistant._friendly_error


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.last_call = None

    def generate_content(self, model=None, contents=None, config=None):
        self.last_call = {"model": model, "contents": contents, "config": config}
        if self.error is not None:
            raise self.error
        return SimpleNamespace(text=self.text)


class FakeClient:
    def __init__(self, text=None, error=None):
        self.models = FakeModels(text=text, error=error)


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

        call = client.models.last_call
        roles = [content.role for content in call["contents"]]
        self.assertEqual(roles, ["user", "model", "user"])
        self.assertIn("not scientifically validated", call["config"].system_instruction)

    def test_product_context_included(self):
        client = FakeClient(text="reply")
        chat(
            "Any tips?",
            product_context="Banana Chips (Snacks), batch 10 kg",
            client=client,
        )
        instruction = client.models.last_call["config"].system_instruction
        self.assertIn("Banana Chips (Snacks)", instruction)

    def test_api_error_mapped_to_friendly_message(self):
        class FakeAPIError(Exception):
            def __init__(self, message, code=None):
                super().__init__(message)
                self.code = code

        client = FakeClient(error=FakeAPIError("429 RESOURCE_EXHAUSTED: rate limit", code=429))
        with self.assertRaises(AssistantError) as ctx:
            chat("Hello", client=client)
        self.assertIn("rate-limited", str(ctx.exception))

    def test_empty_reply_raises(self):
        client = FakeClient(text="")
        with self.assertRaises(AssistantError):
            chat("Hello", client=client)

    def test_missing_key_raises_with_instructions(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(ai_assistant, "get_api_key", return_value=None):
                with self.assertRaises(AssistantError) as ctx:
                    chat("Hello")
        self.assertIn("aistudio.google.com/apikey", str(ctx.exception))

    def test_empty_question_raises(self):
        client = FakeClient(text="reply")
        with self.assertRaises(AssistantError):
            chat("  ", client=client)


class TestFriendlyError(unittest.TestCase):
    def test_rate_limit(self):
        message = str(FRIENDLY_ERROR(Exception("429 RESOURCE_EXHAUSTED")))
        self.assertIn("rate-limited", message)

    def test_bad_key(self):
        message = str(FRIENDLY_ERROR(Exception("400 API_KEY_INVALID")))
        self.assertIn("GEMINI_API_KEY", message)

    def test_network(self):
        message = str(FRIENDLY_ERROR(Exception("connection timed out")))
        self.assertIn("internet connection", message)

    def test_generic(self):
        message = str(FRIENDLY_ERROR(Exception("boom")))
        self.assertIn("boom", message)


class TestSystemPrompt(unittest.TestCase):
    def test_contains_required_disclaimers(self):
        prompt = ai_assistant.SYSTEM_PROMPT
        self.assertIn("not scientifically validated", prompt)
        self.assertIn("FSSAI", prompt)
        self.assertIn("PRELIMINARY", prompt)


if __name__ == "__main__":
    unittest.main()
