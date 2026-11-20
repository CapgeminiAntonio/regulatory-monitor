"""Step 1: pull feeds, dedupe, fetch full text, and store RegItems."""

import logging
from dataclasses import dataclass, field

import httpx
import trafilatura
from sqlmodel import Session, select

from app.config import settings
from app.models import RegItem, utcnow
from app.sources import RawItem, live_sources
from app.sources.base import default_since, http_client
from app.sources.fixtures import load_fixtures

log = logging.getLogger(__name__)


@dataclass
class IngestResult:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


def fetch_full_text(client: httpx.Client, raw: RawItem) -> str:
    url = raw.extra.get("full_text_url") or raw.url
    try:
        resp = client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("full-text fetch failed for %s: %s", url, e)
        return ""
    if "text/plain" in resp.headers.get("content-type", ""):
        return resp.text
    return trafilatura.extract(resp.text, include_tables=True, favor_recall=True) or ""


def upsert(session: Session, raw: RawItem, full_text: str, result: IngestResult) -> RegItem | None:
    """Insert new items; if a known URL's content changed, update it and queue it for re-analysis."""
    existing = session.exec(select(RegItem).where(RegItem.url == raw.url)).first()
    if existing and existing.content_hash == raw.content_hash:
        result.unchanged += 1
        return None
    if existing:
        existing.title, existing.abstract = raw.title, raw.abstract
        existing.full_text = full_text or existing.full_text
        existing.content_hash, existing.status, existing.error = raw.content_hash, "new", None
        existing.fetched_at = utcnow()
        session.add(existing)
        result.updated += 1
        return existing
    item = RegItem(
        source=raw.source,
        regulation=raw.regulation,
        title=raw.title,
        url=raw.url,
        published=raw.published,
        abstract=raw.abstract,
        full_text=full_text,
        content_hash=raw.content_hash,
    )
    session.add(item)
    result.new += 1
    return item


def collect_live(limit: int, lookback_days: int) -> tuple[list[tuple[RawItem, str]], list[str]]:
    since = default_since(lookback_days)
    rows: list[tuple[RawItem, str]] = []
    errors: list[str] = []
    with http_client() as client:
        for source in live_sources():
            try:
                raws = source.fetch(client, limit, since)
            except Exception as e:  # one broken feed shouldn't stop the others
                log.exception("source %s failed", source.name)
                errors.append(f"{source.name}: {e}")
                continue
            for raw in raws:
                rows.append((raw, fetch_full_text(client, raw)))
    return rows, errors


def ingest(session: Session) -> IngestResult:
    result = IngestResult()
    if settings.demo_mode:
        rows = load_fixtures(settings.fixtures_dir)
        if not rows:
            result.errors.append("DEMO_MODE is on but data/fixtures/feed_items.json is missing")
    else:
        rows, result.errors = collect_live(settings.max_items_per_source, settings.lookback_days)
    for raw, text in rows:
        if raw.url:
            upsert(session, raw, text, result)
    session.commit()
    return result
