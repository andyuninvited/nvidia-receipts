"""
NIM client. Wraps the OpenAI SDK pointed at integrate.api.nvidia.com.

If NVIDIA_API_KEY is unset, falls back to a deterministic stub responder
that produces a templated answer from the retrieved evidence. The stub
exists so a reviewer can clone, run, and see the receipt flow without
needing a NIM key. The receipt explicitly records provider='stub' so
audit logs never confuse stub output with real model output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
# Kept comfortably under the Vercel function maxDuration (60s) so the call
# always returns or raises in time for the handler to emit valid JSON. The
# function timing out itself produces a non-JSON platform error page.
NIM_TIMEOUT_SECONDS = 45.0


@dataclass
class ModelResult:
    text: str
    provider: str
    model_id: str
    endpoint: str


class ModelClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("NVIDIA_API_KEY", "")
        self.base_url = base_url or os.environ.get("NVIDIA_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or os.environ.get("NVIDIA_MODEL", DEFAULT_MODEL)
        self.provider = "nvidia_nim" if self.api_key else "stub"

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        evidence: Optional[dict] = None,
    ) -> ModelResult:
        if self.provider == "stub":
            return self._stub_response(evidence or {})
        try:
            return self._nim_call(system_prompt, user_prompt)
        except Exception as exc:
            # NIM was unreachable, errored, or ran past the timeout budget.
            # Degrade to the deterministic stub so the response is always valid
            # and within the function's time budget, and record honestly that
            # the real model did not answer.
            fallback = self._stub_response(evidence or {})
            return ModelResult(
                text=(
                    f"[NIM fallback: the model call failed or timed out ({type(exc).__name__}). "
                    "A deterministic answer computed from the retrieved rows follows.]\n\n"
                    + fallback.text
                ),
                provider="stub",
                model_id="deterministic-stub-v1 (nim-fallback)",
                endpoint="local",
            )

    def _nim_call(self, system_prompt: str, user_prompt: str) -> ModelResult:
        from openai import OpenAI

        # max_retries=0 is the important one: the SDK otherwise retries up to
        # twice with backoff, which can silently stack past the function budget
        # and turn one slow call into a platform timeout.
        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=NIM_TIMEOUT_SECONDS,
            max_retries=0,
        )
        completion = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        text = completion.choices[0].message.content or ""
        return ModelResult(
            text=text.strip(),
            provider="nvidia_nim",
            model_id=self.model,
            endpoint=self.base_url,
        )

    def _stub_response(self, evidence: dict) -> ModelResult:
        inv = evidence.get("inventory")
        sup = evidence.get("supply_signals")

        if inv is None or not inv.rows:
            text = (
                "STUB RESPONSE (no NIM key configured). "
                "No inventory rows matched the query filters. "
                "Set NVIDIA_API_KEY in .env to call a real model."
            )
            return ModelResult(text=text, provider="stub", model_id="deterministic-stub-v1", endpoint="local")

        lines = ["STUB RESPONSE (no NIM key configured). At-risk SKU/store combinations identified from the retrieved inventory:\n"]
        ranked = sorted(
            inv.rows,
            key=lambda r: int(r["reorder_point"]) - int(r["on_hand_units"]),
            reverse=True,
        )
        for r in ranked:
            gap = int(r["reorder_point"]) - int(r["on_hand_units"])
            lines.append(
                f"- {r['sku']} ({r['product_name']}) at {r['store_id']} {r['store_city']}: "
                f"on hand {int(r['on_hand_units'])} units, reorder point {int(r['reorder_point'])} "
                f"(short by {gap})."
            )
        if sup is not None and sup.rows:
            critical = [r for r in sup.rows if r.get("supplier_status") in ("delayed", "backorder")]
            if critical:
                lines.append("\nSupplier signals to be aware of:")
                for r in critical:
                    lines.append(
                        f"- {r['sku']} via {r['supplier_name']} ({r['supplier_status']}): "
                        f"ETA moved from {int(r['prior_eta_days'])} to {int(r['current_eta_days'])} days. "
                        f"{r['signal_note']}"
                    )
        lines.append("\nSet NVIDIA_API_KEY in .env to call a real NIM model and replace this templated answer.")
        return ModelResult(
            text="\n".join(lines),
            provider="stub",
            model_id="deterministic-stub-v1",
            endpoint="local",
        )
