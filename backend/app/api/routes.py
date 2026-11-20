from fastapi import APIRouter, Depends, HTTPException, Query
import re

from fastapi.responses import PlainTextResponse, Response
from sqlmodel import Session, func, select

from app.config import settings
from app.db import get_session
from app.models import Analysis, Impact, Policy, RegItem
from app.pipeline import run as pipeline
from app.report_pdf import build_report_pdf

router = APIRouter(prefix="/api")

IMPACT_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def item_summary(item: RegItem, analysis: Analysis | None, impacts: list[Impact]) -> dict:
    hits = [i for i in impacts if i.impact != "none"]
    top = max((IMPACT_RANK[i.impact] for i in hits), default=0)
    return {
        "id": item.id,
        "source": item.source,
        "regulation": item.regulation,
        "url": item.url,
        "published": item.published,
        "status": item.status,
        "error": item.error,
        "raw_title": item.title,
        "title": analysis.title if analysis else item.title,
        "summary": analysis.summary if analysis else item.abstract[:400],
        "severity": analysis.severity if analysis else None,
        "topics": analysis.topics if analysis else [],
        "affected_policies": len(hits),
        "max_impact": next(k for k, v in IMPACT_RANK.items() if v == top),
    }


@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    by_status = dict(session.exec(select(RegItem.status, func.count()).group_by(RegItem.status)).all())
    by_reg = dict(session.exec(select(RegItem.regulation, func.count()).group_by(RegItem.regulation)).all())
    high = session.exec(select(func.count(func.distinct(Impact.item_id))).where(Impact.impact == "high")).one()
    return {
        "items": sum(by_status.values()),
        "by_status": by_status,
        "by_regulation": by_reg,
        "items_with_high_impact": high,
        "policies": session.exec(select(func.count()).select_from(Policy)).one(),
    }


@router.get("/items")
def list_items(
    regulation: str | None = None,
    severity: str | None = None,
    q: str | None = Query(None, description="Search in titles"),
    session: Session = Depends(get_session),
):
    stmt = select(RegItem).order_by(RegItem.published.desc())
    if regulation:
        stmt = stmt.where(RegItem.regulation == regulation)
    items = list(session.exec(stmt))
    analyses = {a.item_id: a for a in session.exec(select(Analysis))}
    impacts: dict[int, list[Impact]] = {}
    for imp in session.exec(select(Impact)):
        impacts.setdefault(imp.item_id, []).append(imp)
    out = [item_summary(i, analyses.get(i.id), impacts.get(i.id, [])) for i in items]
    if severity:
        out = [o for o in out if o["severity"] == severity]
    if q:
        ql = q.lower()
        out = [o for o in out if ql in o["title"].lower() or ql in o["raw_title"].lower()]
    return out


