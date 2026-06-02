# DEVLOG

## Working State

**Current Task**: Shipped and deployed the agentic-trust update (schema 1.2.0), a NIM timeout/fallback fix, and UI polish. Demo is live and tested. 14 eval cases + 1 fallback test passing (15 total under pytest; badge reads 14/14).

**Key Files**:
- `src/security.py` - NEW. scan_injection(question) returns SecurityCheck. 7 conservative regex patterns (override, role-reassign, new-directive, prompt-disclosure, system-role-spoof, guardrail-bypass, unconditional-directive). Detection sets fallback.path = blocked_injection; model is never called.
- `src/domain.py` - NEW. check_domain(parsed) returns Answerability. Out-of-domain if a foreign geography is named with no in-domain region, or if there's no in-domain anchor at all. Routes to abstain_out_of_domain with the true reason.
- `src/receipt.py` - Added SecurityCheckRecord + AnswerabilityRecord + setters; decide_fallback(blocked, out_of_domain) guards override the confidence math; schema 1.2.0.
- `src/agent.py` - Runs both guards before retrieval, stamps them on the receipt, branches to BLOCKED / out-of-domain ABSTAIN / low-conf ABSTAIN / model-call.
- `tests/` - NEW. eval_cases.py (9 golden cases + determinism check), run_eval.py (writes public/eval-summary.json, exits nonzero on fail), test_eval.py (pytest wrapper). `python -m tests.run_eval`.
- `public/index.html` - Header eval badge (fetches /eval-summary.json), "Attack the agent:" adversarial pills, red security-block + amber out-of-domain alerts in the Receipt panel.

**Active Decisions**:
- Guards run BEFORE retrieval and the model, and are recorded whether or not they fire, so an auditor sees the checks ran. A detected injection refuses rather than sanitizes: for an audit demo, a visible refusal is the honest behavior.
- Out-of-domain abstains for the TRUE reason (answerability), not via the old low-specificity side effect. The Latvia query previously abstained at confidence 0.3 for "low confidence"; it now abstains as abstain_out_of_domain with matched_ood_terms=['latvia'].
- Eval badge is generated at build/commit time into public/eval-summary.json (static, same-origin fetch). run_eval.py is standalone (no pytest needed) so the badge always regenerates; test_eval.py reuses the same cases under pytest.
- Injection patterns kept conservative to avoid false positives on legitimate operator questions (verified by the legit_query_not_flagged_as_injection case).

**Next Steps**:
1. Commit + push (await Andy's go) and confirm the Vercel deploy serves /eval-summary.json and renders the badge.
2. Re-record / extend the demo: add an "attack the agent" beat (injection blocked) and an out-of-domain beat.
3. Reference the eval badge + injection block in the SecurityScorecard application (cover-securityscorecard-2026-06-02.md).
4. Held for later: #3 cited-row-ID verification, #5-insights dashboard (Bonusly), hash-chained receipts.

**Blockers**: None.

**Gotchas**:
- Eval cases pin reference_date 2026-04-23 internally (eval_cases.py REFERENCE_DATE) so confidence is reproducible (Midwest=1.0/PASS, all-stores=0.65/PASS) regardless of the UI default. Changing the UI reference date does NOT affect the badge.
- The UI reference-date default is now 2026-06-01. Because data is dated ~2026-04-21/22, recency drops (~40-day age, recency ~0.62) and bands shift vs the old 2026-04-23 default: Midwest still PASS (0.886), Northeast still CAVEAT+review-flag (0.5), all-stores moved PASS->CAVEAT (0.576). Bump the data dates or the UI default together if a clean PASS-at-edge demo is wanted again.
- NIM latency on the all-stores query swings 21s to >45s. The 45s client timeout + max_retries=0 keeps the call inside the 60s Vercel budget; a slow call degrades to the deterministic stub (provider=stub, model_id "...nim-fallback") rather than a non-JSON timeout page.
- Injection guard runs on the raw question only (input-side). Output-side validation (e.g. cited-row-ID verification) is NOT yet implemented; that's held item #3.
- macOS ships Python 3.9 by default; use `/opt/homebrew/bin/python3.13` for the venv.
- Vercel `functions` block in vercel.json requires explicit `runtime: "@vercel/python@4.3.0"` or it errors with "doesn't match any Serverless Functions inside the api directory".
- With a `functions` block configured, Vercel switches into a configured-build mode that expects static assets under `public/`. Root-level index.html returns 404.
- Andy's personal NIM key is in `.env` (gitignored) and in Vercel env vars. NEVER paste keys into `.env.example`; that file is committed.
- The "Across all stores" sample lands at exactly confidence 0.65 (caveat threshold). Comparison is `<`, so it scrapes through as PASS. Float comparison drift could flip this in some Python versions.

## Session Archive

### 2026-06-02 - Agentic-trust update (schema 1.2.0): injection guard, domain check, eval harness
Shipped three on-thesis features to make the demo land harder for agentic-security / eval-framework roles. (1) Input prompt-injection guard (`src/security.py`): 7 conservative regex patterns; a hit sets fallback.path=blocked_injection and the model is never called. (2) Answerability / out-of-domain check (`src/domain.py`): foreign geography with no in-domain region, or no in-domain anchor at all, routes to abstain_out_of_domain with the true reason recorded (fixes the Latvia query, which previously abstained for "low confidence" via the specificity floor rather than for being out of domain). (3) Golden-case eval harness (`tests/`): 9 cases + a determinism check, run_eval.py writes public/eval-summary.json, UI header shows a live "eval: 10/10 passing" badge. Receipt schema bumped to 1.2.0 with security + answerability objects and two new fallback paths. UI gained "Attack the agent:" adversarial pills plus red injection-block and amber out-of-domain alerts. Both guards verified end-to-end via CLI (real NIM for in-domain, blocked/abstained for adversarial). All 10 eval cases green under both run_eval and pytest. Not yet committed/pushed - awaiting Andy's go.

### 2026-06-02 - NIM timeout fix + UI polish (post-deploy)
Fixed a production bug: the all-stores query returned a client-side "is not valid JSON" error because the real NIM call (latency 21s to >45s) blew past Vercel's 60s function budget, returning a non-JSON platform error page. Root cause was the OpenAI SDK's silent 2x retry stacking latency. Fix: pinned a 45s client timeout, set max_retries=0, and degrade to the deterministic stub on any NIM failure so the API always returns valid JSON in budget (added test_nim_fallback.py to lock it). UI also now parses the response defensively and shows a clean message on any non-JSON body. Then a round of UI polish per Andy: the adversarial pills now start on their own line under the sample pills with a flex break, the label reads "Try attacking the agent:", attack pills carry the same grey outline as normal pills and only turn red on hover (matching the green-on-hover pattern), and the UI reference-date default moved to 2026-06-01 (which shifts the all-stores sample from PASS to CAVEAT as recency decays).

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
