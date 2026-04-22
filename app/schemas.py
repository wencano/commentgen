from datetime import datetime
from typing import Literal
from typing import Optional

from pydantic import BaseModel, Field


class CommentRunRequest(BaseModel):
    source_post_text: str = ""
    image_data_url: Optional[str] = None
    intent: str = Field(default="supportive")
    tone: str = Field(default="professional")
    length: Literal["short", "medium", "long"] = "short"
    variants: int = Field(default=3, ge=1, le=10)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)


class CommentRunCreateResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime


class CommentRunStatusResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    completed_at: Optional[datetime] = None
    comment_count: int = 0
    agent_name: str = "comment_reply"


class CommentArtifactResponse(BaseModel):
    run_id: str
    status: str
    request: CommentRunRequest
    comments: list[str]
    agent_name: str
    provider: str
    model: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class SessionCreateRequest(BaseModel):
    first_message: str = ""
    intent: str = Field(default="supportive")
    tone: str = Field(default="professional")
    length: Literal["short", "medium", "long"] = "short"
    variants: int = Field(default=3, ge=1, le=10)


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    message_id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class SessionDetail(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage]


class SessionIterateRequest(BaseModel):
    message: str = ""
    image_data_url: Optional[str] = None


class SessionIterateResponse(BaseModel):
    session_id: str
    title: str
    assistant_message: ChatMessage
    comments: list[str]
    extracted_image_text: str = ""
