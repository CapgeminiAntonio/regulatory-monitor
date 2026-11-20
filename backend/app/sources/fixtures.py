"""Offline demo data: cached feed items (with full text) saved by `python -m app.cli snapshot`."""

import json
from pathlib import Path

from app.sources.base import RawItem, parse_date

FIXTURE_FILE = "feed_items.json"


def load_fixtures(fixtures_dir: Path) -> list[tuple[RawItem, str]]:
    path = fixtures_dir / FIXTURE_FILE
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        item = RawItem(
            source=r["source"],
            regulation=r["regulation"],
            title=r["title"],
            url=r["url"],
            published=parse_date(r.get("published")),
            abstract=r.get("abstract", ""),
        )
        out.append((item, r.get("full_text", "")))
    return out


def save_fixtures(fixtures_dir: Path, rows: list[tuple[RawItem, str]]) -> Path:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    path = fixtures_dir / FIXTURE_FILE
    data = [
        {
            "source": it.source,
            "regulation": it.regulation,
            "title": it.title,
            "url": it.url,
            "published": it.published.isoformat() if it.published else None,
            "abstract": it.abstract,
            "full_text": text,
        }
        for it, text in rows
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
