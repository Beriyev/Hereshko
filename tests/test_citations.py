import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.chat import ChatMessage, ChatRole
from app.core.chunking import Chunk
from app.core.exceptions import ChatError
from app.core.normalization import SourceType
from app.schemas.chat import ChatRequest
from app.services.rag.llm import generate_answer


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.request = ChatRequest(notebook_id="nb", query="Question")
        self.chunks = [
            Chunk(chunk_id="a", document_id="doc-a", notebook_id="nb", content="First source",
                  position_type=SourceType.PDF, source_name="Document A", page_number=3),
            Chunk(chunk_id="b", document_id="doc-b", notebook_id="nb", content="Second source",
                  position_type=SourceType.WEBSITE, source_name="Document B",
                  metadata={"url": "https://example.com/source"}),
        ]

    def answer(self, text, chunks=None, history=None):
        completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
        with patch("app.services.rag.llm.client.chat.completions.create", return_value=completion) as create:
            response = generate_answer(self.request, self.chunks if chunks is None else chunks, history)
        return response, create.call_args.kwargs

    def test_markers_map_to_correct_chunks_and_source_details(self):
        response, _ = self.answer("Second [2]. First [1]. Second again [2].")
        self.assertEqual([(source.marker, source.chunk_id) for source in response.sources], [(2, "b"), (1, "a")])
        self.assertEqual(response.sources[0].source_url, "https://example.com/source")
        self.assertEqual(response.sources[1].source_name, "Document A")
        self.assertEqual(response.sources[1].page_number, 3)
        self.assertEqual(response.sources[1].source_type, "pdf")

    def test_unknown_markers_do_not_produce_source_cards(self):
        response, _ = self.answer("Valid [1]. Invalid [99]. Repeated [99].")
        self.assertEqual(response.answer, "Valid [1]. Invalid [99]. Repeated [99].")
        self.assertEqual([source.marker for source in response.sources], [1])

    def test_full_source_content_and_history_are_preserved(self):
        self.chunks[0].content = "Evidence " * 2100
        history = [ChatMessage(role=ChatRole.USER, content="Earlier " * 200),
                   ChatMessage(role=ChatRole.ASSISTANT, content="Old answer [2]")]
        _, arguments = self.answer("Answer [1]", history=history)
        messages = arguments["messages"]
        self.assertIn(f"[1] {self.chunks[0].content}", messages[0]["content"])
        self.assertEqual(messages[1]["content"], history[0].content)
        self.assertEqual(messages[2]["content"], "Old answer ")
        self.assertEqual(messages[-1]["content"], "Question")

    def test_no_sources_does_not_produce_fake_citations(self):
        response, _ = self.answer("No evidence [1]", chunks=[])
        self.assertEqual(response.sources, [])
        self.assertEqual(response.answer, "No evidence [1]")

    def test_missing_llm_response_raises_chat_error(self):
        with self.assertRaises(ChatError):
            self.answer(None)


if __name__ == "__main__":
    unittest.main()
