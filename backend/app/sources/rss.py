"""Generic RSS sources: SEC press releases, EDPB publications (GDPR), EU AI Act news."""

import re
from datetime import datetime

import feedparser
import httpx

from app.sources.base import RawItem, parse_date, strip_html


class RssSource:
    def __init__(
        self,
        name: str,
        url: str,
        regulation: str,
        include: str | None = None,
        exclude: str | None = None,
        title_only: bool = False,
    ):
        self.name = name
        self.url = url
        self.regulation = regulation
        self.include = re.compile(include, re.I) if include else None
        self.exclude = re.compile(exclude, re.I) if exclude else None
        self.title_only = title_only  # apply include/exclude to the title only (stricter)

    def fetch(self, client: httpx.Client, limit: int, since: datetime) -> list[RawItem]:
        resp = client.get(self.url)
        resp.raise_for_status()
        return self.parse(resp.content, limit, since)

    def parse(self, content: bytes, limit: int, since: datetime | None = None) -> list[RawItem]:
        feed = feedparser.parse(content)
        items: list[RawItem] = []
        for entry in feed.entries:
            title = strip_html(entry.get("title", ""))
            summary = strip_html(entry.get("summary", ""))
            haystack = title if self.title_only else f"{title} {summary}"
            if self.include and not self.include.search(haystack):
                continue
            if self.exclude and self.exclude.search(haystack):
                continue
            published = parse_date(entry.get("published") or entry.get("updated"))
            if since and published and published < since:
                continue
            items.append(
                RawItem(
                    source=self.name,
                    regulation=self.regulation,
                    title=title,
                    url=entry.get("link", ""),
                    published=published,
                    abstract=summary[:2000],
                )
            )
            if len(items) >= limit:
                break
        return items


SEC_PRESS = RssSource(
    "SEC · Press Releases",
    "https://www.sec.gov/news/pressreleases.rss",
    "SEC",
    # Keep rulemaking/guidance; skip routine enforcement & personnel announcements.
    include=r"\b(adopt|propos|rule|amend|guidance|disclosure|staff statement|exemptive|cyber|AI|artificial intelligence)",
    exclude=r"\b(charges|names|appoint|sentenced|settle|obtains? judgment|announces departure)\b",
)

FINRA_NOTICES = RssSource(
    "FINRA · Regulatory Notices",
    "https://www.finra.org/rules-guidance/notices/rss",
    "FINRA",
    # Regulatory Notices carry rule changes and guidance; Information Notices are mostly operational
    # (holiday closings, fee schedules), so they're skipped.
    include=r"^Regulatory Notice",
    title_only=True,
)
