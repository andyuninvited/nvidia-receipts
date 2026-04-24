# NVIDIA Receipts

Audit-grade retail agent on NVIDIA NIM. Every answer ships with a structured compliance receipt so a retail risk committee can sign off.

- Live: https://nvidia-receipts.vercel.app/
- Repo: https://github.com/andyuninvited/nvidia-receipts (MIT)

Built as a portfolio prototype for the NVIDIA JR2015305 Director, Product Platform Retail and CPG application. Thesis: enterprise retail adoption of agentic AI stalls at the risk committee, not the model. Receipts are the platform primitive that unlocks production deployment.

## Stack

- Python 3.13 (CLI + Vercel Function), stdlib at runtime (csv, http.server, json, dataclasses)
- openai SDK against integrate.api.nvidia.com (NIM hosted, free tier)
- Default model: nvidia/llama-3.3-nemotron-super-49b-v1 (env-overridable)
- Streamlit for local dev UI; vanilla HTML + JS for production UI
- Deployment: Vercel (api/agent.py as Fluid Compute Python function + public/index.html static)

## Commands

```bash
# local CLI
.venv/bin/python -m src.cli "Which SKUs are at risk of stockout this week in the Midwest?"

# local Streamlit
.venv/bin/streamlit run ui/app.py

# install
pip install -r requirements.txt        # production (Vercel function deps)
pip install -r requirements-dev.txt    # adds Streamlit for local UI

# deploy
git push origin main                   # Vercel Git integration auto-deploys
```

## Structure

```
src/
  receipt.py        Deterministic confidence math + receipt dataclass
  retrieval.py      stdlib csv + region/intent filter (no pandas)
  nim_client.py     openai SDK against NIM, stub fallback when no key
  agent.py          Orchestration: parse, retrieve, score, call, finalize
  cli.py            CLI entrypoint
api/agent.py        Vercel Function (POST /api/agent)
public/index.html   Static UI for Vercel
ui/app.py           Streamlit UI for local dev
data/               3 mock CSVs with the Midwest stockout story baked in
receipt-schema.json JSON Schema 2020-12 for the receipt
vercel.json         Functions block + includeFiles for src/ and data/
```

## Architecture

Receipt is generated inline as the agent runs, not retroactively. Confidence is deterministic from four components: data_coverage (sources successfully queried), recency (max age of matched rows), volume (rows pulled), and query_specificity (parser signal extraction). Two thresholds gate behavior: caveat (0.65) and abstain (0.40). Below abstain the agent skips NIM entirely and routes to a queue ticket.

Three downstream consumers read the receipt: risk and compliance (reproducibility), operations (triage), finance (cost attribution). Schema in `receipt-schema.json`. Full thesis in `ARCHITECTURE.md`.

## Conventions

- Receipts always emitted, never optional. `model.provider` flips between `nvidia_nim` and `stub` based on whether `NVIDIA_API_KEY` is set.
- Stub responder produces templated answers from retrieved evidence so reviewers can clone and run without credentials.
- Reference date pinned via `REFERENCE_DATE` env var so recency math stays stable as the demo data ages.
- Sample questions are designed to exercise PASS, CAVEAT, and ABSTAIN bands with live NIM calls (3 of 4 hit NIM).
- No emojis in code or docs. Use complete sentences. Avoid emdashes.

## Key Context

- 1000 free NIM credits on Andy's personal account at build.nvidia.com. Key in `.env` (gitignored) and Vercel env vars.
- Vercel project Git-integrated; pushes to `main` auto-deploy. Static homepage from `public/`, Python function from `api/`.
- The Northeast clean-empty case is the headline demo: model honestly says "none found" because the data is empty, receipt records why confidence dropped to 0.5 (volume=0, recency=0, specificity stayed 1.0). That's the audit story for a NVIDIA reviewer.
- Coverage math fixed on 2026-04-24: empty results at high specificity now reach NIM with caveat instead of abstaining. See DEVLOG Mistakes & Lessons.
- See `PUBLISH.md` for the demo script and three LinkedIn caption drafts.

## Environment

`.env` requires:
- `NVIDIA_API_KEY` — `nvapi-...` from build.nvidia.com (free tier)

Optional:
- `NVIDIA_MODEL` — defaults to `nvidia/llama-3.3-nemotron-super-49b-v1`
- `REFERENCE_DATE` — `2026-04-23` (pin recency for stable demos)
- `RECEIPT_USER` — defaults to `me@andyrosic.com`
- `CONFIDENCE_CAVEAT_THRESHOLD` / `CONFIDENCE_ABSTAIN_THRESHOLD` — defaults 0.65 / 0.40
