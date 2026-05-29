from pydantic import BaseModel


class PaginatedParams(BaseModel):
    page: int = 1
    limit: int = 20
