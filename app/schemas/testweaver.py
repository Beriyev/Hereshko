from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Topic(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)


class TopicSet(BaseModel):
    topics: list[Topic] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [topic.id for topic in self.topics]
        if len(ids) != len(set(ids)):
            raise ValueError("Topic IDs must be unique")
        for topic in self.topics:
            if not all(value.strip() for value in (topic.id, topic.title, topic.summary, *topic.key_points)):
                raise ValueError("Topic fields and key points must not be blank")
        return self


class TopicsRequest(BaseModel):
    document_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")


class Question(BaseModel):
    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"]


class MCQQuestion(Question):
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: int = Field(ge=0, le=3, strict=True, description="Zero-based index of the correct option")
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_options(self):
        normalized = [option.strip().casefold() for option in self.options]
        if not all(normalized):
            raise ValueError("MCQ options must not be blank")
        if len(set(normalized)) != 4:
            raise ValueError("MCQ options must be distinct")
        return self


class Result(BaseModel):
    correctness: Literal["correct", "partially_correct", "incorrect"]
    score: int = Field(ge=0, le=10)
    points_to_improve: list[str]


class TestRequest(TopicsRequest):
    mode: Literal["objective", "subjective"]
    number_of_questions: int = Field(ge=1, le=50, strict=True)


class SubjectiveQuestion(Question):
    expected_answer: str


class ObjectiveTest(BaseModel):
    mode: Literal["objective"] = "objective"
    questions: list[MCQQuestion] = Field(min_length=1)


class SubjectiveTest(BaseModel):
    mode: Literal["subjective"] = "subjective"
    questions: list[SubjectiveQuestion] = Field(min_length=1, max_length=3)


GeneratedTest = ObjectiveTest | SubjectiveTest


class CompareAnswersRequest(BaseModel):
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    provided_answer: str
