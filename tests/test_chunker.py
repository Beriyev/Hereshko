import os
os.environ["HF_HUB_OFFLINE"] = "1"

import unittest
from datetime import datetime, timezone

from app.core.normalization import Document, SourceType
from app.services.rag.chunker import chunker, get_token_count


class ChunkerTests(unittest.TestCase):
    def document(self, text, boundaries=None, kind=SourceType.PDF):
        return Document(
            document_id="test-document", notebook_id="test-notebook", title="Test source",
            content=text, source_type=kind, source_identifier="https://example.com/source",
            ingested_at=datetime.now(timezone.utc), raw_metadata={"boundaries": boundaries or []},
        )

    def test_default_size_limits_and_overlap_preserve_text(self):
        paragraphs = [f"Section {i}: The program manager monitors risks and delivers benefits. "
                      "The sponsor authorizes resources, while stakeholders review the outcomes."
                      for i in range(100)]
        chunks = chunker(self.document("\n\n".join(paragraphs)))
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(get_token_count(chunk.content), 384)
        for paragraph in paragraphs:
            self.assertTrue(any(paragraph in chunk.content for chunk in chunks))
        for first, second in zip(chunks, chunks[1:]):
            self.assertTrue(any(first.content.endswith(second.content[:length])
                                for length in range(30, min(len(first.content), len(second.content)))))

    def test_page_boundaries_and_citation_metadata_are_unchanged(self):
        first = "First page discusses risk monitoring. " * 150
        second = "Second page discusses stakeholder engagement. " * 150
        text = first + second
        chunks = chunker(self.document(text, [
            {"start": 0, "end": len(first), "page_number": 1},
            {"start": len(first), "end": len(text), "page_number": 2},
        ]))
        self.assertEqual({chunk.page_number for chunk in chunks}, {1, 2})
        for chunk in chunks:
            self.assertEqual(chunk.document_id, "test-document")
            self.assertEqual(chunk.notebook_id, "test-notebook")
            self.assertEqual(chunk.source_name, "Test source")
            if chunk.page_number == 1:
                self.assertNotIn("Second page", chunk.content)
            else:
                self.assertNotIn("First page", chunk.content)
        self.assertEqual(len({chunk.chunk_id for chunk in chunks}), len(chunks))

    def test_short_sources_and_url_metadata_are_unchanged(self):
        chunks = chunker(self.document("A short source with one fact.", kind=SourceType.WEBSITE))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].content, "A short source with one fact.")
        self.assertEqual(chunks[0].metadata["url"], "https://example.com/source")
        self.assertEqual(chunker(self.document("")), [])


if __name__ == "__main__":
    unittest.main()
