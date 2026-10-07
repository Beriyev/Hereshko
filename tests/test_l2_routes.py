import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.api import routes_chat
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag.memory import ConversationStore


class L2RouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_endpoint_dispatches_l2(self):
        request = ChatRequest(notebook_id="test", query="Question", mode="l2")
        response = ChatResponse(answer="Final answer", sources=[])
        with patch.object(routes_chat, "l2_orchestrator", new_callable=AsyncMock, return_value=response) as l2, patch.object(
            routes_chat, "answer_l1", new_callable=AsyncMock
        ) as l1:
            result = await routes_chat.chat(request, Mock())
        self.assertIs(result, response)
        l2.assert_awaited_once()
        l1.assert_not_awaited()

    async def test_stream_reports_progress_and_saves_only_final_turn(self):
        store = ConversationStore()
        request = ChatRequest(notebook_id="test", query="Original", session_id="session", mode="l2")

        async def orchestrator(request, service, history, on_progress):
            await on_progress({"type": "planning"})
            await on_progress({"type": "planned", "questions": ["Subquestion"]})
            await on_progress({"type": "answering", "index": 0})
            await on_progress({"type": "answered", "index": 0, "answer": "Subanswer", "sources": []})
            await on_progress({"type": "synthesizing"})
            return ChatResponse(answer="Final answer", sources=[])

        with patch.object(routes_chat, "conversation_store", store), patch.object(
            routes_chat, "l2_orchestrator", side_effect=orchestrator
        ):
            response = await routes_chat.chat_l2(request, Mock())
            events = [json.loads(chunk) async for chunk in response.body_iterator]
        self.assertEqual([event["type"] for event in events],
                         ["planning", "planned", "answering", "answered", "synthesizing", "done"])
        self.assertEqual(events[-1]["answer"], "Final answer")
        self.assertEqual([message.content for message in store.get_recent("session", 16)],
                         ["Original", "Final answer"])

    async def test_stream_failure_reports_error_without_saving_turn(self):
        store = ConversationStore()
        with patch.object(routes_chat, "conversation_store", store), patch.object(
            routes_chat, "l2_orchestrator", new_callable=AsyncMock, side_effect=RuntimeError("Test failure")
        ):
            response = await routes_chat.chat_l2(
                ChatRequest(notebook_id="test", query="Question", session_id="session"), Mock()
            )
            events = [json.loads(chunk) async for chunk in response.body_iterator]
        self.assertEqual(events, [{"type": "error", "message": "Test failure"}])
        self.assertEqual(store.conversations, {})


if __name__ == "__main__":
    unittest.main()
