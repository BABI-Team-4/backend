from pydantic import BaseModel


class CreateEssayRequest(BaseModel):
    title: str = ""
    company: str = ""
    position: str = ""


class SubmitEssayRequest(BaseModel):
    essay_question: str
    essay_answer: str
