from app.sources.base import RawItem, Source
from app.sources.federal_register import FINCEN_RULES, SEC_RULES
from app.sources.rss import FINRA_NOTICES, SEC_PRESS


def live_sources() -> list[Source]:
    return [SEC_RULES, SEC_PRESS, FINRA_NOTICES, FINCEN_RULES]


__all__ = ["RawItem", "Source", "live_sources"]
