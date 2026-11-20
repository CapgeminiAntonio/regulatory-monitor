from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RegItem(SQLModel, table=True):
    """One regulatory update pulled from a feed."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # e.g. "SEC Federal Register", "EDPB"
    regulation: str = Field(index=True)  # SEC | GDPR | EU_AI_ACT | OTHER (source hint; refined by LLM)
    title: str
    url: str = Field(unique=True, index=True)
    published: Optional[datetime] = Field(default=None, index=True)
    abstract: str = ""
    full_text: str = ""
    content_hash: str = Field(index=True)
    status: str = Field(default="new", index=True)  # new | analyzed | mapped | failed
    error: Optional[str] = None
    fetched_at: datetime = Field(default_factory=utcnow)


class Analysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="regitem.id", unique=True, index=True)
    title: str
    summary: str
    what_changed: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    new_obligations: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    who_is_affected: str = ""
    effective_date: Optional[str] = None
    comment_deadline: Optional[str] = None
    regulation: str
    severity: str  # low | medium | high | critical
    topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    model: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Policy(SQLModel, table=True):
    id: str = Field(primary_key=True)  # slug, e.g. "data-retention"
    title: str
    owner: str = ""
    body: str


class Impact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="regitem.id", index=True)
    policy_id: str = Field(foreign_key="policy.id", index=True)
    impact: str  # none | low | medium | high
    affected_sections: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rationale: str = ""
    recommended_action: str = ""
    confidence: float = 0.0
