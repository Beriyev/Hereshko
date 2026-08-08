from pydantic import BaseModel

class TokenVerifyRequest(BaseModel):
    access_token: str

class CurrentUser(BaseModel):
    user_id: str
    email: str