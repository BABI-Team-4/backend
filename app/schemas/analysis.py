from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    analysis_type: str = "full"
