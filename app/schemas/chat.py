from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    initial_message: str = ""


class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "text"


class SubmitEssayRequest(BaseModel):
    essay_question: str
    essay_answer: str


class UpdateContextRequest(BaseModel):
    target_company_id: int | None = None
    target_job_role_id: int | None = None
    job_posting_id: int | None = None