def load_item(session: Session, item_id: int):
    item = session.get(RegItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    analysis = session.exec(select(Analysis).where(Analysis.item_id == item_id)).first()
    impacts = list(session.exec(select(Impact).where(Impact.item_id == item_id)))
    policies = {p.id: p for p in session.exec(select(Policy))}
    impacts.sort(key=lambda i: (-IMPACT_RANK[i.impact], -i.confidence))
    return item, analysis, impacts, policies


@router.get("/items/{item_id}")
def get_item(item_id: int, session: Session = Depends(get_session)):
    item, analysis, impacts, policies = load_item(session, item_id)
    return {
        **item_summary(item, analysis, impacts),
        "abstract": item.abstract,
        "has_full_text": bool(item.full_text),
        "analysis": analysis.model_dump(exclude={"id", "item_id"}) if analysis else None,
        "impacts": [
            {**i.model_dump(exclude={"id", "item_id"}), "policy_title": policies[i.policy_id].title,
             "policy_owner": policies[i.policy_id].owner}
            for i in impacts if i.policy_id in policies
        ],
    }


@router.get("/items/{item_id}/report.md", response_class=PlainTextResponse)
def item_report(item_id: int, session: Session = Depends(get_session)):
    item, analysis, impacts, policies = load_item(session, item_id)
    if not analysis:
        raise HTTPException(409, "Item has not been analyzed yet")
    lines = [
        f"# Regulatory Impact Report: {analysis.title}",
        "",
        f"- **Source:** {item.source} ([link]({item.url}))",
        f"- **Published:** {item.published.date() if item.published else 'unknown'}",
        f"- **Regulation:** {analysis.regulation}   **Severity:** {analysis.severity}",
        f"- **Effective date:** {analysis.effective_date or 'n/a'}   **Comment deadline:** {analysis.comment_deadline or 'n/a'}",
        "",
        "## Summary",
        analysis.summary,
        "",
        "## What changed",
        *[f"- {x}" for x in analysis.what_changed],
        "",
        "## New obligations",
        *([f"- {x}" for x in analysis.new_obligations] or ["- None identified"]),
        "",
        f"**Who is affected:** {analysis.who_is_affected}",
        "",
        "## Affected policies",
    ]
    hits = [i for i in impacts if i.impact != "none"]
    if not hits:
        lines.append("No policies require changes.")
    for i in hits:
        p = policies.get(i.policy_id)
        lines += [
            f"### {p.title if p else i.policy_id} ({i.impact.upper()} impact)",
            f"- **Owner:** {p.owner if p else ''}",
            f"- **Sections:** {', '.join(i.affected_sections) or 'n/a'}",
            f"- **Why:** {i.rationale}",
            f"- **Action:** {i.recommended_action}",
            f"- **Confidence:** {i.confidence:.0%}",
            "",
        ]
    lines.append(f"_Generated by Regulatory Change Monitor using {analysis.model}. AI-generated; verify before acting._")
    return "\n".join(lines)


@router.get("/items/{item_id}/report.pdf")
def item_report_pdf(item_id: int, session: Session = Depends(get_session)):
    item, analysis, impacts, policies = load_item(session, item_id)
    if not analysis:
        raise HTTPException(409, "Item has not been analyzed yet")
    pdf = build_report_pdf(item, analysis, impacts, policies, settings.client_name)
    slug = re.sub(r"[^a-z0-9]+", "-", analysis.title.lower()).strip("-")[:60] or f"item-{item_id}"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="impact-report-{slug}.pdf"'},
    )


@router.get("/policies")
def list_policies(session: Session = Depends(get_session)):
    policies = list(session.exec(select(Policy).order_by(Policy.title)))
    counts: dict[str, dict[str, int]] = {}
    for imp in session.exec(select(Impact).where(Impact.impact != "none")):
        c = counts.setdefault(imp.policy_id, {"low": 0, "medium": 0, "high": 0})
        c[imp.impact] += 1
    return [
        {"id": p.id, "title": p.title, "owner": p.owner, "impacts": counts.get(p.id, {"low": 0, "medium": 0, "high": 0})}
        for p in policies
    ]


@router.get("/policies/{policy_id}")
def get_policy(policy_id: str, session: Session = Depends(get_session)):
    policy = session.get(Policy, policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")
    rows = session.exec(
        select(Impact, RegItem, Analysis)
        .join(RegItem, Impact.item_id == RegItem.id)
        .join(Analysis, Analysis.item_id == RegItem.id, isouter=True)
        .where(Impact.policy_id == policy_id, Impact.impact != "none")
    ).all()
    changes = [
        {
            "item_id": item.id,
            "title": analysis.title if analysis else item.title,
            "regulation": item.regulation,
            "published": item.published,
            "impact": imp.impact,
            "affected_sections": imp.affected_sections,
            "rationale": imp.rationale,
            "recommended_action": imp.recommended_action,
        }
        for imp, item, analysis in rows
    ]
    changes.sort(key=lambda c: -IMPACT_RANK[c["impact"]])
    return {**policy.model_dump(), "changes": changes}


@router.get("/matrix")
def matrix(session: Session = Depends(get_session)):
    policies = list(session.exec(select(Policy).order_by(Policy.title)))
    items = list(session.exec(select(RegItem).where(RegItem.status == "mapped").order_by(RegItem.published.desc())))
    analyses = {a.item_id: a for a in session.exec(select(Analysis))}
    cells = {(i.item_id, i.policy_id): i.impact for i in session.exec(select(Impact))}
    return {
        "policies": [{"id": p.id, "title": p.title} for p in policies],
        "rows": [
            {
                "item_id": it.id,
                "title": analyses[it.id].title if it.id in analyses else it.title,
                "regulation": it.regulation,
                "severity": analyses[it.id].severity if it.id in analyses else None,
                "cells": {p.id: cells.get((it.id, p.id), "none") for p in policies},
            }
            for it in items
        ],
    }


@router.post("/scan")
def trigger_scan(limit: int | None = Query(None, ge=1, le=200)):
    started = pipeline.start_scan_in_background(limit)
    return {"started": started, "status": pipeline.status.to_dict()}


@router.get("/scan/status")
def scan_status():
    return pipeline.status.to_dict()
