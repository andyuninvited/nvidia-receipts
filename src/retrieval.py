"""
Retrieval layer. Keyword + region filter over the 3 mock CSVs.

Returns one bundle per source with: matched rows (list of dicts), row_ids,
age of the freshest row, and a human-readable filter description that lands
in the receipt. The filter description is what an auditor reads, so it is
plain English not pandas code.

Uses the stdlib csv module so the code path is dependency-light enough to
run inside a Vercel Function with a sub-second cold start.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

REGIONS = {
    "midwest": "Midwest",
    "west": "West",
    "south": "South",
    "northeast": "Northeast",
    "southwest": "Southwest",
}

STOCKOUT_KEYWORDS = (
    "stockout",
    "stock out",
    "out of stock",
    "running low",
    "low inventory",
    "at risk",
    "depleted",
    "deplete",
    "shortage",
)


@dataclass
class ParsedQuery:
    raw: str
    region: Optional[str]
    intent: str

    def describe_region(self) -> str:
        return self.region if self.region else "all regions"


@dataclass
class SourceResult:
    name: str
    rows: list[dict]
    filter_desc: str
    newest_row_age_days: Optional[float]

    @property
    def row_ids(self) -> list[str]:
        return [str(r["row_id"]) for r in self.rows]


def parse_question(question: str) -> ParsedQuery:
    q = question.lower()
    region = next((REGIONS[k] for k in REGIONS if k in q), None)
    intent = "stockout_risk" if any(kw in q for kw in STOCKOUT_KEYWORDS) else "general"
    return ParsedQuery(raw=question, region=region, intent=intent)


def retrieve(
    parsed: ParsedQuery,
    data_dir: Path | str,
    *,
    reference_date: Optional[date] = None,
) -> dict[str, SourceResult]:
    data_dir = Path(data_dir)
    today = reference_date or date.today()

    inventory_full = _load_csv(data_dir / "inventory.csv")
    sales_full = _load_csv(data_dir / "sales.csv")
    supply_full = _load_csv(data_dir / "supply_signals.csv")

    inventory = inventory_full
    inv_filter_parts = []

    if parsed.region:
        inventory = [r for r in inventory if r["store_region"] == parsed.region]
        inv_filter_parts.append(f"store_region == '{parsed.region}'")

    if parsed.intent == "stockout_risk":
        inventory = [r for r in inventory if int(r["on_hand_units"]) < int(r["reorder_point"])]
        inv_filter_parts.append("on_hand_units < reorder_point")

    inv_filter_desc = " AND ".join(inv_filter_parts) if inv_filter_parts else "no filter (full table)"

    if not inventory:
        sales: list[dict] = []
        supply: list[dict] = []
        sales_filter_desc = "no inventory matches; sales not pulled"
        supply_filter_desc = "no inventory matches; supply signals not pulled"
    else:
        sku_store_keys = {(r["sku"], r["store_id"]) for r in inventory}
        skus = sorted({r["sku"] for r in inventory})
        sales = [r for r in sales_full if (r["sku"], r["store_id"]) in sku_store_keys]
        sales_filter_desc = f"(sku, store_id) joined to filtered inventory ({len(sku_store_keys)} pairs)"
        supply = [r for r in supply_full if r["sku"] in set(skus)]
        supply_filter_desc = f"sku in {skus}"

    return {
        "inventory": SourceResult(
            name="inventory.csv",
            rows=inventory,
            filter_desc=inv_filter_desc,
            newest_row_age_days=_newest_age(inventory, "last_inventory_check", today),
        ),
        "sales": SourceResult(
            name="sales.csv",
            rows=sales,
            filter_desc=sales_filter_desc,
            newest_row_age_days=_newest_age(sales, "week_ending", today),
        ),
        "supply_signals": SourceResult(
            name="supply_signals.csv",
            rows=supply,
            filter_desc=supply_filter_desc,
            newest_row_age_days=_newest_age(supply, "signal_date", today),
        ),
    }


def _load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _newest_age(rows: list[dict], date_col: str, today: date) -> Optional[float]:
    if not rows:
        return None
    parsed = []
    for r in rows:
        v = r.get(date_col)
        if not v:
            continue
        try:
            parsed.append(date.fromisoformat(v))
        except ValueError:
            continue
    if not parsed:
        return None
    newest = max(parsed)
    return float((today - newest).days)
