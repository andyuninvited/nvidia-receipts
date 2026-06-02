"""
A slow or failing NIM call must never crash the request. It degrades to the
deterministic stub so the API always returns valid JSON within the function
budget. This locks that behavior.
"""

from __future__ import annotations

from src.nim_client import ModelClient


def test_nim_failure_degrades_to_stub():
    client = ModelClient(api_key="fake-key")  # provider resolves to nvidia_nim
    assert client.provider == "nvidia_nim"

    def _boom(system_prompt, user_prompt):
        raise TimeoutError("simulated NIM timeout")

    client._nim_call = _boom  # force the failure path

    result = client.chat(system_prompt="s", user_prompt="u", evidence={})

    assert result.provider == "stub"
    assert "nim-fallback" in result.model_id
    assert result.text.startswith("[NIM fallback")
