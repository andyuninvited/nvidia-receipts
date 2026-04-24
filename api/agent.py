"""
Vercel Function entrypoint. POST /api/agent.

Wraps src.agent.run_agent. Body schema:
    {
      "question": "<operator question>",
      "user": "<optional override>",
      "reference_date": "<YYYY-MM-DD optional>",
      "caveat": <optional float>,
      "abstain": <optional float>
    }

Response:
    { "answer": "<text>", "receipt": { ...full receipt JSON... } }

Receipts are written to /tmp on the function instance (not persisted across
invocations). The receipt is also returned in the response so the client can
download it locally.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agent import run_agent  # noqa: E402

DATA_DIR = ROOT / "data"
RECEIPTS_DIR = Path("/tmp/receipts")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid JSON body"})
            return

        question = (body.get("question") or "").strip()
        if not question:
            self._respond(400, {"error": "question is required"})
            return

        user = body.get("user") or os.environ.get("RECEIPT_USER", "me@andyrosic.com")
        ref_str = body.get("reference_date") or os.environ.get("REFERENCE_DATE")
        try:
            ref_date = date.fromisoformat(ref_str) if ref_str else None
        except ValueError:
            self._respond(400, {"error": f"reference_date must be YYYY-MM-DD, got {ref_str!r}"})
            return

        try:
            caveat = float(body.get("caveat") or os.environ.get("CONFIDENCE_CAVEAT_THRESHOLD", "0.65"))
            abstain = float(body.get("abstain") or os.environ.get("CONFIDENCE_ABSTAIN_THRESHOLD", "0.40"))
        except ValueError:
            self._respond(400, {"error": "caveat and abstain must be floats"})
            return

        try:
            answer, receipt, _ = run_agent(
                question,
                user=user,
                data_dir=DATA_DIR,
                receipts_dir=RECEIPTS_DIR,
                reference_date=ref_date,
                caveat_threshold=caveat,
                abstain_threshold=abstain,
            )
        except Exception as exc:
            self._respond(500, {"error": f"{type(exc).__name__}: {exc}"})
            return

        self._respond(200, {"answer": answer, "receipt": receipt})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        self._respond(200, {"status": "ok", "post": "/api/agent"})

    def _respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
