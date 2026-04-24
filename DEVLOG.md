# DEVLOG

## Working State

**Current Task**: Prototype shipped end-to-end. CLI + Streamlit run against stub. Awaiting Andy to (1) get a NIM key and verify live model path, (2) record the 3-minute demo, (3) push to public GitHub.

**Key Files**:
- `src/receipt.py` - Receipt dataclass, deterministic confidence math (coverage + recency + volume) gated by query_specificity multiplier
- `src/agent.py` - Orchestration: parse, retrieve, populate receipt, score, decide fallback, call NIM or skip
- `src/retrieval.py` - Region + intent filter over CSVs, returns row_ids and freshness for the receipt
- `src/nim_client.py` - OpenAI SDK against integrate.api.nvidia.com, deterministic stub when no key
- `ui/app.py` - Streamlit two-panel: answer left, receipt right, sample questions and threshold sliders in sidebar

**Active Decisions**:
- Confidence is deterministic, not LLM self-reported. Risk committee will not accept a model grading itself.
- Specificity multiplier punishes vague queries that pull full tables. Floor 0.3 so a wholly vague query caps at 30 percent of coverage_subscore, which lands below the abstain threshold by default.
- No-key stub responder generates a templated answer from retrieved evidence so the demo runs without credentials. Receipt records `provider="stub"`.
- Reference date pinned to 2026-04-23 in `.env.example` so recency math stays stable as the demo data ages.

**Next Steps**:
1. Get NIM key from build.nvidia.com, paste into `.env`, run a live query, verify receipt records `provider="nvidia_nim"`.
2. Push to public GitHub repo with MIT license. Confirm README renders cleanly.
3. Record demo video per `demo-script.md` (3 minutes, problem -> walkthrough -> generalize).
4. Publish LinkedIn caption Monday morning.

**Blockers**: None. Awaiting Andy's NIM key and demo recording window.

**Gotchas**:
- macOS ships Python 3.9 by default; use `/opt/homebrew/bin/python3.13` for the venv.
- Streamlit headless boots OK on port 8765 but the watchdog warning is cosmetic.
- The "Charcoal briquettes nationwide" sample question abstains because the parser does not extract SKU. That is intentional for v1; SKU parsing is a one-line add but would obscure the demo of the abstain behavior.

## Session Archive

### 2026-04-23 - Day 1 build (Claude Code session)
Scaffolded full project end-to-end: receipt schema (JSON Schema 2020-12), 3 mock CSVs with a Midwest stockout story baked in (SKUs 1042 patio cushions, 2087 charcoal, 3155 mosquito repellent at stores M-217/218/219), receipt module with deterministic confidence (coverage + recency + volume + specificity multiplier), retrieval layer (region + stockout intent filter), NIM client with stub fallback, agent orchestration, CLI, Streamlit UI. Smoke tested all three confidence states (PASS at 1.0, ABSTAIN at 0.3 for vague Latvia query). Wrote README and ARCHITECTURE. Total session ~3 hours. Caught one real product issue mid-build: vague queries were producing full-table pulls at confidence 1.0, fixed by adding query_specificity term to the confidence calculation.

## Milestones

- 2026-04-23 - End-to-end prototype runs CLI + Streamlit, three confidence states demonstrable, docs written.

## Mistakes & Lessons

- 2026-04-23 - Initial confidence calculation only weighted data coverage / recency / volume, which let vague queries produce 1.0 confidence over irrelevant data. Lesson: confidence must include a "did the parser understand the question" term, not just "did we find rows." Fix: query_specificity multiplier with a 0.3 floor.

## Technical Debt

- Retrieval is keyword + region only. SKU and product-name extraction would let the "charcoal briquettes nationwide" sample land in the caveat band rather than abstain.
- No formal JSON Schema validation step in CI. Add `jsonschema` validation against `receipt-schema.json` in a pre-commit hook before merging to main.
- Stub responder duplicates some logic that the real model would otherwise produce. Extract a shared "evidence formatter" if the demo grows beyond a one-shot prototype.
- The Streamlit caveat path is reachable only by sliding the threshold up; engineering one sample question that lands between abstain and caveat with default thresholds would make the demo cleaner.
