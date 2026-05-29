from pydantic import BaseModel


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
