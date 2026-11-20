"""Step 2: summarize what a regulatory update changes, as structured fields."""

from typing import Literal

from pydantic import BaseModel, Field

from app.llm import structured_call
from app.models import RegItem

# Regulatory texts can be very long (full Federal Register rules run to hundreds of pages).
# We send up to this many characters and tell the model when it is reading an excerpt.
MAX_CHARS = 120_000


class ChangeAnalysis(BaseModel):
    title: str = Field(description="Short plain-English title for the change (max ~12 words)")
    summary: str = Field(description="2-4 sentence executive summary for a compliance officer")
    what_changed: list[str] = Field(description="Concrete changes vs. the prior state, one per bullet")
    new_obligations: list[str] = Field(description="New or modified obligations for regulated firms; empty if none")
    who_is_affected: str = Field(description="Which kinds of organizations or activities are in scope")
    effective_date: str | None = Field(description="Effective/compliance date (YYYY-MM-DD or text), null if unknown")
    comment_deadline: str | None = Field(description="Public comment deadline if this is a proposal, else null")
    regulation: Literal["SEC", "FINRA", "AML", "OTHER"] = Field(
        description="Primary regime: SEC rules/guidance, FINRA rules/notices, AML = FinCEN/BSA/sanctions, else OTHER"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="low=informational; medium=guidance worth reviewing; high=binding change needing action; "
        "critical=binding change with near-term deadline or enforcement risk"
    )
    topics: list[str] = Field(description="3-6 short topic tags, e.g. 'custody', 'Marketing Rule', 'AML program'")


SYSTEM = """You are a senior regulatory-compliance analyst at a consulting firm serving US financial \
services clients. You read regulatory publications (SEC rules and releases, FINRA Regulatory Notices, \
FinCEN anti-money-laundering rules) and explain precisely what changed and what regulated firms now \
have to do.

Be concrete and faithful to the source: cite rule numbers, articles, dates and thresholds when the \
text gives them, and never invent obligations the text does not support. If the source is only a \
news item or explainer rather than a binding instrument, say so in the summary and rate severity \
accordingly."""


def build_prompt(item: RegItem) -> str:
    body = item.full_text or item.abstract or "(no body text available; rely on the title)"
    note = ""
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS]
        note = "\nNOTE: the document is long; below is the first part only. Say so if it limits your analysis.\n"
    published = item.published.date().isoformat() if item.published else "unknown"
    return (
        f"Source feed: {item.source}\nPublished: {published}\nURL: {item.url}\n"
        f"Title: {item.title}\n{note}\n<document>\n{body}\n</document>\n\n"
        "Analyze this regulatory update."
    )


def analyze_item(item: RegItem) -> tuple[ChangeAnalysis, str]:
    return structured_call(system=SYSTEM, user=build_prompt(item), output=ChangeAnalysis, effort="medium")
