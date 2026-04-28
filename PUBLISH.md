# Publish kit

Two artifacts: the 3-minute demo script and the LinkedIn caption draft. Both are scoped to the NVIDIA Director, Product Platform Retail and CPG application (JR2015305).

- Live demo URL: https://nvidia-receipts.vercel.app/
- Repo: https://github.com/andyuninvited/nvidia-receipts
- Architecture writeup: https://github.com/andyuninvited/nvidia-receipts/blob/main/ARCHITECTURE.md

---

## Demo script (3 minutes, hard cap)

Open Streamlit on a clean browser, full screen. No music. Plain narration.

### Minute 1 — The problem (60 sec)

> "Enterprise retail adoption of agentic AI does not stall on the model. It stalls at the risk committee. I have spent the last few weeks talking to retail product and ops leader friends and the same three blockers keep coming up. First, audit-grade receipts. The risk team will not approve an answer they cannot reconstruct. Second, legacy coexistence. Dinosaurs tech like AS/400, SAP ECC, and ColdFusion are not getting replaced. Third, ROI math at single-digit percent net margins. AI spend has to return 3 to 5x in 18 months. The platform that solves all three owns the category. This weekend I built the receipts piece on the NVIDIA NIM stack."

### Minute 2 — The walkthrough (75 sec)

Live Vercel URL on screen: https://nvidia-receipts.vercel.app/

> "Operator question: which SKUs are at risk of stockout this week in the Midwest." [Click sample pill 1. Click Run agent.]

> "Answer on the left names the SKU and store combinations short of the reorder point and flags the supplier delays driving them. The receipt on the right is the headline of the demo."

> "Confidence is one point zero. It is not the model's self-reported number. It is computed deterministically from data coverage, recency, volume, and a query specificity term. Every term is reproducible from the receipt alone. Sources queried lists all three CSVs with the exact filter applied and the row IDs pulled. Prompt context records the character count and SHA-256 of the full prompt sent to the model. An auditor can verify nothing was tampered with after the fact."

> "Now a region with no risk." [Click sample pill 2: 'Are any SKUs running low in the Northeast this week?']

> "The model honestly says no SKUs are running low. But notice the receipt: confidence is point five, in the caveat band. The system queried all three sources cleanly. Coverage is one. Specificity is one. But volume is zero and recency is zero because no rows came back. The receipt explains the model's clean negative answer at a confidence the risk team can audit. This is the case I want the platform to handle."

> "And the failure case." [Click sample pill 4: 'Which suppliers in Latvia are most reliable?']

> "Confidence drops to point three. The parser found no region or intent signal. The specificity multiplier collapses the score. The agent does not call the model at all. It abstains and surfaces a queue ticket for human review. The receipt explains exactly why."

### Minute 3 — Why this generalizes (45 sec)

> "This pattern is not specific to stockout questions. The receipt layer sits between three NVIDIA components. NeMo Retriever populates sources queried. NIM populates the model block. NeMo Guardrails populates the fallback decision. Every NVIDIA Retail Blueprint, the Shopping Advisor, Personalized Recommendations, Customer Service, ships the model and the orchestration. None of them ship the receipt layer. That is the gap, and it is what unlocks production deployment in regulated retailers."

> "Code is on GitHub, MIT licensed, runs in 10 minutes. Architecture doc walks through what production adds. I'm Andy Rosic. Thanks for watching."

---

## LinkedIn caption (draft)

Three options. The middle one is my recommended publish.

### Option A — Direct

I am applying for NVIDIA's Director, Product Platform Retail and CPG role, and I built a working prototype on their stack to show what I think the platform needs.

Enterprise retail adoption of agentic AI stalls at the risk committee, not the model. The blocker is that risk teams cannot sign off on an answer they cannot reconstruct. So this weekend I built a minimal retail agent on NIM that emits an audit-grade receipt for every response. The receipt records what data was pulled, what context the model received, a deterministic confidence score, and which fallback path triggered. Vague questions abstain and route to human review. Specific questions answer with full provenance.

The receipt is the artifact the risk committee actually signs off on. It is what unlocks production deployment in regulated retailers, and I think it is the missing primitive in the NVIDIA Retail Blueprints surface.

Code: https://github.com/andyuninvited/nvidia-receipts
Architecture writeup explaining why receipts are a platform primitive, not an SDK feature: https://nvidia-receipts.vercel.app/  (repo: https://github.com/andyuninvited/nvidia-receipts)

If you work on agentic platforms in retail, I would love to compare notes.

### Option B — Recommended

Most agentic AI demos show the model. This one shows the receipt.

Enterprise retail adoption of agentic AI stalls at the risk committee. The blocker is reconstructability. Risk teams will not approve an answer they cannot trace back to the data, the prompt, the confidence math, and the fallback decision.

I built a weekend prototype on the NVIDIA NIM stack that makes the receipt a first-class artifact. Every agent response ships with a structured JSON record of: sources queried with row IDs, prompt context with a SHA-256, deterministic confidence broken into four components, and a fallback decision. Vague questions abstain and route to human review with a queue ticket. Specific questions answer with full provenance.

This is the piece I think is missing from every NVIDIA Retail Blueprint. The receipt sits between NeMo Retriever, NIM, and NeMo Guardrails. It is what gets a project past compliance and into production in retailers that run 2 to 6 percent net margins.

Code, architecture writeup, and a 3-minute walkthrough: https://nvidia-receipts.vercel.app/  (repo: https://github.com/andyuninvited/nvidia-receipts)

### Option C — Provocative

Confidence scores from LLMs are a compliance failure mode.

A model marking its own paper is not an audit trail. It is a tautology. So this weekend I built a retail agent on the NVIDIA NIM stack where confidence is computed deterministically from observable properties of the retrieval, not asked of the model. Every response ships with a structured receipt that a risk committee can actually sign off on.

The receipt is the platform primitive that unlocks regulated retail. Repo and architecture writeup: https://nvidia-receipts.vercel.app/  (repo: https://github.com/andyuninvited/nvidia-receipts)

---

## Posting checklist

- [x] Push to public GitHub `andyuninvited/nvidia-receipts` (MIT)
- [x] Deploy live at https://nvidia-receipts.vercel.app/ (Vercel + NIM key in env vars)
- [x] Update README links at the top of this file
- [x] Verify all 4 sample questions exercise PASS / CAVEAT / PASS-at-edge / ABSTAIN with live NIM
- [ ] Test clone-and-run on a fresh machine in under 10 minutes
- [ ] Record the demo, upload to Loom or GitHub release asset
- [ ] Publish Monday morning between 8 and 10 AM PT
- [ ] Send a direct message to the NVIDIA recruiter or hiring manager with a short note pointing at the post
