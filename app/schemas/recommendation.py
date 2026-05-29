from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    limit: int = 10
