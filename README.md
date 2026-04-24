# NVIDIA Receipts

A weekend prototype of an audit-grade retail agent on the NVIDIA NIM stack. Every answer the agent emits ships with a structured receipt that a retail risk committee can sign off on.

**Live demo:** https://nvidia-receipts.vercel.app/
**Repo:** https://github.com/andyuninvited/nvidia-receipts (MIT)

## Why this exists

Enterprise retail adoption of agentic AI stalls at the risk committee, not the model. The three blockers are predictable.

1. **Audit-grade receipts.** Risk teams will not approve an answer they cannot reconstruct. They need to see what data was pulled, what context the model received, what confidence applied, and which fallback path triggered.
2. **Legacy coexistence.** Retailers run AS/400, SAP ECC, and ColdFusion monoliths that are not getting replaced. Any agent that demands a green-field stack ships into a graveyard.
3. **Outsized ROI math.** Net margins in retail run 2 to 6 percent. AI spend has to return 3 to 5x in documented value within 18 months or the program dies.

This prototype is the receipts piece. The same pattern generalizes across every NVIDIA Retail Blueprint.

## What it does

- Accepts a retail-operator question.
- Retrieves matching rows from three mock CSV sources (inventory, sales, supply signals).
- Builds a context block, computes a deterministic confidence score, and decides whether to call the model, caveat the answer, or abstain and route to human review.
- Calls a NIM-hosted Nemotron model through the OpenAI-compatible NIM endpoint. Falls back to a deterministic stub when no API key is set so the demo still runs.
- Emits a receipt JSON for every response, written to `receipts/`.
- Renders both panels in a Streamlit UI.

## Quickstart (local)

```bash
git clone https://github.com/andyuninvited/nvidia-receipts
cd nvidia-receipts

python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # includes Streamlit for local UI

cp .env.example .env
# Optional: paste a free NIM key from https://build.nvidia.com into NVIDIA_API_KEY.
# Without a key, the agent runs against a deterministic stub responder and the
# receipt records provider="stub" so audit logs never confuse the two.

# CLI
python -m src.cli "Which SKUs are at risk of stockout this week in the Midwest?"

# Streamlit UI
streamlit run ui/app.py
```

## Deploy to Vercel

The repo is Vercel-native. The static `index.html` is served as the homepage and `api/agent.py` is a Vercel Function (Fluid Compute, Python 3.12+).

```bash
npm i -g vercel
vercel link
vercel env add NVIDIA_API_KEY              # paste your NIM key, all environments
vercel env add NVIDIA_MODEL                # e.g. nvidia/llama-3.3-nemotron-super-49b-v1
vercel env add REFERENCE_DATE              # 2026-04-23 (optional, stabilizes recency)
vercel deploy --prod
```

The shareable URL surfaces the same two-panel UI as the local Streamlit version.

## Example

```
$ python -m src.cli "Which SKUs are at risk of stockout this week in the Midwest?"
```

Returns an answer that names the at-risk SKU/store combinations, plus a receipt that records:

- `confidence: 1.0` with breakdown of `data_coverage`, `recency`, `volume`, and `query_specificity`.
- `sources_queried` listing all three CSVs with the exact filter applied and the row IDs pulled.
- `prompt_context` with character count, first 800 characters, and SHA-256 of the full prompt.
- `model` block recording whether the response came from NIM or the stub.
- `fallback` block showing whether a caveat or abstain path triggered.
- `duration_ms`, `timestamp`, `user`, and `receipt_id`.

## Sample questions and what they demonstrate

The four sample question pills in the UI are designed to demonstrate every band of agent behavior with live NIM calls.

| Question | Confidence | State | NIM call | What the model says |
|---|---|---|---|---|
| Which SKUs are at risk of stockout this week in the Midwest? | 1.00 | PASS | yes | Lists the 9 at-risk SKU/store rows by ID with supplier-delay context |
| Are any SKUs running low in the Northeast this week? | 0.50 | CAVEAT | yes | "No SKUs identified as running low" — clean negative answer with caveat that volume was 0 |
| Which SKUs are at risk of stockout this week across all our stores? | 0.65 | PASS (at threshold) | yes | Same retrieval as Midwest case, but receipt shows lower specificity multiplier (no region in question) |
| Which suppliers in Latvia are most reliable? | 0.30 | ABSTAIN | no | Queue ticket emitted, no NIM call. Receipt records that the parser found no region or intent signal. |

The Northeast clean-empty case is the demo-defining one: the model honestly says "none found" because the data is empty, and the receipt records exactly why confidence dropped (volume=0, recency=0, but specificity stayed 1.0). That is the audit story.

## Sample receipt (excerpt)

```json
{
  "receipt_id": "88acccdd-ad2a-4317-90a4-d1aea169d094",
  "timestamp": "2026-04-23T23:33:55+00:00",
  "user": "me@andyrosic.com",
  "query": "Which SKUs are at risk of stockout this week in the Midwest?",
  "confidence": 1.0,
  "confidence_components": {
    "data_coverage": 1.0,
    "recency": 1.0,
    "volume": 1.0,
    "query_specificity": 1.0,
    "coverage_subscore": 1.0,
    "specificity_multiplier": 1.0
  },
  "fallback": { "triggered": false, "path": "none" },
  "sources_queried": [
    {
      "source": "inventory.csv",
      "filter": "store_region == 'Midwest' AND on_hand_units < reorder_point",
      "rows_matched": 9,
      "row_ids": ["INV-1042-M217", "INV-2087-M217", "INV-3155-M217", "..."]
    }
  ],
  "model": {
    "provider": "nvidia_nim",
    "model_id": "nvidia/llama-3.3-nemotron-super-49b-v1",
    "endpoint": "https://integrate.api.nvidia.com/v1"
  }
}
```

The full schema lives in `receipt-schema.json`.

## Project layout

```
data/                   3 mock CSVs (inventory, sales, supply_signals)
src/
  agent.py              Orchestration: parse, retrieve, score, call, finalize
  receipt.py            Receipt dataclass + deterministic confidence math
  retrieval.py          Region + keyword filter (stdlib csv, no pandas)
  nim_client.py         OpenAI SDK against NIM, with stub fallback
  cli.py                CLI entrypoint
api/agent.py            Vercel Function wrapping run_agent (POST /api/agent)
index.html              Static UI served as the homepage on Vercel
ui/app.py               Streamlit two-panel UI for local dev
receipt-schema.json     JSON Schema for the receipt
vercel.json             Vercel deployment config
ARCHITECTURE.md         Why receipts are a first-class platform primitive
```

## What this is not

A production agent. The retrieval layer is naive keyword matching over CSVs. The data is mocked. There is no auth, no audit log persistence beyond local files, no policy engine, no integration into a real ERP or POS. `ARCHITECTURE.md` covers what production adds.

## License

MIT. See `LICENSE`.
