import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.chat import ChatMessage, ChatRole
from app.core.exceptions import ChatError
from app.schemas.chat import ChatRequest
from app.services.rag import l2


class L2PlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_planner_receives_inputs_and_returns_model(self):
        request = ChatRequest(notebook_id="test", query="Explain the project materials")
        completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"query_list": ["What materials does the project use?"]}'
        ))])
        history = [ChatMessage(role=ChatRole.ASSISTANT, content="Earlier answer [1]")]
        with patch.object(l2, "get_notebook", return_value={}), patch.object(
            l2, "notebook_summaries", {"test": "A project using copper panels."}
        ), patch.object(l2.client.chat.completions, "create", return_value=completion) as create:
            plan = await l2.l2_planner(request, history)
        self.assertIsInstance(plan, l2.StringListResponse)
        self.assertEqual(plan.query_list, ["What materials does the project use?"])
        arguments = create.call_args.kwargs
        self.assertEqual(arguments["response_format"], {"type": "json_object"})
        self.assertIn(request.query, arguments["messages"][-1]["content"])
        self.assertIn("A project using copper panels.", arguments["messages"][-1]["content"])
        self.assertEqual(arguments["messages"][1]["content"], "Earlier answer ")

    async def test_missing_summary_is_allowed(self):
        completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"query_list": ["Question?"]}'
        ))])
        with patch.object(l2, "get_notebook", return_value=None), patch.object(
            l2, "notebook_summaries", {}
        ), patch.object(l2.client.chat.completions, "create", return_value=completion):
            plan = await l2.l2_planner(ChatRequest(notebook_id="test", query="Question"))
        self.assertEqual(plan.query_list, ["Question?"])

    async def test_empty_completion_raises_chat_error(self):
        completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])
        with patch.object(l2, "get_notebook", return_value=None), patch.object(
            l2.client.chat.completions, "create", return_value=completion
        ):
            with self.assertRaises(ChatError):
                await l2.l2_planner(ChatRequest(notebook_id="test", query="Question"))


if __name__ == "__main__":
    unittest.main()
