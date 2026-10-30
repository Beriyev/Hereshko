import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.api import routes_chat
from app.core.chat import ChatMessage, ChatRole
from app.core.exceptions import ChatError, HereshkoError, RetrievalError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag import l1


class L1Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = ChatRequest(notebook_id="notebook", query="Question", session_id="session")
        self.response = ChatResponse(answer="Answer", sources=[])
        self.chunks = [Mock()]
        self.service = Mock()
        self.service.retrieve_chunks.return_value = self.chunks
        self.embed = self.patch("embed_queries", return_value=[0.1])
        self.notebook = self.patch("get_notebook", return_value={"source_count": 2})
        self.web = self.patch("gather_web_sources", new_callable=AsyncMock, return_value=[])
        self.generate = self.patch("generate_answer", return_value=self.response)
        self.patch("print")
        trace = patch.object(l1.traceback, "print_exception")
        trace.start()
        self.addCleanup(trace.stop)

    def patch(self, name, **kwargs):
        patcher = patch.object(l1, name, **kwargs)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    async def test_normal_answer_preserves_retrieval_and_history(self):
        history = [ChatMessage(role=ChatRole.USER, content="Previous question")]
        result = await l1.answer_l1(self.request, self.service, history=history)
        self.assertIs(result, self.response)
        self.embed.assert_called_once_with("Question")
        self.service.retrieve_chunks.assert_called_once_with(
            query="Question", embedding=[0.1], limit=10, candidate_limit=20, notebook_id="notebook"
        )
        self.web.assert_not_awaited()
        self.generate.assert_called_once_with(
            chat_request=self.request, retrieved_chunks=self.chunks, history=history
        )

    async def test_larger_notebook_uses_existing_candidate_limit(self):
        self.notebook.return_value = {"source_count": 6}
        await l1.answer_l1(self.request, self.service)
        self.assertEqual(self.service.retrieve_chunks.call_args.kwargs["candidate_limit"], 24)

    async def test_explicit_web_search_combines_sources(self):
        self.request.web_search = True
        web_chunks = [Mock()]
        self.web.return_value = web_chunks
        await l1.answer_l1(self.request, self.service)
        self.web.assert_awaited_once_with(
            query="Question", context_chunks=self.chunks, notebook_id="notebook", force_web=True
        )
        self.assertEqual(self.generate.call_args.kwargs["retrieved_chunks"], self.chunks + web_chunks)

    async def test_web_off_does_not_search_even_with_empty_retrieval(self):
        self.service.retrieve_chunks.return_value = []
        self.web.side_effect = RuntimeError("offline")
        result = await l1.answer_l1(self.request, self.service)
        self.assertIs(result, self.response)
        self.web.assert_not_awaited()
        self.assertEqual(self.generate.call_args.kwargs["retrieved_chunks"], [])

    async def test_forced_web_failure_preserves_503(self):
        self.request.web_search = True
        self.web.side_effect = RuntimeError("offline")
        with self.assertRaises(HTTPException) as caught:
            await l1.answer_l1(self.request, self.service)
        self.assertEqual(caught.exception.status_code, 503)
        self.generate.assert_not_called()

    async def test_stage_failures_preserve_error_responses(self):
        for mocked, error, prefix in (
            (self.embed, HereshkoError("broken"), "Embedding"),
            (self.service.retrieve_chunks, RetrievalError("broken"), "Retrieval"),
            (self.generate, ChatError("broken"), "Chat"),
        ):
            with self.subTest(stage=prefix):
                mocked.side_effect = error
                with self.assertRaises(HTTPException) as caught:
                    await l1.answer_l1(self.request, self.service)
                self.assertEqual(caught.exception.status_code, 500)
                self.assertEqual(caught.exception.detail, f"{prefix} failed: broken")
                mocked.side_effect = None

    async def test_route_loads_and_saves_history(self):
        history = [ChatMessage(role=ChatRole.USER, content="Previous question")]
        with (
            patch.object(routes_chat, "get_history", return_value=history) as get_history,
            patch.object(routes_chat, "save_history", return_value=1) as save_history,
            patch.object(routes_chat, "answer_l1", new_callable=AsyncMock, return_value=self.response) as answer,
        ):
            result = await routes_chat.chat_l1(self.request, self.service)
        self.assertIs(result, self.response)
        get_history.assert_called_once_with("notebook", "session")
        answer.assert_awaited_once_with(request=self.request, weaviate_service=self.service, history=history)
        self.assertEqual(save_history.call_count, 2)
        self.assertEqual(save_history.call_args_list[0].args[2], ChatMessage(role=ChatRole.USER, content="Question"))
        self.assertEqual(save_history.call_args_list[1].args[2], ChatMessage(role=ChatRole.ASSISTANT, content="Answer"))


if __name__ == "__main__":
    unittest.main()
