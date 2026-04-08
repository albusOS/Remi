"""RERouter — real-estate-specific request classifier.

Implements the ``RequestRouter`` protocol from ``agent/runtime/router.py``.
All domain knowledge (operation names, keyword patterns, entity ID formats)
lives here in the application layer, not in the kernel.

Rule-based today.  Swappable for a Haiku classifier call later by
implementing the same protocol.
"""

from __future__ import annotations

import re

import structlog

from remi.agent.runtime.router import RoutingDecision, Tier

logger = structlog.get_logger(__name__)


_GREETING_RE = re.compile(
    r"^(h(i|ello|ey)|good\s+(morning|afternoon|evening)|thanks?|thank\s+you|"
    r"ok(ay)?|sure|got\s+it|sounds?\s+good|great|cool|bye|see\s+ya|cheers|"
    r"yep|nope|yes|no)[\s!?.]*$",
    re.IGNORECASE,
)

_AGENT_SIGNALS = re.compile(
    r"\b(writ(e|ing)|generat(e|ing)|creat(e|ing)\s+(a\s+)?(report|plan|analysis)|"
    r"analyz(e|ing)|compar(e|ing)|correlat(e|ion)|regress(ion)?|"
    r"trend.{0,5}over\s+time|deep\s+dive|investigat(e|ion)|"
    r"action\s+(plan|item)|python|script|code|plot|chart|graph|csv|excel|"
    r"delegat(e|ion)|research(er)?)\b",
    re.IGNORECASE,
)

_QUERY_OPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bdashboard\b", re.I), "dashboard"),
    (re.compile(r"\bdelinquen(t|cy|cies)\b", re.I), "delinquency"),
    (re.compile(r"\bvacanc(y|ies|t)\b", re.I), "vacancies"),
    (re.compile(r"\bexpir(ing|ation|e)\s*(lease)?s?\b", re.I), "expiring_leases"),
    (re.compile(r"\brent\s*roll\b", re.I), "rent_roll"),
    (re.compile(r"\brank(ing)?s?\b", re.I), "rankings"),
    (re.compile(r"\bmaintenanc(e|ing)\b", re.I), "maintenance"),
    (re.compile(r"\blease(s)?\b", re.I), "leases"),
    (re.compile(r"\bmanager.{0,10}review\b", re.I), "manager_review"),
    (re.compile(r"\bmanager(s)?\b", re.I), "managers"),
    (re.compile(r"\bpropert(y|ies)\b", re.I), "properties"),
    (re.compile(r"\bunit(s)?\b", re.I), "properties"),
    (re.compile(r"\btenant(s)?\b", re.I), "leases"),
    (re.compile(r"\boccupan(cy|t)\b", re.I), "dashboard"),
    (re.compile(r"\bportfolio\b", re.I), "dashboard"),
    (re.compile(r"\boverdue\b", re.I), "delinquency"),
    (re.compile(r"\bbalance(s)?\b.*\b(ow(e|ed|ing)|due|outstand)\b", re.I), "delinquency"),
]

_HOW_MANY_RE = re.compile(r"\b(how\s+many|count|total|number\s+of)\b", re.I)

_ENTITY_ID_RES = [
    (re.compile(r"\bmanager[_-]?id\s*[:=]\s*(\S+)", re.I), "manager_id"),
    (re.compile(r"\bproperty[_-]?id\s*[:=]\s*(\S+)", re.I), "property_id"),
]


class RERouter:
    """Rule-based classifier for real estate questions.

    Falls back to ``Tier.AGENT`` when uncertain — safest default.
    """

    def classify(self, question: str, *, manager_id: str | None = None) -> RoutingDecision:
        stripped = question.strip()

        if not stripped or _GREETING_RE.match(stripped):
            return RoutingDecision(tier=Tier.DIRECT)

        if len(stripped.split()) <= 3 and not any(
            p.search(stripped) for p, _ in _QUERY_OPS
        ):
            return RoutingDecision(tier=Tier.DIRECT)

        if _AGENT_SIGNALS.search(stripped):
            return RoutingDecision(tier=Tier.AGENT)

        params: dict[str, str] = {}
        if manager_id:
            params["manager_id"] = manager_id

        for pattern, param_name in _ENTITY_ID_RES:
            m = pattern.search(stripped)
            if m:
                params[param_name] = m.group(1)

        for pattern, op in _QUERY_OPS:
            if pattern.search(stripped):
                if _HOW_MANY_RE.search(stripped):
                    op = _refine_count_query(stripped, op)
                logger.debug("re_router_classified", tier="query", operation=op, params=params)
                return RoutingDecision(tier=Tier.QUERY, operation=op, params=params)

        if "search" in stripped.lower() or "find" in stripped.lower():
            return RoutingDecision(tier=Tier.QUERY, operation="search", params=params)

        if "?" in stripped and len(stripped.split()) < 15:
            return RoutingDecision(tier=Tier.QUERY, operation="dashboard", params=params)

        return RoutingDecision(tier=Tier.AGENT)


def _refine_count_query(question: str, default_op: str) -> str:
    q = question.lower()
    if "propert" in q:
        return "properties"
    if "unit" in q:
        return "properties"
    if "lease" in q:
        return "leases"
    if "tenant" in q:
        return "leases"
    if "maintenanc" in q:
        return "maintenance"
    if "vacan" in q:
        return "vacancies"
    return default_op
