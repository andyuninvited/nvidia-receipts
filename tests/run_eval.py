"""
Eval runner. Runs the golden cases and writes public/eval-summary.json, which
the UI reads to render the "Eval: N/N passing" badge.

    python -m tests.run_eval

Exits nonzero if any case fails, so it can gate a deploy.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from tests.eval_cases import CASES, confidence_is_deterministic, run_case

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "public" / "eval-summary.json"


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for case in CASES:
            try:
                passed, detail, _ = run_case(case, tmp)
            except Exception as exc:  # a thrown case is a failed case
                passed, detail = False, f"{type(exc).__name__}: {exc}"
            results.append({"name": case.name, "status": "pass" if passed else "fail", "detail": detail})

        det_passed, det_detail = confidence_is_deterministic(tmp)
        results.append({
            "name": "confidence_is_deterministic",
            "status": "pass" if det_passed else "fail",
            "detail": det_detail,
        })

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "all_pass": passed == total,
        "cases": results,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n")

    for r in results:
        mark = "PASS" if r["status"] == "pass" else "FAIL"
        print(f"  [{mark}] {r['name']}  {r['detail']}")
    print(f"\nEval: {passed}/{total} passing  ->  {SUMMARY_PATH.relative_to(ROOT)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
