# Regulatory Change Monitor

Watches US financial-services regulatory feeds (SEC, FINRA, FinCEN), uses Claude to summarize what changed, and maps each change to the client policies it affects. For each affected policy it gives a rationale, the affected sections, and a recommended action.

**The problem:** compliance teams track dozens of regulators by hand, then work out which internal policies each update touches. This tool turns that into a ranked feed, an impact matrix, and an exportable impact report.

## How it works

```
Feeds ──► Ingest (fetch, dedupe, full text) ──► Analyze (Claude → structured summary)
                                                        │
Client policy library (markdown) ──────────────► Map (Claude → impact per policy)
                                                        │
                                   SQLite ◄─────────────┘ ──► FastAPI ──► React UI
```

| Source | Regulation | Feed |
|---|---|---|
| SEC final & proposed rules (full text) | SEC | Federal Register API |
| SEC press releases (rulemaking only) | SEC | sec.gov RSS |
| FINRA Regulatory Notices | FINRA | finra.org RSS |
| FinCEN final & proposed rules (AML, special measures) | FinCEN / AML | Federal Register API |

Scans run automatically once a week (Mondays 07:00 by default, set with `SCAN_DAY_OF_WEEK` / `SCAN_HOUR`) while the backend is running, or on demand with **Scan now**.

- **Analyze** (`backend/app/pipeline/analyze.py`): Claude (`claude-opus-5-5`) returns a validated Pydantic `ChangeAnalysis`: summary, what changed, new obligations, effective date, severity and topics. Long rules are capped at 120k characters, and the model is told when it is reading an excerpt.
- **Map** (`backend/app/pipeline/map_policies.py`): the client profile and the whole policy library go in a cached system prompt (prompt caching), and Claude rates every policy none/low/medium/high with section references. With about 10 policies this needs no vector DB. For hundreds of policies, add an embeddings retrieval step to shortlist candidates first.
- **Resilience:** server-side refusal fallbacks are enabled, failed items are marked `failed` and retried on the next scan, and content changes to a known URL re-queue the item.
- The **client** is the fictional *Northwind Wealth & Asset Management* (`data/policies/`): an SEC-registered adviser with an affiliated FINRA broker-dealer and funds, serving clients across the Americas. It has 10 policies (custody, marketing, best interest, books & records, code of ethics, AML & sanctions, privacy & cyber, trading, fund governance, AI & third-party risk) plus `_client-profile.md`.
- **Changing policies:** when policy files are added or removed, existing mappings are dropped and those items are marked *not mapped* (summaries are kept). Nothing is re-mapped automatically. Run `uv run python -m app.cli remap` (optionally `--limit N` or `--model anthropic.claude-sonnet-5-5`) when you want to pay to refresh them. Editing the text of an existing policy does not mark anything stale.

## Run it

Prereqs: [uv](https://docs.astral.sh/uv/), Node 20+, and an LLM key, either:
- a **Capgemini AI Passport Gateway** key (`LLM_PROVIDER=gateway`, the default). Claude is called through the gateway's OpenAI-compatible Responses API as `anthropic.claude-opus-5-5`, or
- an **Anthropic API** key (`LLM_PROVIDER=anthropic`).

```bash
cp .env.example .env              # add GATEWAY_API_KEY (or ANTHROPIC_API_KEY)

# backend: http://127.0.0.1:8000  (API docs at /docs)
cd backend
uv sync
uv run uvicorn app.main:app --reload

# frontend: http://localhost:5173
cd frontend
npm install
npm run dev
```

Click **Scan now** in the UI, or run `uv run python -m app.cli scan --limit 5` for a quick, cheap first run.

Other commands (from `backend/`):

```bash
uv run python -m app.cli fetch      # preview live feed items (no LLM calls)
uv run python -m app.cli snapshot   # refresh offline fixtures in data/fixtures/
uv run pytest                       # tests (Claude is mocked; no key needed)
```

**Offline demo:** set `DEMO_MODE=true` to ingest from `data/fixtures/feed_items.json` (captured 2026-11-18) instead of live feeds, so a demo doesn't depend on regulator websites. Analysis still calls Claude. Run one scan before the demo, and the results persist in `backend/regmon.db`.

## Demo script (~3 min)
1. **Problem:** "Northwind's compliance team tracks the SEC, FINRA and FinCEN by hand, then works out which policies each change touches."
2. **Feed:** click *Scan now*. New items stream in with severity and the number of affected policies.
3. **Detail:** open the SEC crypto custody proposal, FINRA's Rule 2210 projections notice, or a FinCEN funds-transfer (Travel Rule) proposal. Show the summary, the new obligations, then the affected policies, each with a section reference, a rationale and an action. Click **Download PDF report** to get a formatted impact report to hand to policy owners.
4. **Matrix:** a heatmap of every change against every policy, showing where the work concentrates.
5. **Policy view:** open *Custody & Safeguarding* or *AML, KYC & Sanctions* to see everything pending against it, next to the policy text.
6. **Next steps:** real client policies (upload), more regulators (CFPB, OCC, NYDFS, state privacy laws, Canadian CSA/CIRO), owner notifications via email or Teams, and an approval workflow.

## Repo layout
```
backend/app/sources/    feed adapters (Federal Register, RSS) + fixtures
backend/app/pipeline/   ingest → analyze → map, orchestration
backend/app/api/        REST endpoints
backend/tests/          parser, dedupe, SDK request-shape, end-to-end API tests
frontend/src/pages/     Feed, ItemDetail, Matrix, Policies, PolicyDetail
data/policies/          sample client policy library
```

_All analysis is AI-generated and must be verified against the source before acting on it._
