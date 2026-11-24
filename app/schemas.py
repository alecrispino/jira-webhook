"""Pydantic-Modelle für den flachen Body aus der Jira Automation und die /stats-Antwort."""

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JiraEvent(BaseModel):
    """Body aus Jira Automation "Send web request":
    {"key": "...", "summary": "...", "status": "...", "urgency": "..."}
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    key: str = Field(min_length=1, max_length=255)
    summary: str = Field(max_length=10_000)
    status: str = Field(min_length=1, max_length=255)
    urgency: Optional[str] = Field(default=None, max_length=255)

    @field_validator("urgency", mode="before")
    @classmethod
    def empty_urgency_is_none(cls, v):
        # Jira-Smart-Values liefern für leere Felder einen leeren String.
        if isinstance(v, str) and not v.strip():
            return None
        return v


class WebhookResponse(BaseModel):
    status: str
    event_id: int


class StatsResponse(BaseModel):
    by_status: Dict[str, int]
    by_urgency: Dict[str, int]
