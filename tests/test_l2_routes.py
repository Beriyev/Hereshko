import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.api import routes_chat
from app.core.chat import ChatMessage, ChatRole
from app.schemas.chat import ChatRequest, ChatResponse


class L2RouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_reports_progress(self):
        request = ChatRequest(notebook_id="test", query="Original", session_id="session", mode="l2")
        history = [ChatMessage(role=ChatRole.USER, content="Previous question")]

        async def orchestrator(request, weaviate_service, history, on_progress):
            self.assertEqual(history, [ChatMessage(role=ChatRole.USER, content="Previous question")])
            await on_progress({"type": "planning"})
            await on_progress({"type": "planned", "questions": ["Subquestion"]})
            await on_progress({"type": "answering", "index": 0})
            await on_progress({"type": "answered", "index": 0, "answer": "Subanswer", "sources": []})
            await on_progress({"type": "synthesizing"})
            return ChatResponse(answer="Final answer", sources=[])

        with (
            patch.object(routes_chat, "get_history", return_value=history) as get_history,
            patch.object(routes_chat, "save_history", return_value=1) as save_history,
            patch.object(routes_chat, "l2_orchestrator", side_effect=orchestrator),
        ):
            response = await routes_chat.chat_l2(request, Mock())
            events = [json.loads(chunk) async for chunk in response.body_iterator]
        get_history.assert_called_once_with("test", "session")
        self.assertEqual(save_history.call_count, 2)
        self.assertEqual(save_history.call_args_list[0].args[2], ChatMessage(role=ChatRole.USER, content="Original"))
        self.assertEqual(save_history.call_args_list[1].args[2], ChatMessage(role=ChatRole.ASSISTANT, content="Final answer"))
        self.assertEqual([event["type"] for event in events],
                         ["planning", "planned", "answering", "answered", "synthesizing", "done"])
        self.assertEqual(events[-1]["answer"], "Final answer")

    async def test_stream_failure_reports_error(self):
        with (
            patch.object(routes_chat, "get_history", return_value=[]),
            patch.object(routes_chat, "save_history") as save_history,
            patch.object(routes_chat, "l2_orchestrator", new_callable=AsyncMock, side_effect=RuntimeError("Test failure")),
        ):
            response = await routes_chat.chat_l2(
                ChatRequest(notebook_id="test", query="Question", session_id="session"), Mock()
            )
            events = [json.loads(chunk) async for chunk in response.body_iterator]
        self.assertEqual(events, [{"type": "error", "message": "Test failure"}])
        save_history.assert_not_called()


if __name__ == "__main__":
    unittest.main()
