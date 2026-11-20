"""End-to-end: demo-mode ingest → (mocked) Claude analysis + mapping → API responses."""

import pytest
from fastapi.testclient import TestClient

from app.llm import LLMError
from app.pipeline import analyze, map_policies
from app.pipeline import run as pipeline
from app.pipeline.analyze import ChangeAnalysis
from app.pipeline.map_policies import PolicyImpact, PolicyMapping


def fake_structured_call(*, system, user, output, effort="medium", max_tokens=16000):
    if output is ChangeAnalysis:
        if "Regulatory Notice" in user:
            raise LLMError("simulated failure")
        return ChangeAnalysis(
            title="Test change", summary="Something changed.", what_changed=["x"], new_obligations=["y"],
            who_is_affected="advisers", effective_date=None, comment_deadline=None,
            regulation="SEC", severity="high", topics=["custody"],
        ), "claude-opus-5-5"
    assert output is PolicyMapping
    assert "<policy_library>" in system[1]["text"] and "cache_control" in system[1]
    return PolicyMapping(impacts=[
        PolicyImpact(policy_id="custody-safeguarding", impact="high", affected_sections=["2.2"],
                     rationale="custody", recommended_action="update §2.2", confidence=0.9),
        PolicyImpact(policy_id="ai-vendor-risk", impact="none", affected_sections=[], rationale="",
                     recommended_action="", confidence=0.95),
        PolicyImpact(policy_id="not-a-real-policy", impact="high", affected_sections=[], rationale="",
                     recommended_action="", confidence=0.5),
    ]), "claude-opus-5-5"


@pytest.fixture(scope="module")
def client():
    mp = pytest.MonkeyPatch()
    mp.setattr(analyze, "structured_call", fake_structured_call)
    mp.setattr(map_policies, "structured_call", fake_structured_call)
    from app.main import app

    with TestClient(app) as c:
        st = pipeline.run_scan(limit=5)
        assert st.stage == "done", st.errors
        yield c
    mp.undo()


def test_success_clears_earlier_error():
    from sqlmodel import Session, SQLModel, create_engine

    from app.models import RegItem

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        item = RegItem(source="s", regulation="SEC", title="t", url="u", content_hash="h",
                       status="failed", error="Claude API error 401")
        s.add(item); s.commit()
        result, _ = fake_structured_call(system="", user="x", output=ChangeAnalysis)
        pipeline.save_analysis(s, item, result, "m")
        assert item.error is None and item.status == "analyzed"
        item.error = "old"
        pipeline.save_impacts(s, item, [])
        assert item.error is None and item.status == "mapped"


def test_scan_processed_items(client):
    st = pipeline.status
    assert st.new > 5 and st.processed == 5
    stats = client.get("/api/stats").json()
    assert stats["policies"] == 10
    assert stats["by_status"].get("mapped", 0) + stats["by_status"].get("failed", 0) == 5


def test_items_and_detail(client):
    items = client.get("/api/items").json()
    mapped = [i for i in items if i["status"] == "mapped"]
    assert mapped and mapped[0]["max_impact"] == "high" and mapped[0]["affected_policies"] == 1
    detail = client.get(f"/api/items/{mapped[0]['id']}").json()
    assert detail["analysis"]["severity"] == "high"
    # unknown policy ids from the model are dropped
    assert {i["policy_id"] for i in detail["impacts"]} == {"custody-safeguarding", "ai-vendor-risk"}
    report = client.get(f"/api/items/{mapped[0]['id']}/report.md").text
    assert "Custody" in report and "HIGH impact" in report
    pdf = client.get(f"/api/items/{mapped[0]['id']}/report.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and "attachment" in pdf.headers["content-disposition"]


def test_matrix_and_policies(client):
    m = client.get("/api/matrix").json()
    assert len(m["policies"]) == 10 and m["rows"]
    assert m["rows"][0]["cells"]["custody-safeguarding"] == "high"
    pol = client.get("/api/policies/custody-safeguarding").json()
    assert pol["changes"] and pol["changes"][0]["impact"] == "high"


def test_rescan_is_idempotent(client):
    before = len(client.get("/api/items").json())
    st = pipeline.run_scan(limit=0)
    assert st.new == 0 and len(client.get("/api/items").json()) == before
