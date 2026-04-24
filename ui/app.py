"""
Streamlit two-panel UI.

Left: question input, answer.
Right: the receipt, rendered so a non-engineer auditor can read it.
Sidebar: identity, model, thresholds, sample questions.

Run with:   streamlit run ui/app.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agent import run_agent  # noqa: E402
from src.nim_client import DEFAULT_BASE_URL, DEFAULT_MODEL, ModelClient  # noqa: E402

load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RECEIPTS_DIR = ROOT / "receipts"

SAMPLE_QUESTIONS = [
    "Which SKUs are at risk of stockout this week in the Midwest?",
    "Are any SKUs running low in the Northeast this week?",
    "Which SKUs are at risk of stockout this week across all our stores?",
    "Which suppliers in Latvia are most reliable?",
]

st.set_page_config(
    page_title="NVIDIA Receipts: Audit-Grade Retail Agent",
    layout="wide",
    page_icon=None,
)


def _parse_ref_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _sidebar() -> dict:
    st.sidebar.title("NVIDIA Receipts")
    st.sidebar.caption("Audit-grade retail agent on NIM")

    st.sidebar.markdown("**Identity**")
    user = st.sidebar.text_input(
        "User",
        value=os.environ.get("RECEIPT_USER", "me@andyrosic.com"),
        label_visibility="collapsed",
    )

    st.sidebar.markdown("**Model**")
    has_key = bool(os.environ.get("NVIDIA_API_KEY"))
    badge = "NIM live" if has_key else "STUB (no NIM key)"
    st.sidebar.code(f"{badge}\n{os.environ.get('NVIDIA_MODEL', DEFAULT_MODEL)}", language=None)

    st.sidebar.markdown("**Thresholds**")
    caveat = st.sidebar.slider(
        "Caveat threshold",
        0.0, 1.0,
        float(os.environ.get("CONFIDENCE_CAVEAT_THRESHOLD", "0.65")),
        0.05,
    )
    abstain = st.sidebar.slider(
        "Abstain threshold",
        0.0, 1.0,
        float(os.environ.get("CONFIDENCE_ABSTAIN_THRESHOLD", "0.40")),
        0.05,
    )

    st.sidebar.markdown("**Reference date**")
    ref = st.sidebar.text_input(
        "Reference date (YYYY-MM-DD)",
        value=os.environ.get("REFERENCE_DATE", "2026-04-23"),
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Sample questions**")
    chosen = None
    for q in SAMPLE_QUESTIONS:
        if st.sidebar.button(q, use_container_width=True):
            chosen = q

    return {
        "user": user,
        "caveat": caveat,
        "abstain": abstain,
        "reference_date": _parse_ref_date(ref),
        "chosen_sample": chosen,
    }


def _confidence_badge(value: float, caveat: float, abstain: float) -> str:
    if value >= caveat:
        return "PASS"
    if value >= abstain:
        return "CAVEAT"
    return "ABSTAIN"


def _render_receipt(receipt: dict, *, caveat: float, abstain: float) -> None:
    st.subheader("Receipt")
    st.caption(f"`{receipt['receipt_id']}` issued {receipt['timestamp']}")

    badge = _confidence_badge(receipt["confidence"], caveat, abstain)
    cols = st.columns(3)
    cols[0].metric("Confidence", f"{receipt['confidence']:.2f}", delta=badge, delta_color="off")
    cols[1].metric("Fallback path", receipt["fallback"]["path"])
    cols[2].metric("Latency", f"{receipt['duration_ms']} ms")

    comp = receipt.get("confidence_components") or {}
    if comp:
        st.markdown("**Confidence breakdown**")
        bcols = st.columns(3)
        bcols[0].metric("Data coverage", f"{comp['data_coverage']:.2f}")
        bcols[1].metric("Recency", f"{comp['recency']:.2f}")
        bcols[2].metric("Volume", f"{comp['volume']:.2f}")
        st.caption(
            f"Weights: coverage {comp['weights']['data_coverage']}, "
            f"recency {comp['weights']['recency']}, "
            f"volume {comp['weights']['volume']}. "
            f"Thresholds: caveat {receipt['confidence_threshold']['caveat']}, "
            f"abstain {receipt['confidence_threshold']['abstain']}."
        )

    st.markdown("**Sources queried**")
    for src in receipt["sources_queried"]:
        with st.expander(
            f"{src['source']} -- {src['rows_matched']} rows "
            f"(newest age: {src.get('newest_row_age_days', 'n/a')} days)"
        ):
            st.code(f"filter: {src['filter']}", language=None)
            if src["row_ids"]:
                st.code("\n".join(src["row_ids"]), language=None)
            else:
                st.caption("No rows matched.")

    st.markdown("**Prompt context sent to model**")
    pc = receipt["prompt_context"]
    st.caption(f"{pc['char_count']} chars. SHA-256 `{pc['sha256'][:16]}...`")
    with st.expander("Preview (first 800 chars)"):
        st.code(pc["preview"], language=None)

    st.markdown("**Model**")
    m = receipt["model"]
    st.code(f"{m['provider']}  |  {m['model_id']}\n{m['endpoint']}", language=None)

    st.markdown("**Identity**")
    st.code(receipt["user"], language=None)

    st.download_button(
        "Download receipt JSON",
        data=json.dumps(receipt, indent=2),
        file_name=f"{receipt['receipt_id']}.json",
        mime="application/json",
    )


def main() -> None:
    settings = _sidebar()

    st.title("Audit-Grade Retail Agent")
    st.caption(
        "Every answer ships with a structured receipt. The receipt is what a retail "
        "risk committee signs off on, not the model output."
    )

    default_q = settings["chosen_sample"] or st.session_state.get("question", SAMPLE_QUESTIONS[0])
    question = st.text_area("Operator question", value=default_q, height=80)
    st.session_state["question"] = question

    run = st.button("Run agent", type="primary")

    left, right = st.columns([5, 7])

    if run and question.strip():
        with st.spinner("Retrieving, prompting, emitting receipt..."):
            answer, receipt, path = run_agent(
                question,
                user=settings["user"],
                data_dir=DATA_DIR,
                receipts_dir=RECEIPTS_DIR,
                reference_date=settings["reference_date"],
                caveat_threshold=settings["caveat"],
                abstain_threshold=settings["abstain"],
            )

        with left:
            st.subheader("Answer")
            st.write(answer)
            st.caption(f"Receipt saved to `{path.relative_to(ROOT)}`")
        with right:
            _render_receipt(receipt, caveat=settings["caveat"], abstain=settings["abstain"])
    else:
        with left:
            st.info("Enter a question and click Run agent.")
        with right:
            st.info("The receipt will render here.")


if __name__ == "__main__":
    main()
