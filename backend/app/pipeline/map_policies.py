"""Step 3: map an analyzed change onto the client's policy library."""

from typing import Literal

from pydantic import BaseModel, Field

from app.config import settings
from app.llm import structured_call
from app.models import Analysis, Policy, RegItem


class PolicyImpact(BaseModel):
    policy_id: str = Field(description="The id attribute of the <policy> element")
    impact: Literal["none", "low", "medium", "high"] = Field(
        description="none=unrelated; low=awareness only; medium=review/minor update; high=policy must change"
    )
    affected_sections: list[str] = Field(description="Section numbers in the policy that are affected, e.g. '4.2'")
    rationale: str = Field(description="1-2 sentences linking the regulatory change to the policy text; empty if none")
    recommended_action: str = Field(description="Specific edit or task for the policy owner; empty if impact is none")
    confidence: float = Field(description="0.0-1.0 confidence in this assessment")


class PolicyMapping(BaseModel):
    impacts: list[PolicyImpact] = Field(description="Exactly one entry per policy in the library")


INSTRUCTIONS = """You are a compliance analyst mapping regulatory changes onto a client's internal \
policy library. For each policy, decide whether the change requires it to be reviewed or updated.

Rules:
- Return exactly one entry for every policy in the library, using its id.
- Ground every non-"none" rating in specific section numbers and wording from the policy text.
- Be discriminating: most changes touch only a few policies. Use "none" when the link is tenuous.
- Consider the client's business profile when judging applicability (jurisdiction, activities).
- Recommended actions should be specific enough for the policy owner to act on."""


def policy_library_block(policies: list[Policy]) -> str:
    parts = [f'<policy id="{p.id}" title="{p.title}" owner="{p.owner}">\n{p.body}\n</policy>' for p in policies]
    return "<policy_library>\n" + "\n\n".join(parts) + "\n</policy_library>"


def client_profile() -> str:
    path = settings.policies_dir / "_client-profile.md"
    return path.read_text(encoding="utf-8") if path.exists() else "(no client profile provided)"


def build_system(policies: list[Policy]) -> list[dict]:
    # Profile + policy library are identical for every item, so they are cached and reused across calls.
    return [
        {"type": "text", "text": INSTRUCTIONS},
        {
            "type": "text",
            "text": f"<client_profile>\n{client_profile()}\n</client_profile>\n\n{policy_library_block(policies)}",
            "cache_control": {"type": "ephemeral"},
        },
    ]


def build_prompt(item: RegItem, analysis: Analysis) -> str:
    bullets = lambda xs: "\n".join(f"- {x}" for x in xs) or "- (none stated)"  # noqa: E731
    return (
        f"Regulatory change ({analysis.regulation}, severity {analysis.severity}) from {item.source}:\n"
        f"Title: {analysis.title}\nURL: {item.url}\n\nSummary: {analysis.summary}\n\n"
        f"What changed:\n{bullets(analysis.what_changed)}\n\n"
        f"New obligations:\n{bullets(analysis.new_obligations)}\n\n"
        f"Who is affected: {analysis.who_is_affected}\n"
        f"Effective date: {analysis.effective_date or 'unknown'}\n\n"
        "Map this change to every policy in the library."
    )


def map_item(item: RegItem, analysis: Analysis, policies: list[Policy]) -> tuple[list[PolicyImpact], str]:
    result, model = structured_call(
        system=build_system(policies),
        user=build_prompt(item, analysis),
        output=PolicyMapping,
        effort="high",
    )
    known = {p.id for p in policies}
    return [i for i in result.impacts if i.policy_id in known], model
