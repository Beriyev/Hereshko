import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.core.exceptions import ChatError
from app.services.rag import l2


class L2CitationStartTests(unittest.IsolatedAsyncioTestCase):
    async def test_small_answer_forwards_required_start(self):
        request = ChatRequest(notebook_id="test", query="Question")
        service = Mock()
        service.retrieve_chunks.return_value = [Mock()]
        response = ChatResponse(answer="Answer", sources=[])
        with patch.object(l2, "embed_queries", return_value=[0.1]), patch.object(
            l2, "get_notebook", return_value={}
        ), patch.object(l2, "generate_answer", return_value=response) as generate:
            result = await l2.answer_l1_small(request, service, citation_start=7)
        self.assertIs(result, response)
        service.retrieve_chunks.assert_called_once_with(
            query="Question", embedding=[0.1], limit=10, candidate_limit=20, notebook_id="test"
        )
        self.assertEqual(generate.call_args.kwargs["citation_start"], 7)
        with self.assertRaises(TypeError):
            await l2.answer_l1_small(request, service)

    async def test_orchestrator_advances_after_highest_cited_marker(self):
        request = ChatRequest(notebook_id="test", query="Original", web_search=True)
        service = Mock()
        responses = [
            ChatResponse(answer="First [4]", sources=[Citation(
                marker=4, chunk_id="a", content="Evidence", source_type="pdf"
            )]),
            ChatResponse(answer="No evidence", sources=[]),
            ChatResponse(answer="Third [5]", sources=[Citation(
                marker=5, chunk_id="b", content="Evidence", source_type="pdf"
            )]),
        ]
        progress = AsyncMock()
        with patch.object(l2, "l2_planner", new_callable=AsyncMock,
                          return_value=l2.StringListResponse(query_list=["First", "Second", "Third"])), patch.object(
            l2, "get_notebook", return_value={}
        ), patch.object(l2, "answer_l1_small", new_callable=AsyncMock, side_effect=responses) as small, patch.object(
            l2.client.chat.completions, "create", return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Combined [5]. Again [5]. Unknown [99]."))]
            )
        ) as create:
            result = await l2.l2_orchestrator(request, service, on_progress=progress)
        calls = small.await_args_list
        self.assertEqual([call.kwargs["citation_start"] for call in calls], [1, 5, 5])
        self.assertEqual([call.kwargs["request"].query for call in calls], ["First", "Second", "Third"])
        self.assertTrue(all(call.kwargs["request"].web_search for call in calls))
        self.assertEqual(request.query, "Original")
        self.assertEqual([call.args[0]["type"] for call in progress.await_args_list],
                         ["planning", "planned", "answering", "answered", "answering", "answered",
                          "answering", "answered", "synthesizing"])
        self.assertEqual(result.answer, "Combined [5]. Again [5]. Unknown .")
        self.assertEqual([citation.marker for citation in result.sources], [5])
        self.assertEqual(result.sources[0].chunk_id, "b")
        context = create.call_args.kwargs["messages"][-1]["content"]
        self.assertIn("Original question: Original", context)
        self.assertIn("Question: First\nAnswer: First [4]", context)
        self.assertIn("Question: Second\nAnswer: No evidence", context)
        self.assertIn("Question: Third\nAnswer: Third [5]", context)

    async def test_marker_increment_is_numeric(self):
        response = ChatResponse(answer="Evidence [2][10]", sources=[])
        with patch.object(l2, "l2_planner", new_callable=AsyncMock,
                          return_value=l2.StringListResponse(query_list=["First", "Second"])), patch.object(
            l2, "get_notebook", return_value={}
        ), patch.object(l2, "answer_l1_small", new_callable=AsyncMock, return_value=response) as small, patch.object(
            l2.client.chat.completions, "create", return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Not enough evidence."))]
            )
        ):
            await l2.l2_orchestrator(ChatRequest(notebook_id="test", query="Original"), Mock())
        self.assertEqual([call.kwargs["citation_start"] for call in small.await_args_list], [1, 11])

    async def test_empty_synthesis_raises_chat_error(self):
        with patch.object(l2, "l2_planner", new_callable=AsyncMock,
                          return_value=l2.StringListResponse(query_list=["Question"])), patch.object(
            l2, "get_notebook", return_value={}
        ), patch.object(l2, "answer_l1_small", new_callable=AsyncMock,
                        return_value=ChatResponse(answer="No evidence.", sources=[])), patch.object(
            l2.client.chat.completions, "create", return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
            )
        ):
            with self.assertRaises(ChatError):
                await l2.l2_orchestrator(ChatRequest(notebook_id="test", query="Original"), Mock())


if __name__ == "__main__":
    unittest.main()
