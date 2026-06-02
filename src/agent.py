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

from .domain import check_domain
from .nim_client import ModelClient
from .receipt import REVIEW_MARGIN_DEFAULT, Receipt
from .retrieval import SourceResult, parse_question, retrieve
from .security import scan_injection

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
    review_margin: float = REVIEW_MARGIN_DEFAULT,
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

    # Guards run before retrieval and before the model. The receipt records
    # both checks whether or not they fire, so an auditor sees they ran.
    security = scan_injection(question)
    receipt.set_security(
        injection_detected=security.injection_detected,
        action=security.action,
        matched_patterns=security.matched_patterns,
        note=security.note,
    )
    domain = check_domain(parsed)
    receipt.set_answerability(
        in_domain=domain.in_domain,
        reason=domain.reason,
        matched_ood_terms=domain.matched_ood_terms,
        matched_anchors=domain.matched_anchors,
    )

    ticket = f"HUMAN-{receipt.receipt_id[:8].upper()}"

    # A failed guard short-circuits before retrieval and before the model. We
    # deliberately do NOT query any source: an injection attempt or an
    # out-of-domain question must leave an empty sources_queried list, so the
    # receipt cannot be misread as "the agent worked over real data."
    if security.injection_detected or not domain.in_domain:
        receipt.set_prompt_context("")
        receipt.confidence_threshold = {"caveat": caveat_threshold, "abstain": abstain_threshold}
        decision = receipt.decide_fallback(
            blocked=security.injection_detected,
            out_of_domain=not domain.in_domain,
        )
        receipt.evaluate_review_flag(margin=review_margin)
        if decision.path == "blocked_injection":
            answer = (
                "[BLOCKED] A prompt-injection attempt was detected in the input "
                f"({', '.join(security.matched_patterns)}). The question was not sent to the model "
                "and no data was retrieved. The attempt is recorded in the receipt for audit."
            )
        else:
            answer = (
                f"[ABSTAIN] {domain.reason} No in-domain sources were queried. Routed to a human "
                f"reviewer (queue ticket {ticket}). The decision is recorded in the receipt."
            )
        receipt.set_answer_summary(answer)
        receipt_dict = receipt.finalize()
        path = receipt.write(receipts_dir)
        return answer, receipt_dict, path

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
    receipt.evaluate_review_flag(margin=review_margin)

    if decision.path == "abstain_route_to_human":
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
