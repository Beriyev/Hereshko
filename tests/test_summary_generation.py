import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.exceptions import ChatError
from app.services.rag.llm import generate_preview_summary


class SummaryGenerationTests(unittest.TestCase):
    def generate(self, answer):
        completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])
        with patch("app.services.rag.llm.client.chat.completions.create", return_value=completion) as create:
            overview = generate_preview_summary([{"title": "Source", "preview_text": "Source text"}])
        return overview, create.call_args.kwargs

    def test_requests_json_and_parses_it_directly(self):
        overview, arguments = self.generate('{"title": "Notebook", "summary": "Overview"}')
        self.assertEqual(overview.title, "Notebook")
        self.assertEqual(overview.summary, "Overview")
        self.assertEqual(arguments["response_format"], {"type": "json_object"})

    def test_invalid_json_or_missing_fields_raise_chat_error(self):
        for answer in ("not json", '{"title": "Missing summary"}', None):
            with self.subTest(answer=answer), self.assertRaises(ChatError):
                self.generate(answer)

    def test_empty_previews_do_not_call_llm(self):
        with patch("app.services.rag.llm.client.chat.completions.create") as create:
            with self.assertRaises(ChatError):
                generate_preview_summary([])
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
