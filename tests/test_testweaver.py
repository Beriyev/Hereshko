import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.genai.errors import APIError
from httpx import RequestError
from pydantic import ValidationError

from app.api import routes_testweaver
from app.core.exceptions import HereshkoError
from app.core.normalization import Document, SourceType
from app.schemas.chat import ChatResponse
from app.schemas.testweaver import MCQQuestion, Question, Topic, TopicSet
from app.services.testweaver import generator


TOPICS = {"topics": [{
    "id": "topic-1", "title": "Photosynthesis",
    "summary": "Plants convert light energy into chemical energy.",
    "key_points": ["Light provides energy.", "Chlorophyll absorbs light."],
}]}


class TopicGenerationTests(unittest.TestCase):
    def setUp(self):
        self.document = Document(
            document_id="doc-1", notebook_id="nb-1", title="Biology",
            content="Plants convert light energy into chemical energy using chlorophyll.",
            source_type=SourceType.TXT, source_identifier="biology.txt",
            ingested_at=datetime.now(timezone.utc), raw_metadata={},
        )

    def generate(self, text):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=text)
        with patch.object(generator, "load_document", return_value=self.document) as load, \
             patch.object(generator.genai, "Client", return_value=client):
            result = generator.generate_topics("doc-1")
        load.assert_called_once_with(document_id="doc-1")
        client.close.assert_called_once()
        return result, client.models.generate_content.call_args.kwargs

    def test_uses_full_source_json_and_structured_topic_schema(self):
        result, arguments = self.generate(json.dumps(TOPICS))
        self.assertEqual(result, TOPICS)
        self.assertIn(self.document.model_dump_json(), arguments["contents"])
        self.assertIn("no fixed count", arguments["contents"])
        self.assertEqual(arguments["config"].response_mime_type, "application/json")
        self.assertIs(arguments["config"].response_schema, TopicSet)

    def test_accepts_content_driven_topic_count(self):
        topics = {"topics": [TOPICS["topics"][0], {
            "id": "topic-2", "title": "Chlorophyll", "summary": "Absorbs light.",
            "key_points": ["Chlorophyll is a pigment."],
        }]}
        self.assertEqual(len(self.generate(json.dumps(topics))[0]["topics"]), 2)

    def test_missing_response_raises_readable_error(self):
        for text in (None, ""):
            with self.subTest(text=text), self.assertRaisesRegex(HereshkoError, "no topic content"):
                self.generate(text)

    def test_rejects_invalid_json_empty_topics_duplicates_and_blank_points(self):
        invalid = ["not json", '{"topics": []}', json.dumps({"topics": TOPICS["topics"] * 2}),
                   json.dumps({"topics": [{**TOPICS["topics"][0], "key_points": [" "]}]})]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValidationError):
                self.generate(text)

    def test_empty_source_never_calls_gemini(self):
        self.document.content = " "
        with patch.object(generator, "load_document", return_value=self.document), \
             patch.object(generator.genai, "Client") as client:
            with self.assertRaisesRegex(HereshkoError, "no extracted text"):
                generator.generate_topics("doc-1")
            client.assert_not_called()


class QuestionGenerationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.topic = Topic.model_validate(TOPICS["topics"][0])
        self.question = Question(question_id="q-1", question="Explain photosynthesis.", difficulty="medium")
        self.client = MagicMock()
        self.async_client = self.client.aio.__aenter__.return_value
        self.async_client.models.generate_content = AsyncMock(
            return_value=SimpleNamespace(text=self.question.model_dump_json())
        )

    async def test_topics_then_question_use_separate_clients_and_await_answer(self):
        sync_client = Mock()
        sync_client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(TOPICS))
        document = Mock(content="Source content")
        document.model_dump_json.return_value = '{"content": "Source content"}'
        service = Mock()
        with patch.object(generator.genai, "Client", side_effect=[sync_client, self.client]) as create, \
             patch.object(generator, "load_document", return_value=document), \
             patch.object(generator, "get_weaviate_service", return_value=service), \
             patch.object(generator, "answer_l1", new_callable=AsyncMock,
                          return_value=ChatResponse(answer="Expected answer", sources=[])) as answer:
            self.assertEqual(generator.generate_topics("doc-1"), TOPICS)
            result = await generator.subjective_generate_question_and_answer(self.topic, "nb-1")
        self.assertEqual(result, (self.question, "Expected answer"))
        self.assertEqual(create.call_count, 2)
        sync_client.close.assert_called_once()
        self.async_client.models.generate_content.assert_awaited_once()
        self.client.aio.__aexit__.assert_awaited_once()
        self.client.models.generate_content.assert_not_called()
        answer.assert_awaited_once()
        self.assertEqual(answer.call_args.kwargs["request"].notebook_id, "nb-1")
        self.assertIs(answer.call_args.kwargs["weaviate_service"], service)

    async def test_async_client_is_closed_on_gemini_failure(self):
        self.async_client.models.generate_content.side_effect = RequestError("offline")
        with patch.object(generator.genai, "Client", return_value=self.client), \
             patch.object(generator, "answer_l1", new_callable=AsyncMock) as answer:
            with self.assertRaises(RequestError):
                await generator.subjective_generate_question_and_answer(self.topic, "nb-1")
        self.client.aio.__aexit__.assert_awaited_once()
        answer.assert_not_awaited()

    async def test_missing_question_never_calls_l1(self):
        self.async_client.models.generate_content.return_value = SimpleNamespace(text=None)
        with patch.object(generator.genai, "Client", return_value=self.client), \
             patch.object(generator, "answer_l1", new_callable=AsyncMock) as answer:
            with self.assertRaisesRegex(HereshkoError, "no questions"):
                await generator.subjective_generate_question_and_answer(self.topic, "nb-1")
        self.client.aio.__aexit__.assert_awaited_once()
        answer.assert_not_awaited()


class TestGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcq_count_unique_ids_and_answer_keys_are_preserved(self):
        question = MCQQuestion(
            question_id="repeated-llm-id", question="What absorbs light?", difficulty="easy",
            options=["Chlorophyll", "Starch", "Glucose", "Cellulose"],
            correct_option=0, explanation="Chlorophyll absorbs light.",
        )
        with patch.object(generator, "generate_topics", return_value=TOPICS) as topics, \
             patch.object(generator, "objective_generate_question_and_answer", new_callable=AsyncMock,
                          side_effect=[MCQQuestion.model_validate(question.model_dump()) for _ in range(4)]) as generate:
            questions = await generator.generate_mcq_test("doc-1", "nb-1", 4, model="test-model")
        self.assertEqual(len(questions), 4)
        self.assertEqual(len({item.question_id for item in questions}), 4)
        self.assertTrue(all(UUID(item.question_id).version == 4 for item in questions))
        self.assertTrue(all(item.correct_option == 0 and item.explanation == question.explanation for item in questions))
        self.assertEqual(question.question_id, "repeated-llm-id")
        topics.assert_called_once_with(document_id="doc-1", model="test-model")
        self.assertEqual(generate.await_count, 4)
        for call in generate.call_args_list:
            self.assertEqual(call.kwargs["topic"].id, "topic-1")
            self.assertEqual(call.kwargs["notebook_id"], "nb-1")
            self.assertEqual(call.kwargs["model"], "test-model")

    async def test_subjective_count_unique_ids_and_answer_pairing(self):
        question = Question(question_id="repeated-llm-id", question="Explain photosynthesis.", difficulty="medium")
        answers = ["Expected answer 1", "Expected answer 2", "Expected answer 3"]
        with patch.object(generator, "generate_topics", return_value=TOPICS) as topics, \
             patch.object(generator, "subjective_generate_question_and_answer", new_callable=AsyncMock,
                          side_effect=[(Question.model_validate(question.model_dump()), answer) for answer in answers]) as generate:
            questions = await generator.generate_subjective_test("doc-1", "nb-1", 3, model="test-model")
        self.assertEqual(len(questions), 3)
        self.assertEqual([answer for _, answer in questions], answers)
        self.assertEqual(len({item.question_id for item, _ in questions}), 3)
        self.assertTrue(all(UUID(item.question_id).version == 4 for item, _ in questions))
        self.assertEqual(question.question_id, "repeated-llm-id")
        topics.assert_called_once_with(document_id="doc-1", model="test-model")
        self.assertEqual(generate.await_count, 3)
        for call in generate.call_args_list:
            self.assertEqual(call.kwargs["topic"].id, "topic-1")
            self.assertEqual(call.kwargs["notebook_id"], "nb-1")
            self.assertEqual(call.kwargs["model"], "test-model")

    async def test_invalid_counts_do_not_generate_topics(self):
        with patch.object(generator, "generate_topics") as topics:
            for count in (-1, 0):
                with self.subTest(mode="mcq", count=count), self.assertRaises(HereshkoError):
                    await generator.generate_mcq_test("doc-1", "nb-1", count)
            for count in (-1, 0, 4):
                with self.subTest(mode="subjective", count=count), self.assertRaises(HereshkoError):
                    await generator.generate_subjective_test("doc-1", "nb-1", count)
            topics.assert_not_called()


class TopicRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(routes_testweaver.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        for name, result in (("get_notebook", {"notebook_id": "nb-1"}),
                             ("list_sources", [{"document_id": "doc-1"}]),
                             ("generate_topics", TOPICS)):
            patcher = patch.object(routes_testweaver, name, return_value=result)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def request(self, body=None):
        return self.client.post("/notebooks/nb-1/testweaver/topics",
                                json={"document_id": "doc-1"} if body is None else body)

    def test_returns_topics_and_only_passes_document_id(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), TOPICS)
        self.generate_topics.assert_called_once_with(document_id="doc-1")

    def test_unknown_notebook_or_foreign_source_never_calls_generator(self):
        self.get_notebook.return_value = None
        self.assertEqual(self.request().status_code, 404)
        self.get_notebook.return_value = {"notebook_id": "nb-1"}
        self.list_sources.return_value = [{"document_id": "other-doc"}]
        self.assertEqual(self.request().status_code, 404)
        self.generate_topics.assert_not_called()

    def test_invalid_document_ids_are_rejected(self):
        for document_id in ("", "../outside", "path/with/slashes"):
            with self.subTest(document_id=document_id):
                self.assertEqual(self.request({"document_id": document_id}).status_code, 422)
        self.generate_topics.assert_not_called()

    def test_errors_have_readable_details(self):
        cases = [(FileNotFoundError(), 409), (HereshkoError("No topics"), 502),
                 (RequestError("offline"), 503),
                 (APIError(429, {"error": {"message": "Quota", "status": "RESOURCE_EXHAUSTED"}}), 429)]
        for error, code in cases:
            with self.subTest(error=error):
                self.generate_topics.side_effect = error
                response = self.request()
                self.assertEqual(response.status_code, code, response.text)
                self.assertIsInstance(response.json()["detail"], str)


if __name__ == "__main__":
    unittest.main()
