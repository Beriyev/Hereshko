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


class Question(BaseModel):
    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"]


class MCQQuestion(Question):
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: str = Field(description="This is the correct option string.")
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
    points_to_improve: list[str] | None = None
    mcq_explanation: str | None = None


class SubjectiveGenerationResponse(BaseModel):
    question_answer_pairs: list[tuple[Question, str]]


class ObjectiveGenerationResponse(BaseModel):
    mcq_questions: list[MCQQuestion]


class SubmissionResponse(BaseModel):
    results: list[Result]

