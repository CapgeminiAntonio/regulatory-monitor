"""Load the client's policy library (markdown files with a small front-matter header)."""

from pathlib import Path

import logging

from sqlmodel import Session, delete, select

from app.models import Impact, Policy, RegItem

log = logging.getLogger(__name__)


def parse_policy_file(path: Path) -> Policy:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        _, header, body = text.split("---", 2)
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return Policy(
        id=meta.get("id", path.stem),
        title=meta.get("title", path.stem.replace("-", " ").title()),
        owner=meta.get("owner", ""),
        body=body.strip(),
    )


def sync_policies(session: Session, policies_dir: Path) -> int:
    """Load policy files into the DB.

    If the *set* of policies changed (files added or removed), existing mappings were made against a
    different library: impacts for removed policies are deleted and every mapped item is marked
    "stale". Stale items are NOT re-mapped automatically (that costs LLM calls); run
    `python -m app.cli remap` when you want them refreshed.
    """
    on_disk = [parse_policy_file(p) for p in sorted(policies_dir.glob("*.md")) if not p.name.startswith("_")]
    disk_ids = {p.id for p in on_disk}
    db_ids = set(session.exec(select(Policy.id)).all())

    for policy in on_disk:
        existing = session.get(Policy, policy.id)
        if existing:
            existing.title, existing.owner, existing.body = policy.title, policy.owner, policy.body
            session.add(existing)
        else:
            session.add(policy)

    removed = db_ids - disk_ids
    if removed:
        session.exec(delete(Impact).where(Impact.policy_id.in_(removed)))
        session.exec(delete(Policy).where(Policy.id.in_(removed)))
    if db_ids and db_ids != disk_ids:
        # Mappings were made against a different library, so they are dropped entirely (summaries are kept).
        mapped = list(session.exec(select(RegItem).where(RegItem.status == "mapped")))
        for item in mapped:
            item.status = "stale"
            session.add(item)
        session.exec(delete(Impact).where(Impact.item_id.in_([i.id for i in mapped])))
        log.info("Policy library changed (+%d / -%d); mapped items marked stale", len(disk_ids - db_ids), len(removed))
    session.commit()
    return len(on_disk)


def all_policies(session: Session) -> list[Policy]:
    return list(session.exec(select(Policy).order_by(Policy.id)))
