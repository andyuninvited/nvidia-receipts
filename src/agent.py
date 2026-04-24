"""
Agent orchestration. Single entrypoint: run_agent.

Flow:
    parse question -> retrieve from CSVs -> populate receipt sources ->
    compute confidence -> decide fallback -> call NIM (or skip on abstain)
    -> finalize receipt -> return (answer, receipt_dict, receipt_path)

The receipt is populated as the agent executes, not after the fact. That
ordering matters: a receipt assembled retroactively can be tampered with.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .nim_client import ModelClient
from .receipt import Receipt
from .retrieval import SourceResult, parse_question, retrieve

SYSTEM_PROMPT = (
    "You are a retail operations assistant. Answer the operator's question using ONLY the data "
    "provided in the context block. Do not invent SKUs, store IDs, supplier names, dates, or numbers. "
    "If the data does not support an answer, say so explicitly. Be concise. Lead with the headline finding, "
    "then list specific SKU/store/supplier rows that drove it. Cite row IDs in brackets like [INV-1042-M217]."
)


def run_agent(
    question: str,
    *,
    user: str,
    data_dir: Path | str,
    receipts_dir: Path | str,
    reference_date: Optional[date] = None,
    caveat_threshold: float = 0.65,
    abstain_threshold: float = 0.40,
    client: Optional[ModelClient] = None,
) -> tuple[str, dict, Path]:
    client = client or ModelClient()

    receipt = Receipt.start(
        query=question,
        user=user,
        model_provider=client.provider,
        model_id=client.model,
        endpoint=client.base_url,
        expected_sources=3,
    )

    parsed = parse_question(question)
    sources = retrieve(parsed, data_dir, reference_date=reference_date)

    for src in sources.values():
        receipt.add_source(
            source=src.name,
            filter_desc=src.filter_desc,
            row_ids=src.row_ids,
            newest_row_age_days=src.newest_row_age_days,
        )

    context_block = _build_context_block(parsed.raw, sources)
    receipt.set_prompt_context(context_block)
    receipt.compute_confidence(
        caveat=caveat_threshold,
        abstain=abstain_threshold,
        query_specificity=_query_specificity(parsed),
    )
    decision = receipt.decide_fallback()

    if decision.path == "abstain_route_to_human":
        ticket = f"HUMAN-{receipt.receipt_id[:8].upper()}"
        answer = (
            f"[ABSTAIN] Confidence {receipt.confidence} fell below the abstain threshold "
            f"{abstain_threshold}. This query has been routed to a human reviewer "
            f"(queue ticket {ticket}). Sources touched are recorded in the receipt."
        )
    else:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=context_block,
            evidence=sources,
        )
        answer = result.text
        receipt.model.provider = result.provider
        receipt.model.model_id = result.model_id
        receipt.model.endpoint = result.endpoint
        if decision.path == "answer_with_caveat":
            answer = (
                f"[LOW CONFIDENCE {receipt.confidence} < {caveat_threshold}] "
                f"Treat as directional. Verify against source rows before acting.\n\n{answer}"
            )

    receipt.set_answer_summary(answer)
    receipt_dict = receipt.finalize()
    path = receipt.write(receipts_dir)
    return answer, receipt_dict, path


def _query_specificity(parsed) -> float:
    """0.0 if parser extracted no signals, 0.5 if one, 1.0 if both region and intent."""
    extracted = (1 if parsed.region else 0) + (1 if parsed.intent != "general" else 0)
    return extracted / 2.0


def _build_context_block(question: str, sources: dict[str, SourceResult]) -> str:
    parts = [
        "QUESTION:",
        question,
        "",
        "RETRIEVED DATA:",
    ]
    for src in sources.values():
        parts.append(f"\n=== {src.name} ===")
        parts.append(f"Filter applied: {src.filter_desc}")
        parts.append(f"Rows matched: {len(src.rows)}")
        if not src.rows:
            parts.append("(no rows)")
            continue
        parts.append("")
        parts.append(_rows_to_csv(src.rows))
    parts.append("\nEND OF DATA.")
    return "\n".join(parts)


def _rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    cols = list(rows[0].keys())
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(str(r.get(c, "")) for c in cols))
    return "\n".join(lines)
