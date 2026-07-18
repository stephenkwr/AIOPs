"""Evaluation API models."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetItemOut(BaseModel):
    id: str
    question: str
    category: str
    answerable: bool
    gold_doc: str | None
    reference_answer: str


class DatasetInfo(BaseModel):
    name: str
    total: int
    answerable: int
    unanswerable: int
    corpus_docs: list[str]
    items: list[DatasetItemOut]


class EvalStartRequest(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    retrieval_mode: str = Field(default="hybrid", pattern="^(keyword|vector|hybrid)$")
    k: int = Field(default=8, ge=1, le=50)
    graded: bool = False
    limit: int | None = Field(default=None, ge=1, le=500)


class EvalRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    dataset: str
    retrieval_mode: str
    k: int
    graded: bool
    answer_model: str | None
    judge_model: str | None
    status: str
    num_cases: int
    metrics: dict | None
    created_at: datetime
    finished_at: datetime | None


class EvalCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: str
    question: str
    category: str
    answerable: bool
    gold_doc: str | None
    retrieved: list[str] | None
    hit: bool
    rank: int | None
    reciprocal_rank: float
    answer: str | None
    refused: bool
    judge: dict | None
    correct: bool | None


class EvalRunDetail(EvalRunSummary):
    failure_reason: str | None
    cases: list[EvalCaseOut]
