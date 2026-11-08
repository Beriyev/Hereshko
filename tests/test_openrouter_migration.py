import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from openai import OpenAI

from app.clients.openrouter_client import structured_options
from app.schemas.graphweaver import MindMap
from app.schemas.testweaver import MCQQuestion, Question, Result, Topic, TopicSet
from app.core.exceptions import HereshkoError
from app.services.graphweaver import generator as graph
from app.services.testweaver import generator as study


def completion(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class OpenRouterTests(unittest.TestCase):
    def test_sdk_sends_schema_and_routing_parameters(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"choices": [{"index": 0, "message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}]})

        with OpenAI(api_key="test", base_url="https://openrouter.ai/api/v1", http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
            client.chat.completions.create(model="test/model", messages=[{"role": "user", "content": "test"}], **structured_options(MindMap))
        self.assertEqual(str(requests[0].url), "https://openrouter.ai/api/v1/chat/completions")
        body = json.loads(requests[0].content)
        self.assertEqual(body["response_format"]["json_schema"]["schema"], MindMap.model_json_schema())
        self.assertTrue(body["provider"]["require_parameters"])

    def test_mindmap_sends_source_and_validates_response(self):
        data = {"nodes": [{"id": "root", "parent_id": None, "title": "Topic", "summary": "Summary"}]}
        client = Mock()
        client.chat.completions.create.return_value = completion(json.dumps(data))
        with patch.object(graph, "load_document", return_value=SimpleNamespace(content="source text")), patch.object(graph, "openrouter_client", client):
            self.assertEqual(graph.generate_mindmap("doc"), data)
        args = client.chat.completions.create.call_args.kwargs
        self.assertEqual(args["messages"][1]["content"], "source text")
        self.assertEqual(args["response_format"]["json_schema"]["name"], "MindMap")

    def test_topics_send_source_and_cache_validated_result(self):
        data = {"topics": [{"id": "t", "title": "Title", "summary": "Summary", "key_points": ["Fact"]}]}
        client = Mock()
        client.chat.completions.create.return_value = completion(json.dumps(data))
        study.topic_cache.clear()
        self.addCleanup(study.topic_cache.clear)
        with patch.object(study, "load_document", return_value=SimpleNamespace(content="source text")), patch.object(study, "openrouter_client", client):
            self.assertEqual(study.generate_topics("doc", model="test/model"), data)
            self.assertEqual(study.generate_topics("doc", model="test/model"), data)
        client.chat.completions.create.assert_called_once()
        args = client.chat.completions.create.call_args.kwargs
        self.assertEqual(args["messages"][1]["content"], "source text")
        self.assertEqual(args["response_format"]["json_schema"]["schema"], TopicSet.model_json_schema())

    def test_empty_response_does_not_get_cached(self):
        client = Mock()
        client.chat.completions.create.return_value = completion(None)
        study.topic_cache.clear()
        with patch.object(study, "load_document", return_value=SimpleNamespace(content="source")), patch.object(study, "openrouter_client", client):
            with self.assertRaisesRegex(HereshkoError, "no topic content"):
                study.generate_topics("doc", model="test/model")
        self.assertNotIn(("doc", "test/model"), study.topic_cache)


class AsyncOpenRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_subjective_question_uses_structured_output_and_retrieval(self):
        question = Question(question_id="q", question="Explain?", difficulty="easy")
        client = Mock()
        client.chat.completions.create = AsyncMock(return_value=completion(question.model_dump_json()))
        topic = Topic(id="t", title="Title", summary="Summary", key_points=["Fact"])
        answer = SimpleNamespace(answer="Answer [1]")
        with patch.object(study, "async_openrouter_client", client), patch.object(study, "get_weaviate_service"), patch.object(study, "answer_l1", new_callable=AsyncMock, return_value=answer):
            result, text = await study.subjective_generate_question_and_answer([topic], "nb", model="test/model")
        self.assertEqual(result, question)
        self.assertEqual(text, "Answer ")
        self.assertEqual(client.chat.completions.create.call_args.kwargs["response_format"]["json_schema"]["name"], "Question")

    async def test_mcq_and_grading_use_their_schemas(self):
        mcq = MCQQuestion(question_id="q", question="Which?", difficulty="easy", options=["A", "B", "C", "D"], correct_option="A", explanation="A is right")
        grade = Result(correctness="correct", score=10)
        client = Mock()
        client.chat.completions.create = AsyncMock(side_effect=[completion(mcq.model_dump_json()), completion(grade.model_dump_json())])
        topic = Topic(id="t", title="Title", summary="Summary", key_points=["Fact"])
        with patch.object(study, "async_openrouter_client", client):
            self.assertEqual(await study.objective_generate_question_and_answer([topic], "nb", model="test/model"), mcq)
            self.assertEqual(await study.subjective_compare_answers("Q", "A", "A", model="test/model"), grade)
        schemas = [call.kwargs["response_format"]["json_schema"]["name"] for call in client.chat.completions.create.await_args_list]
        self.assertEqual(schemas, ["MCQQuestion", "Result"])
