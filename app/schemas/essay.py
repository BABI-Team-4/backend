from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Essay(BaseModel):
    id: str | None = Field(None, alias="_id")
    source: Literal["jobkorea", "linkareer"]
    source_id: str
    company: str
    org_type: Literal["corp", "bank", "public"]
    role: str
    hire_type: str
    year: int
    season: str
    university: str = ""
    major: str = ""
    crawled_at: datetime = Field(default_factory=datetime.utcnow)


class QnA(BaseModel):
    id: str | None = Field(None, alias="_id")
    essay_id: str
    question: str
    answer: str
    question_clean: str = ""
    answer_clean: str = ""
    question_type: str = ""
    char_count: int = 0
    is_valid: int = 1


class QnAEmbedding(BaseModel):
    qna_id: str
    chroma_id: str
    model_name: str = "BAAI/bge-m3"
    embedded_at: datetime = Field(default_factory=datetime.utcnow)
