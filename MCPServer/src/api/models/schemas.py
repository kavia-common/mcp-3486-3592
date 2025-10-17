import uuid
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class UserBase(BaseModel):
    username: str = Field(..., description="Unique username")
    role: str = Field(..., description="User role (e.g., admin, user)")


class UserCreate(UserBase):
    password: str = Field(..., description="Plain password")


class UserRead(UserBase):
    id: uuid.UUID = Field(..., description="User ID")
    created_at: datetime = Field(..., description="User creation timestamp")


class MessageBase(BaseModel):
    content: str = Field(..., description="Raw message content")
    status: Literal["pending", "processed", "failed"] = Field(default="pending", description="Message status")
    jira_issue_id: Optional[str] = Field(default=None, description="Linked JIRA issue id")


class MessageCreate(BaseModel):
    content: str = Field(..., description="Raw message content")


class MessageUpdate(BaseModel):
    status: Optional[Literal["pending", "processed", "failed"]] = None
    jira_issue_id: Optional[str] = None


class MessageRead(MessageBase):
    id: uuid.UUID = Field(..., description="Message ID")
    created_at: datetime
    updated_at: Optional[datetime] = None


class RuleBase(BaseModel):
    name: str = Field(..., description="Rule name")
    definition: str = Field(..., description="Rule definition in DSL/JSON")
    is_active: bool = Field(default=True, description="Rule active flag")


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    definition: Optional[str] = None
    is_active: Optional[bool] = None


class RuleRead(RuleBase):
    id: uuid.UUID
    created_at: datetime


class AuditRead(BaseModel):
    id: uuid.UUID
    action: str
    performed_by: Optional[uuid.UUID] = None
    timestamp: datetime
    details: Optional[str] = None


class JiraIssueLinkRequest(BaseModel):
    message_id: uuid.UUID = Field(..., description="Message ID to link")
    jira_issue_id: str = Field(..., description="Target JIRA issue ID/key")


class JiraSyncRead(BaseModel):
    id: uuid.UUID
    jira_issue_id: str
    message_id: Optional[uuid.UUID] = None
    sync_status: Literal["pending", "synced", "error"]
    last_synced_at: Optional[datetime] = None
