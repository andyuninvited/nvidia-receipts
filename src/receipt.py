"""
Receipt module. One Receipt is emitted per agent response.

The receipt is the audit-grade record that a retail risk committee signs off
on. It records exactly what data was pulled, what context the model received,
how confidence was computed, and which fallback path triggered.

Confidence is deterministic and reproducible from the receipt alone. It is
NOT model self-reported. A risk committee cannot accept a system that lets
the model grade its own work.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = "1.1.0"
PREVIEW_CHARS = 800
ANSWER_PREVIEW_CHARS = 400
RECENCY_FULL_CREDIT_DAYS = 14
RECENCY_ZERO_CREDIT_DAYS = 90
VOLUME_TARGET_ROWS = 10
CONFIDENCE_WEIGHTS = {"data_coverage": 0.5, "recency": 0.3, "volume": 0.2}
SPECIFICITY_FLOOR = 0.3
REVIEW_MARGIN_DEFAULT = 0.15


@dataclass
class SourceQueried:
    source: str
    filter: str
    rows_matched: int
    row_ids: list[str]
    newest_row_age_days: Optional[float] = None


@dataclass
class PromptContext:
    char_count: int
    preview: str
    sha256: str


@dataclass
class ModelInfo:
    provider: str
    model_id: str
    endpoint: str = ""


@dataclass
class ConfidenceComponents:
    data_coverage: float
    recency: float
    volume: float
    query_specificity: float
    coverage_subscore: float
    specificity_multiplier: float
    weights: dict


@dataclass
class FallbackDecision:
    triggered: bool
    path: str
    reason: str = ""


@dataclass
class ReviewFlag:
    # The grey-zone signal. The fallback rule already permitted an answer with
    # caveat, but the confidence sat close enough to the abstain line that a
    # compliance reviewer should look at the rule itself, not just the answer.
    # Distance is signed: positive means above abstain (the only case we flag).
    triggered: bool
    margin: float
    distance_to_abstain: float
    reason: str = ""


@dataclass
class Receipt:
    receipt_id: str
    schema_version: str
    timestamp: str
    user: str
    query: str
    model: ModelInfo
    sources_queried: list[SourceQueried] = field(default_factory=list)
    prompt_context: Optional[PromptContext] = None
    confidence: float = 0.0
    confidence_threshold: dict = field(default_factory=dict)
    confidence_components: Optional[ConfidenceComponents] = None
    fallback: Optional[FallbackDecision] = None
    review_flag: Optional[ReviewFlag] = None
    duration_ms: int = 0
    answer_summary: str = ""

    _start_ns: int = field(default=0, repr=False)
    _expected_sources: int = field(default=3, repr=False)

    @classmethod
    def start(
        cls,
        *,
        query: str,
        user: str,
        model_provider: str,
        model_id: str,
        endpoint: str = "",
        expected_sources: int = 3,
    ) -> "Receipt":
        return cls(
            receipt_id=str(uuid.uuid4()),
            schema_version=SCHEMA_VERSION,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            user=user,
            query=query,
            model=ModelInfo(provider=model_provider, model_id=model_id, endpoint=endpoint),
            _start_ns=time.monotonic_ns(),
            _expected_sources=expected_sources,
        )

    def add_source(
        self,
        *,
        source: str,
        filter_desc: str,
        row_ids: list[str],
        newest_row_age_days: Optional[float],
    ) -> None:
        self.sources_queried.append(
            SourceQueried(
                source=source,
                filter=filter_desc,
                rows_matched=len(row_ids),
                row_ids=row_ids,
                newest_row_age_days=newest_row_age_days,
            )
        )

    def set_prompt_context(self, full_text: str) -> None:
        self.prompt_context = PromptContext(
            char_count=len(full_text),
            preview=full_text[:PREVIEW_CHARS],
            sha256=hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        )

    def compute_confidence(
        self,
        *,
        caveat: float,
        abstain: float,
        query_specificity: float,
    ) -> float:
        coverage = self._coverage_score()
        recency = self._recency_score()
        volume = self._volume_score()
        specificity = max(0.0, min(1.0, query_specificity))

        coverage_subscore = (
            CONFIDENCE_WEIGHTS["data_coverage"] * coverage
            + CONFIDENCE_WEIGHTS["recency"] * recency
            + CONFIDENCE_WEIGHTS["volume"] * volume
        )
        spec_multiplier = SPECIFICITY_FLOOR + (1.0 - SPECIFICITY_FLOOR) * specificity
        score = coverage_subscore * spec_multiplier

        self.confidence = round(score, 3)
        self.confidence_threshold = {"caveat": caveat, "abstain": abstain}
        self.confidence_components = ConfidenceComponents(
            data_coverage=round(coverage, 3),
            recency=round(recency, 3),
            volume=round(volume, 3),
            query_specificity=round(specificity, 3),
            coverage_subscore=round(coverage_subscore, 3),
            specificity_multiplier=round(spec_multiplier, 3),
            weights=CONFIDENCE_WEIGHTS,
        )
        return self.confidence

    def decide_fallback(self) -> FallbackDecision:
        thresholds = self.confidence_threshold
        if self.confidence < thresholds["abstain"]:
            decision = FallbackDecision(
                triggered=True,
                path="abstain_route_to_human",
                reason=f"confidence {self.confidence} below abstain threshold {thresholds['abstain']}",
            )
        elif self.confidence < thresholds["caveat"]:
            decision = FallbackDecision(
                triggered=True,
                path="answer_with_caveat",
                reason=f"confidence {self.confidence} below caveat threshold {thresholds['caveat']}",
            )
        else:
            decision = FallbackDecision(triggered=False, path="none", reason="")
        self.fallback = decision
        return decision

    def evaluate_review_flag(self, *, margin: float) -> ReviewFlag:
        # Only flag the caveat band. PASS is high-confidence, ABSTAIN already
        # routed to a human, so neither warrants the same compliance signal.
        abstain = self.confidence_threshold["abstain"]
        distance = round(self.confidence - abstain, 3)
        is_caveat = self.fallback is not None and self.fallback.path == "answer_with_caveat"
        if is_caveat and distance < margin:
            flag = ReviewFlag(
                triggered=True,
                margin=margin,
                distance_to_abstain=distance,
                reason=(
                    f"confidence {self.confidence} is only {distance} above abstain {abstain}; "
                    f"within review margin {margin}. Compliance should review and refine the rule."
                ),
            )
        else:
            flag = ReviewFlag(
                triggered=False,
                margin=margin,
                distance_to_abstain=distance,
                reason="",
            )
        self.review_flag = flag
        return flag

    def set_answer_summary(self, answer: str) -> None:
        self.answer_summary = answer[:ANSWER_PREVIEW_CHARS]

    def finalize(self) -> dict:
        self.duration_ms = (time.monotonic_ns() - self._start_ns) // 1_000_000
        return self.to_dict()

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_start_ns", None)
        d.pop("_expected_sources", None)
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    def write(self, directory: Path | str) -> Path:
        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.receipt_id}.json"
        path.write_text(self.to_json())
        return path

    def _coverage_score(self) -> float:
        # Coverage measures whether the retrieval system reached every expected
        # data source, not whether each source returned rows. A clean empty
        # result (e.g., "no SKUs at risk in this region") is a valid answer
        # and should not be penalized here. Volume captures the row-count
        # signal separately. In production this score would only drop when a
        # source query times out or the system is unreachable.
        if self._expected_sources == 0:
            return 0.0
        return min(len(self.sources_queried) / self._expected_sources, 1.0)

    def _recency_score(self) -> float:
        ages = [s.newest_row_age_days for s in self.sources_queried if s.newest_row_age_days is not None]
        if not ages:
            return 0.0
        max_age = max(ages)
        if max_age <= RECENCY_FULL_CREDIT_DAYS:
            return 1.0
        if max_age >= RECENCY_ZERO_CREDIT_DAYS:
            return 0.0
        span = RECENCY_ZERO_CREDIT_DAYS - RECENCY_FULL_CREDIT_DAYS
        return 1.0 - (max_age - RECENCY_FULL_CREDIT_DAYS) / span

    def _volume_score(self) -> float:
        total = sum(s.rows_matched for s in self.sources_queried)
        return min(total / VOLUME_TARGET_ROWS, 1.0)
