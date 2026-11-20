"""Final and proposed rules for a given agency, from the Federal Register public API (no key needed)."""

from datetime import datetime

import httpx

from app.sources.base import RawItem, parse_date

API = "https://www.federalregister.gov/api/v1/documents.json"


class FederalRegisterAgency:
    def __init__(self, name: str, agency_slug: str, regulation: str):
        self.name = name
        self.agency_slug = agency_slug  # e.g. "securities-and-exchange-commission"
        self.regulation = regulation

    def fetch(self, client: httpx.Client, limit: int, since: datetime) -> list[RawItem]:
        params = {
            "per_page": limit,
            "order": "newest",
            "conditions[agencies][]": self.agency_slug,
            "conditions[type][]": ["RULE", "PRORULE"],
            "conditions[publication_date][gte]": since.date().isoformat(),
            "fields[]": ["title", "type", "abstract", "document_number", "html_url", "publication_date", "raw_text_url"],
        }
        resp = client.get(API, params=params)
        resp.raise_for_status()
        return self.parse(resp.json())

    def parse(self, payload: dict) -> list[RawItem]:
        items = []
        for doc in payload.get("results", []):
            items.append(
                RawItem(
                    source=self.name,
                    regulation=self.regulation,
                    title=f"[{doc.get('type', 'Document')}] {doc['title']}",
                    url=doc["html_url"],
                    published=parse_date(doc.get("publication_date")),
                    abstract=doc.get("abstract") or "",
                    # Plain-text rendering of the full rule; far cleaner than scraping the HTML page.
                    extra={"document_number": doc.get("document_number"), "full_text_url": doc.get("raw_text_url")},
                )
            )
        return items


SEC_RULES = FederalRegisterAgency("SEC · Federal Register", "securities-and-exchange-commission", "SEC")
FINCEN_RULES = FederalRegisterAgency("FinCEN · Federal Register", "financial-crimes-enforcement-network", "AML")
