"""Orchestrates ingest → analyze → map. Safe to run repeatedly; only pending items are processed."""

import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime

from sqlmodel import Session, delete, select

from app.config import settings
from app.db import engine
from app.llm import LLMError
from app.models import Analysis, Impact, RegItem, utcnow
from app.pipeline.analyze import analyze_item
from app.pipeline.ingest import ingest
from app.pipeline.map_policies import map_item
from app.pipeline.policies import all_policies, sync_policies

log = logging.getLogger(__name__)


@dataclass
class ScanStatus:
    running: bool = False
    stage: str = "idle"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    new: int = 0
    updated: int = 0
    processed: int = 0
    to_process: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


status = ScanStatus()
_lock = threading.Lock()


def save_analysis(session: Session, item: RegItem, result, model: str) -> Analysis:
    session.exec(delete(Analysis).where(Analysis.item_id == item.id))
    analysis = Analysis(item_id=item.id, model=model, **result.model_dump())
    session.add(analysis)
    item.regulation = result.regulation
    item.status = "analyzed"
    item.error = None  # clear any error left from an earlier failed attempt
    session.add(item)
    session.commit()
    session.refresh(analysis)
    return analysis


def save_impacts(session: Session, item: RegItem, impacts) -> None:
    session.exec(delete(Impact).where(Impact.item_id == item.id))
    for imp in impacts:
        session.add(Impact(item_id=item.id, **imp.model_dump()))
    item.status = "mapped"
    item.error = None
    session.add(item)
    session.commit()


def process_item(session: Session, item: RegItem, policies) -> None:
    analysis = session.exec(select(Analysis).where(Analysis.item_id == item.id)).first()
    if item.status in ("new", "failed") or analysis is None:
        status.stage = f"Summarizing: {item.title[:60]}"
        result, model = analyze_item(item)
        analysis = save_analysis(session, item, result, model)
    status.stage = f"Mapping to policies: {analysis.title[:60]}"
    impacts, _ = map_item(item, analysis, policies)
    save_impacts(session, item, impacts)


def remap_stale(limit: int | None = None) -> tuple[int, int, list[str]]:
    """Re-map items marked stale (after a policy-library change). Reuses saved summaries; mapping only."""
    with Session(engine) as session:
        sync_policies(session, settings.policies_dir)
        policies = all_policies(session)
        stale = list(session.exec(select(RegItem).where(RegItem.status == "stale").order_by(RegItem.published.desc())))
        stale = stale[:limit] if limit is not None else stale
        done, errors = 0, []
        for item in stale:
            try:
                process_item(session, item, policies)
                done += 1
            except LLMError as e:
                session.rollback()
                errors.append(f"{item.title[:60]}: {e}")
        return done, len(stale), errors


def run_scan(limit: int | None = None) -> ScanStatus:
    """Full pipeline. `limit` caps how many pending items get LLM processing this run."""
    if not _lock.acquire(blocking=False):
        return status
    try:
        status.__init__(running=True, stage="Fetching feeds", started_at=utcnow())
        with Session(engine) as session:
            sync_policies(session, settings.policies_dir)
            policies = all_policies(session)
            res = ingest(session)
            status.new, status.updated, status.errors = res.new, res.updated, list(res.errors)

            pending = list(
                session.exec(
                    select(RegItem)
                    .where(RegItem.status.in_(["new", "analyzed", "failed"]))
                    .order_by(RegItem.published.desc())
                )
            )
            if limit is not None:
                pending = pending[:limit]
            status.to_process = len(pending)

            for item in pending:
                try:
                    process_item(session, item, policies)
                except LLMError as e:
                    session.rollback()
                    item.status, item.error = "failed", str(e)
                    session.add(item)
                    session.commit()
                    status.failed += 1
                    status.errors.append(f"{item.title[:60]}: {e}")
                status.processed += 1
        status.stage = "done"
    except Exception as e:
        log.exception("scan failed")
        status.stage = "error"
        status.errors.append(str(e))
    finally:
        status.running = False
        status.finished_at = utcnow()
        _lock.release()
    return status


def start_scan_in_background(limit: int | None = None) -> bool:
    if status.running:
        return False
    threading.Thread(target=run_scan, kwargs={"limit": limit}, daemon=True).start()
    return True
