from __future__ import annotations

from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class Token(BaseModel):
    """OAuth2 JWT access token response."""

    access_token: str = Field(..., description="JWT access token string")
    token_type: str = Field(default="bearer", description="Type of token, typically 'bearer'")

    model_config = {
        "from_attributes": True,
    }


# PUBLIC_INTERFACE
class LoginRequest(BaseModel):
    """Login request payload using username and password."""

    username: str = Field(..., description="Username of the user")
    password: str = Field(..., description="Plain text password")

    model_config = {
        "from_attributes": True,
    }
