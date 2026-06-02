"""
Answerability layer. Decides whether a question can be answered from this
agent's data domain at all, before confidence math runs.

This closes a gap the confidence score alone papers over. The dataset covers
US retail inventory, sales, and supply signals keyed by region, SKU, and store.
A question like "which suppliers in Latvia are most reliable?" has no in-domain
anchor: Latvia is not a region we hold and "reliability ranking" is not a column
we compute. The old behavior returned the full table and leaned on a low
specificity score to push the answer under the abstain line. That abstains for
the wrong reason ("low confidence") instead of the true one ("out of domain"),
and a reviewer reading the receipt could not tell the difference. This module
makes the true reason explicit and records it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .retrieval import REGIONS, STOCKOUT_KEYWORDS, ParsedQuery

# Entity vocabulary the data can actually speak to.
_IN_DOMAIN_ANCHORS = (
    "sku",
    "skus",
    "store",
    "stores",
    "inventory",
    "stock",
    "reorder",
    "on hand",
    "on-hand",
    "units",
    "supplier",
    "suppliers",
    "supply",
    "restock",
    "backorder",
    "eta",
)

# Geographies outside the US-region domain. If one of these appears and no
# in-domain region matched, the question is asking about a place we do not hold.
_OUT_OF_DOMAIN_PLACES = (
    "latvia", "germany", "france", "spain", "italy", "poland", "ukraine",
    "china", "japan", "india", "korea", "vietnam", "thailand", "taiwan",
    "canada", "mexico", "brazil", "argentina", "chile",
    "uk", "england", "ireland", "scotland", "australia", "africa",
    "europe", "asia", "emea", "apac", "latam",
)


@dataclass
class Answerability:
    in_domain: bool
    reason: str
    matched_ood_terms: list[str] = field(default_factory=list)
    matched_anchors: list[str] = field(default_factory=list)


def check_domain(parsed: ParsedQuery) -> Answerability:
    q = parsed.raw.lower()

    ood_terms = [p for p in _OUT_OF_DOMAIN_PLACES if _word_in(p, q)]
    anchors = [a for a in _IN_DOMAIN_ANCHORS if a in q]
    has_anchor = (
        parsed.region is not None
        or parsed.intent == "stockout_risk"
        or bool(anchors)
        or any(kw in q for kw in STOCKOUT_KEYWORDS)
    )

    # Any out-of-domain geography wins, even alongside a known region. A
    # compound question like "stockout risk in the Midwest and Latvia" is only
    # partly answerable, and the honest move is to route it to a human rather
    # than answer the in-domain half and silently drop Latvia.
    if ood_terms:
        return Answerability(
            in_domain=False,
            reason=(
                f"Question references out-of-domain geography ({', '.join(ood_terms)}). "
                f"This agent holds US-region retail data only: {', '.join(sorted(set(REGIONS.values())))}."
            ),
            matched_ood_terms=ood_terms,
            matched_anchors=anchors,
        )

    if not has_anchor:
        return Answerability(
            in_domain=False,
            reason=(
                "Question has no in-domain anchor (no region, no inventory/supply intent, "
                "no recognized retail entity). Nothing in the dataset can ground an answer."
            ),
            matched_ood_terms=ood_terms,
            matched_anchors=anchors,
        )

    return Answerability(in_domain=True, reason="", matched_ood_terms=ood_terms, matched_anchors=anchors)


def _word_in(term: str, text: str) -> bool:
    # Word-boundary match so "uk" doesn't fire inside "stuck" and "asia" doesn't
    # fire inside a larger token.
    return re.search(rf"\b{re.escape(term)}\b", text) is not None
