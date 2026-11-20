from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import RegItem
from app.pipeline.ingest import IngestResult, upsert
from app.pipeline.policies import parse_policy_file, sync_policies
from app.config import settings
from app.sources.base import RawItem
from app.sources.federal_register import SEC_RULES
from app.sources.rss import RssSource

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>SEC Adopts Cybersecurity Rule</title><link>https://x/1</link>
  <pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;New rule&lt;/p&gt;</description></item>
<item><title>SEC Charges Adviser With Fraud</title><link>https://x/2</link>
  <pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate><description>enforcement</description></item>
<item><title>Old guidance</title><link>https://x/3</link>
  <pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate><description>rule</description></item>
</channel></rss>"""


def test_rss_filters_and_strips_html():
    src = RssSource("t", "u", "SEC", include=r"\b(adopt|rule)", exclude=r"\bcharges\b")
    items = src.parse(RSS, limit=10, since=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert [i.url for i in items] == ["https://x/1"]
    assert items[0].abstract == "New rule"
    assert items[0].published.year == 2026


def test_title_only_filter():
    src = RssSource("t", "u", "EU_AI_ACT", include=r"\bAI\b", title_only=True)
    feed = b"""<rss><channel><item><title>Web Summit</title><link>a</link><description>AI everywhere</description></item>
    <item><title>AI Office guidance</title><link>b</link></item></channel></rss>"""
    assert [i.url for i in src.parse(feed, limit=10)] == ["b"]


def test_federal_register_parse():
    payload = {"results": [{"title": "Custody Rules", "type": "Proposed Rule", "html_url": "https://fr/1",
                            "publication_date": "2026-10-06", "abstract": "abc", "document_number": "2026-1",
                            "raw_text_url": "https://fr/1.txt"}]}
    [item] = SEC_RULES.parse(payload)
    assert item.title == "[Proposed Rule] Custody Rules"
    assert item.extra["full_text_url"] == "https://fr/1.txt"
    assert item.regulation == "SEC"


def test_upsert_dedupes_and_detects_changes():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        raw = RawItem(source="s", regulation="SEC", title="A", url="https://u", abstract="v1")
        res = IngestResult()
        upsert(s, raw, "", res); s.commit()
        upsert(s, raw, "", res); s.commit()
        assert (res.new, res.unchanged) == (1, 1)

        item = s.exec(select(RegItem)).one()
        item.status = "mapped"; s.add(item); s.commit()

        changed = RawItem(source="s", regulation="SEC", title="A", url="https://u", abstract="v2")
        upsert(s, changed, "", res); s.commit()
        item = s.exec(select(RegItem)).one()
        assert res.updated == 1 and item.status == "new" and item.abstract == "v2"


def test_finra_style_dates():
    from app.sources.base import parse_date

    assert parse_date("Nov 18, 2026").date().isoformat() == "2026-11-18"
    assert parse_date("Fri, 13 Nov 2026 10:00:00 GMT").day == 13
    assert parse_date("garbage") is None


def test_policy_change_marks_mapped_items_stale(tmp_path):
    from app.models import Impact, Policy

    (tmp_path / "a.md").write_text("---\nid: a\ntitle: A\n---\nbody", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\nid: b\ntitle: B\n---\nbody", encoding="utf-8")
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        sync_policies(s, tmp_path)
        item = RegItem(source="s", regulation="SEC", title="t", url="u", content_hash="h", status="mapped")
        s.add(item); s.commit()
        s.add(Impact(item_id=item.id, policy_id="a", impact="high")); s.add(Impact(item_id=item.id, policy_id="b", impact="low"))
        s.commit()

        sync_policies(s, tmp_path)  # unchanged library: nothing happens
        assert s.get(RegItem, item.id).status == "mapped"

        (tmp_path / "b.md").unlink()
        sync_policies(s, tmp_path)
        assert s.get(RegItem, item.id).status == "stale"
        assert list(s.exec(select(Impact))) == []  # all old mappings dropped
        assert [p.id for p in s.exec(select(Policy))] == ["a"]


def test_policy_library_loads():
    p = parse_policy_file(settings.policies_dir / "ai-vendor-risk.md")
    assert p.id == "ai-vendor-risk" and p.owner and "## 3." in p.body
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        assert sync_policies(s, settings.policies_dir) == 10  # _client-profile.md is excluded
