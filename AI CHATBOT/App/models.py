"""Pydantic models for Sage chatbot."""
from pydantic import BaseModel, Field  # type: ignore[import-untyped]


class ChatMessage(BaseModel):
    """User chat message."""
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """Chatbot response."""
    response: str
    suggestions: list[str] = []


class UserRegister(BaseModel):
    """User registration."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5)
    password: str = Field(min_length=6, max_length=72)


class UserLogin(BaseModel):
    """User login."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
