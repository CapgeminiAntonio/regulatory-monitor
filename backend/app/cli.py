"""Command-line helpers.

    uv run python -m app.cli scan [--limit N]               # run the full pipeline once
    uv run python -m app.cli remap [--limit N] [--model M]  # re-map "stale" items after policy changes (mapping only)
    uv run python -m app.cli snapshot                       # cache live feed items as offline demo fixtures
    uv run python -m app.cli fetch                          # preview what the live feeds return (no LLM calls)
"""

import argparse
import logging

from app.config import settings
from app.db import init_db
from app.pipeline.analyze import MAX_CHARS
from app.pipeline.ingest import collect_live
from app.pipeline.run import remap_stale, run_scan
from app.sources.fixtures import save_fixtures


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="regmon")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--limit", type=int, default=None)
    remap = sub.add_parser("remap")
    remap.add_argument("--limit", type=int, default=None)
    remap.add_argument("--model", default=None, help="override the model for this run, e.g. anthropic.claude-sonnet-5-5")
    sub.add_parser("snapshot")
    sub.add_parser("fetch")
    args = parser.parse_args()

    if args.cmd == "scan":
        init_db()
        st = run_scan(limit=args.limit)
        print(f"new={st.new} updated={st.updated} processed={st.processed} failed={st.failed}")
        for e in st.errors:
            print("  !", e)
    elif args.cmd == "remap":
        init_db()
        if args.model:
            settings.gateway_model = settings.anthropic_model = args.model
        done, total, errors = remap_stale(limit=args.limit)
        print(f"re-mapped {done}/{total} stale items")
        for e in errors:
            print("  !", e)
    elif args.cmd in ("snapshot", "fetch"):
        rows, errors = collect_live(settings.max_items_per_source, settings.lookback_days)
        for raw, text in rows:
            print(f"[{raw.regulation:6}] {raw.published.date() if raw.published else '?'}  {raw.title[:80]}  ({len(text)} chars)")
        for e in errors:
            print("  !", e)
        if args.cmd == "snapshot":
            # Store only what the analyzer would read, keeping the fixture file small.
            rows = [(raw, text[:MAX_CHARS]) for raw, text in rows]
            print("saved", save_fixtures(settings.fixtures_dir, rows))


if __name__ == "__main__":
    main()
