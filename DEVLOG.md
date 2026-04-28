# DEVLOG

## Working State

**Current Task**: Shipped grey-zone review flag (schema 1.1.0). When a caveat-band answer lands within `review_margin` (default 0.15) of the abstain threshold, the receipt raises a compliance alert. Northeast clean-empty case (confidence 0.5, distance 0.10) is the headline demo for this signal.

**Key Files**:
- `src/receipt.py` - Receipt + ReviewFlag dataclass; evaluate_review_flag(margin) raises grey-zone alert when caveat answer is within margin of abstain. Schema bumped to 1.1.0.
- `src/agent.py` - run_agent now takes review_margin (default REVIEW_MARGIN_DEFAULT=0.15); calls evaluate_review_flag after decide_fallback.
- `api/agent.py` - Accepts review_margin in body, falls back to REVIEW_MARGIN_THRESHOLD env then 0.15.
- `public/index.html` - New review-margin slider; red alert box renders at top of Receipt panel when review_flag.triggered.
- `receipt-schema.json` - schema_version 1.1.0; review_flag object with triggered/margin/distance_to_abstain/reason.

**Active Decisions**:
- Grey zone is bounded by fallback path, not raw confidence. Only `answer_with_caveat` results can flag. PASS doesn't need review; ABSTAIN already routed to a human.
- Default margin = 0.15 chosen so the existing CAVEAT demo (Northeast, confidence 0.5, abstain 0.40) flags out-of-the-box. With 0.10 margin it would not trigger; 0.20+ would over-fire.
- Comparison is strict `<`. distance == margin does not flag. This keeps the upper edge of the grey zone clearly outside.

**Next Steps**:
1. Smoke test the four sample questions: Midwest (PASS, no flag), Northeast (CAVEAT, flag triggers), Across all stores (PASS at edge, no flag), Latvia (ABSTAIN, no flag).
2. Record 3-minute demo per `PUBLISH.md` script. Add a fifth beat showing the grey-zone alert on the Northeast case.
3. Update PUBLISH.md captions to mention the compliance review flag.
4. Optional: send a direct message to NVIDIA recruiter or hiring manager pointing at the post.

**Blockers**: None.

**Gotchas**:
- macOS ships Python 3.9 by default; use `/opt/homebrew/bin/python3.13` for the venv.
- Vercel `functions` block in vercel.json requires explicit `runtime: "@vercel/python@4.3.0"` or it errors with "doesn't match any Serverless Functions inside the api directory".
- With a `functions` block configured, Vercel switches into a configured-build mode that expects static assets under `public/`. Root-level index.html returns 404.
- Andy's personal NIM key is in `.env` (gitignored) and in Vercel env vars. NEVER paste keys into `.env.example`; that file is committed.
- The "Across all stores" sample lands at exactly confidence 0.65 (caveat threshold). Comparison is `<`, so it scrapes through as PASS. Float comparison drift could flip this in some Python versions.

## Session Archive

### 2026-04-23 - Day 1 build (Claude Code session)
Scaffolded full project end-to-end: receipt schema (JSON Schema 2020-12), 3 mock CSVs with a Midwest stockout story baked in (SKUs 1042 patio cushions, 2087 charcoal, 3155 mosquito repellent at stores M-217/218/219), receipt module with deterministic confidence (coverage + recency + volume + specificity multiplier), retrieval layer (region + stockout intent filter), NIM client with stub fallback, agent orchestration, CLI, Streamlit UI. Smoke tested all three confidence states (PASS at 1.0, ABSTAIN at 0.3 for vague Latvia query). Wrote README and ARCHITECTURE. Total session ~3 hours. Caught one real product issue mid-build: vague queries were producing full-table pulls at confidence 1.0, fixed by adding query_specificity term to the confidence calculation.

### 2026-04-28 - Grey-zone review flag (schema 1.1.0)
Added the compliance review signal Andy wanted: when a caveat answer lands within review_margin of the abstain line, the receipt raises a red alert. New ReviewFlag dataclass, evaluate_review_flag method, run_agent param, /api/agent body field, env var (REVIEW_MARGIN_THRESHOLD, default 0.15), UI slider, and a red-bordered alert block at the top of the Receipt panel. Schema bumped to 1.1.0; receipt-schema.json now defines review_flag. Bounded the trigger to fallback path == answer_with_caveat so PASS and ABSTAIN never raise a false alarm. Default margin 0.15 was chosen so the existing Northeast CAVEAT demo (confidence 0.5, abstain 0.40, distance 0.10) flags the alert without slider adjustment, which makes the grey-zone story demoable in one click.

