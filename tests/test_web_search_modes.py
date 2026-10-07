import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag import l1, l2


class WebSearchModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_web_toggle_in_both_helpers_with_and_without_notebook_context(self):
        for module in (l1, l2):
            for enabled in (False, True):
                for has_chunks in (False, True):
                    with self.subTest(module=module.__name__, enabled=enabled, has_chunks=has_chunks):
                        chunks = [Mock()] if has_chunks else []
                        web_chunks = [Mock()]
                        service = Mock()
                        service.retrieve_chunks.return_value = chunks
                        request = ChatRequest(notebook_id="test", query="Question", web_search=enabled)
                        with patch.object(module, "embed_queries", return_value=[0.1]), patch.object(
                            module, "get_notebook", return_value={"source_count": 1}
                        ), patch.object(module, "gather_web_sources", new_callable=AsyncMock,
                                        return_value=web_chunks) as web, patch.object(
                            module, "generate_answer", return_value=ChatResponse(answer="Answer", sources=[])
                        ) as generate:
                            if module is l1:
                                await l1.answer_l1(request, service)
                            else:
                                await l2.answer_l1_small(request, service, citation_start=1)
                        if enabled:
                            web.assert_awaited_once_with(query="Question", context_chunks=chunks,
                                                        notebook_id="test", force_web=True)
                        else:
                            web.assert_not_awaited()
                        self.assertEqual(generate.call_args.kwargs["retrieved_chunks"],
                                         chunks + (web_chunks if enabled else []))


if __name__ == "__main__":
    unittest.main()
