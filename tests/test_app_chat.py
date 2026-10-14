"""UI tests for the AI Guidance chat page using Streamlit's AppTest (no network).

ai_assistant.chat is always mocked, so no API key or internet access is needed.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

from services.ai_assistant import AssistantError

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def isolate_state_file():
    """Point the app's persistence at a fresh (nonexistent) temp file."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="ff_test_chat_state_")
    os.close(fd)
    os.unlink(path)
    os.environ["FOODFOUNDER_STATE_FILE"] = path
    return path


def open_ai_page(state_path=None):
    if state_path is not None:
        os.environ["FOODFOUNDER_STATE_FILE"] = str(state_path)
    else:
        isolate_state_file()
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    at.sidebar.radio[0].set_value("AI Guidance")
    at.run()
    return at


def ok_chat_factory(calls, reply="Canned reply"):
    def fake_chat(message, history=None, product_context=None, **kwargs):
        calls.append(message)
        return reply

    return fake_chat


class TestAIChatInput(unittest.TestCase):
    def test_chat_input_rendered_on_ai_page(self):
        at = open_ai_page()
        self.assertEqual(len(at.chat_input), 1)
        self.assertFalse(at.exception)

    def test_arbitrary_question_flows_to_chat_and_input_recovers(self):
        at = open_ai_page()
        calls = []
        with mock.patch(
            "services.ai_assistant.chat", ok_chat_factory(calls, "Use metallised pouches.")
        ):
            at.chat_input[0].set_value("How do I price my chilli pickle?")
            at.run()

        self.assertEqual(calls, ["How do I price my chilli pickle?"])
        history = at.session_state["chat_history"]
        self.assertEqual(
            history[0], {"role": "user", "text": "How do I price my chilli pickle?"}
        )
        self.assertEqual(history[1]["role"], "model")
        self.assertEqual(history[1]["text"], "Use metallised pouches.")
        self.assertFalse(at.exception)
        self.assertEqual(
            len(at.chat_input), 1, "input must be available again after success"
        )

    def test_suggested_prompt_is_only_a_shortcut(self):
        at = open_ai_page()
        calls = []

        with mock.patch("services.ai_assistant.chat", ok_chat_factory(calls)):
            button = next(
                b for b in at.button if b.label.startswith("How should I package banana chips")
            )
            button.set_value(True)
            at.run()

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith("How should I package banana chips"))
        self.assertEqual(
            len(at.chat_input), 1, "input must remain after using a suggested prompt"
        )

        with mock.patch("services.ai_assistant.chat", ok_chat_factory(calls)):
            at.chat_input[0].set_value("And what about storage temperature?")
            at.run()

        self.assertEqual(calls[-1], "And what about storage temperature?")
        self.assertFalse(at.exception)

    def test_input_recovers_after_error_and_follow_up_works(self):
        at = open_ai_page()

        def failing_chat(message, history=None, product_context=None, **kwargs):
            raise AssistantError(
                "The AI service is temporarily overloaded because of high demand. "
                "This usually clears within a few minutes - please try again shortly."
            )

        with mock.patch("services.ai_assistant.chat", failing_chat):
            at.chat_input[0].set_value("First question")
            at.run()

        self.assertTrue(at.error, "error message must be shown to the user")
        self.assertEqual(
            len(at.chat_input), 1, "input must be available again after an error"
        )

        calls = []
        with mock.patch("services.ai_assistant.chat", ok_chat_factory(calls, "Recovered.")):
            at.chat_input[0].set_value("Follow-up question")
            at.run()

        self.assertEqual(calls, ["Follow-up question"])
        self.assertFalse(at.exception)

    def test_duplicate_submission_of_same_question_is_ignored(self):
        at = open_ai_page()
        calls = []
        with mock.patch("services.ai_assistant.chat", ok_chat_factory(calls)):
            at.chat_input[0].set_value("What margins should I target?")
            at.run()
            at.chat_input[0].set_value("What margins should I target?")
            at.run()

        self.assertEqual(calls, ["What margins should I target?"])
        history = at.session_state["chat_history"]
        self.assertEqual(len(history), 2, "one user turn and one model turn only")
        self.assertFalse(at.exception)


if __name__ == "__main__":
    unittest.main()
