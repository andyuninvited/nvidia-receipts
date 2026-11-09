# DEVLOG

## Working State

**Current Task**: Homepage and demo redesign (issue #5, branch feat/homepage-redesign). PR open, not merged, not deployed to production. Goal: a security-minded reviewer understands what it does, why it matters, and how to try it in about two minutes.

**Key Files**:
- `public/index.html` - Rebuilt single page: sticky nav with eval badge and demo CTA, hero with an animated receipt plate (values from receipts/ac9dddc9...json), request-path toggles (clean, thin evidence, outside the data, injection), confidence explainer sliders using the ARCHITECTURE.md formula, guided demo scenarios, receipt panel with in-browser verify, raw JSON toggle, limits section, footer disclaimer.
- `api/agent.py`, `src/`, `receipt-schema.json`, `vercel.json` - Untouched.

**Active Decisions**:
- Structure and interaction patterns ported from the Rosicodex site redesign (PRs 9 and 14); palette kept exactly (same nine CSS variables and alert colors), system fonts kept, no Rosicodex copy or tokens.
- No hash-chain tamper demo: receipts here are not hash-chained (ARCHITECTURE lists that as a production addition), so showing one would overclaim. The real verify step is a confidence recompute from the receipt's components, plus a WebCrypto SHA-256 check of the prompt when the full prompt fits in the preview (guard paths hash the empty string, which proves nothing was sent).
- Scenario cards auto-run on click. Thresholds, identity, and reference date moved under an advanced toggle; all still sent to the API.
- Guard-path receipts (confidence_components null) now say no scoring ran instead of printing zeros.
- Footer adds "Independent portfolio prototype by Andy Rosic. Not affiliated with or endorsed by NVIDIA."

**Next Steps**:
1. Andy reviews the Vercel preview, merges the PR, then confirm production renders and a live NIM run still works.

**Blockers**: None.

**Gotchas**:
- Verify recompute uses rounded components, so Midwest shows 0.885 vs 0.886; the UI notes components are stored to three decimals.
- Local check used a scratch dev server (static public/ plus api.agent handler) with NVIDIA_API_KEY unset, so answers came from the stub. No NIM credits spent.
- Earlier gotchas still hold: UI reference date 2026-06-01 puts Midwest at 0.886 PASS and Northeast at 0.50 CAVEAT with review flag; injection guard is input-side only.

## Session Archive

### 2026-11-09 - Homepage and demo redesign (issue #5)
Rebuilt public/index.html for a two-minute walkthrough aimed at security-minded reviewers, porting structure and interaction quality from the Rosicodex redesign while keeping this site's palette. Added hero with animated receipt plate, request-path toggles, confidence explainer, guided scenarios, in-browser verify, raw JSON toggle, limits section, OG and Twitter meta, and prefers-reduced-motion handling. pytest 15 passed. Playwright with system Chrome at 1440px and 390px: all scenarios and pills render receipts, verify matches, no horizontal scroll, reduced motion disables the animation.


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