### 2026-04-24 - Day 2 ship: Vercel deployment + receipts fix
Pivoted UI from Streamlit to a Vercel-native deployment so the demo lives at a shareable URL on Andy's stack. Stripped pandas (saved ~50MB cold start), rewrote retrieval and stub responder against stdlib csv and list[dict]. Built `api/agent.py` Vercel Function (BaseHTTPRequestHandler, CORS, /tmp receipts) and a single static `public/index.html` (vanilla JS, two-panel, confidence breakdown, source row IDs as chips, expandable prompt preview, download receipt JSON). Pushed to https://github.com/andyuninvited/nvidia-receipts. First Vercel deploy errored: needed explicit `@vercel/python@4.3.0` runtime in vercel.json functions block and required `index.html` under `public/` not at the repo root. Fixed both. Got NIM key, verified live model call: Nemotron returned grounded answer with row-ID citations exactly as system prompt instructs and added an unprompted "Explicit Non-Answer for Clarity" section. Caught a second real product issue post-deploy: three of four sample questions hit ABSTAIN because (a) retrieval short-circuited sales/supply when inventory was empty and (b) data_coverage measured "sources with rows matched" not "sources successfully queried". Fixed both: removed the short-circuit, redefined coverage, replaced sample questions to demo all three bands with live NIM. Now 3 of 4 samples call NIM with visibly different receipts. Andy edited the homepage subtitle directly in GitHub mid-session; rebased cleanly. Total session ~2.5 hours.

## Milestones

- 2026-04-23 - End-to-end prototype runs CLI + Streamlit, three confidence states demonstrable, docs written.
- 2026-04-24 - Live on Vercel at https://nvidia-receipts.vercel.app/. Repo public on GitHub. NIM key live. Three of four sample questions call real NIM with audit-grade receipts visible in the UI.

## Mistakes & Lessons

- 2026-04-23 - Initial confidence calculation only weighted data coverage / recency / volume, which let vague queries produce 1.0 confidence over irrelevant data. Lesson: confidence must include a "did the parser understand the question" term, not just "did we find rows." Fix: query_specificity multiplier with a 0.3 floor.

- 2026-04-24 - Three of four sample questions hit ABSTAIN after deploy because the retrieval layer treated "empty inventory" as a system failure rather than a clean negative answer. Two coupled bugs: (1) `retrieve()` short-circuited when inventory was empty, marking sales and supply as "not pulled" rather than queried-with-zero-rows; (2) `data_coverage` was computed as `sources_with_rows_matched / expected_sources`, so a clean empty result gave coverage 0 and confidence 0.0 to 0.3, indistinguishable from a system being unreachable. Lesson: in receipts-style agents, "we found nothing" is a valid answer at high confidence when the system functioned as designed. Coverage measures whether the retrieval reached every expected source; volume captures the row-count signal separately. The two must not be conflated. Fix: removed the short-circuit so all three sources are always queried (empty inventory naturally yields zero downstream rows), redefined data_coverage as `len(sources_queried) / expected_sources`, replaced sample questions to demo PASS / CAVEAT / PASS-at-edge / ABSTAIN with live NIM. The Northeast empty-result CAVEAT is now the headline demo because the receipt explains exactly why confidence dropped despite the system working correctly.

- 2026-04-24 - First Vercel deploy errored "doesn't match any Serverless Functions inside the api directory" even with `api/agent.py` present. Cause: when vercel.json declares a `functions` block, Vercel requires an explicit `runtime` value because the auto-detect is bypassed. Lesson: any time you specify per-function config in vercel.json, also specify the runtime. Fix: added `"runtime": "@vercel/python@4.3.0"`.

- 2026-04-24 - After fixing the runtime, the function worked but root `/` returned 404. Cause: with a `functions` block configured, Vercel switches into a configured-build mode that expects static assets under `public/`, not at the repo root. Lesson: in a Vercel-managed project with explicit function config, treat `public/` as the default static output directory. Fix: moved `index.html` from root to `public/index.html`.

## Technical Debt

- Retrieval is keyword + region only. SKU and product-name extraction would let questions like "What is our exposure on charcoal briquettes?" land in caveat or pass rather than abstain.
- No formal JSON Schema validation step in CI. Add `jsonschema` validation against `receipt-schema.json` in a pre-commit hook before merging to main.
- Stub responder duplicates some logic the real model would otherwise produce. Extract a shared "evidence formatter" if the demo grows beyond a one-shot prototype.
- Vercel function regions are unset (defaults to iad1). For a real customer demo, pin to `sfo1` for lowest latency from NVIDIA HQ.
- The "Across all stores" sample lands at exactly confidence 0.65 (the caveat threshold). Comparison is `<`, so it scrapes through as PASS. Engineering one sample to land cleanly inside the CAVEAT band with default thresholds (e.g., a query that drops volume by half) would make the demo cleaner.
- Receipts are written to `/tmp/receipts` on Vercel, which is per-instance and not persisted. For audit log persistence, the function should write receipts to Vercel Blob, S3, or a row in Neon/Supabase. The receipt JSON in the response body is enough for the demo but not for production.
- Receipt download in the UI exports the JSON returned in the response. There is no server-side audit log endpoint to list historical receipts. Add `/api/receipts/list` for production.
