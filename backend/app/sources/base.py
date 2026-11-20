import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx

USER_AGENT = "regulatory-monitor-demo/0.1"
TIMEOUT = httpx.Timeout(25.0)


@dataclass
class RawItem:
    source: str
    regulation: str  # SEC | GDPR | EU_AI_ACT | OTHER
    title: str
    url: str
    published: datetime | None = None
    abstract: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.title}\n{self.abstract}".encode()).hexdigest()


class Source(Protocol):
    name: str

    def fetch(self, client: httpx.Client, limit: int, since: datetime) -> list[RawItem]: ...


def http_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            # e.g. FINRA's "Nov 18, 2026" / "November 18, 2026"
            for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


def default_since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)
