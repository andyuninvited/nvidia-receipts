# Architecture

## Thesis

Enterprise retail adoption of agentic AI is won or lost on three things that are not the model.

1. **Audit-grade receipts.** Outputs the risk committee can sign off on, showing exactly what data was pulled, what context the model received, what confidence applied, and what fallback path triggered.
2. **Legacy coexistence.** Retailers run AS/400, SAP ECC, ColdFusion, Oracle Retail, and a long tail of in-house systems that are not getting replaced this decade. An agent that demands a green-field stack ships into a graveyard.
3. **Outsized ROI math.** Net margins in retail run 2 to 6 percent. AI spend has to return 3 to 5x in documented value within 18 months, or the program dies before its second budget cycle.

The platform that solves all three owns the category. This prototype manifests the receipts piece.

## Why receipts are a platform primitive

In most agent stacks, "logging what the agent did" is an application-level concern. Each team adds it after the fact, in different shapes, with different gaps. By the time the risk committee asks for an audit, the team is reconstructing what happened from scattered logs, prompts in source control, and model output cached in different stores.

A receipt is the inverse pattern. It is generated **as the agent runs**, by the platform, in a single canonical schema. It is emitted before the model call, populated as the call proceeds, and finalized before the response is returned to the consumer surface. This ordering matters. A receipt assembled retroactively can be tampered with. A receipt generated inline cannot.

This is what makes receipts a platform primitive rather than an SDK feature. They have to be present in the runtime, not bolted on by the developer.

## The receipt as a contract

The receipt schema is the contract between the agent runtime and three downstream consumers.

| Consumer | What they need |
|----|----|
| Risk and compliance | Reproducibility. Given a receipt, can they pull the exact rows the agent saw, replay the prompt, and verify the answer? |
| Operations | Triage. When an answer is wrong, was it the data, the retrieval, the prompt, or the model? |
| Finance | Cost attribution. Which queries are expensive, which fall back, and what is the production cost of the abstain path? |

Because the receipt is structured (see `receipt-schema.json`), each consumer reads what they need without coordination. The risk team writes a SOC 2 control that asserts every production response has a receipt with `confidence`, `confidence_components`, and `prompt_context.sha256`. The operations team builds a triage UI. The finance team queries `duration_ms` and `model.model_id` for cost rollups.

## Confidence as a deterministic function

The confidence number on the receipt is not the model's self-reported confidence. A risk committee cannot accept a system that lets the model grade its own work.

Instead, confidence is a deterministic function of four observable properties of the retrieval and the query.

```
confidence = coverage_subscore * specificity_multiplier

coverage_subscore = 0.5 * data_coverage + 0.3 * recency + 0.2 * volume
specificity_multiplier = 0.3 + 0.7 * query_specificity
```

- **data_coverage** = fraction of expected sources that returned at least one row.
- **recency** = 1.0 if all matched rows are within 14 days, decaying linearly to 0.0 at 90 days.
- **volume** = `min(total_rows_matched / 10, 1.0)`.
- **query_specificity** = fraction of expected query signals (region, intent) the parser extracted.

Every term is reproducible from the receipt alone. An auditor with the receipt can recompute the confidence from scratch and either confirm or contradict the agent's own number.

The specificity multiplier is the key insight. A vague question that returns a full table at high coverage is the worst case for an agent: confident answer over irrelevant data. The specificity term punishes the parser's failure to understand the question, not the data layer's success at returning rows.

## Fallback as a first-class behavior

Two thresholds govern the fallback decision.

- Below the **caveat threshold** (default 0.65), the agent answers but prefixes the response with `[LOW CONFIDENCE]` and forces the consumer surface to render the caveat alongside the answer.
- Below the **abstain threshold** (default 0.40), the agent does not call the model at all. It returns a templated decline and emits a queue ticket for human review. The receipt records the decision and the reason.

Abstaining is not failure. It is the platform refusing to spend a budgeted call when the data does not support an answer. In a 2 to 6 percent net margin business, the cost of a wrong, confidently delivered answer dwarfs the cost of the abstain.

## What this prototype skips

This is a weekend prototype. The scaffolding is intentionally incomplete.

| Production layer | What this prototype does | What production adds |
|----|----|----|
| Retrieval | Keyword and region match over local CSVs | Predicate pushdown into ERP, POS, supplier portal, and a vector store via NeMo Retriever |
| Audit log | Local JSON files in `receipts/` | Append-only object store with hash chain and SOC 2 control mappings |
| Policy | Inline thresholds in `agent.py` | NeMo Guardrails policy engine with versioned policy bundles |
| Identity | Email string in the receipt | SSO subject, role, and entitlement context from the enterprise IdP |
| Replay | None | Receipt-driven replay harness that reissues the prompt against any model and diffs outputs |
| Privacy | None | PII redaction in the prompt context preview, with hash retained for verification |
| Cost telemetry | `duration_ms` only | Token counts, model cost attribution, and per-team chargeback |

None of these require a redesign of the receipt schema. They are downstream of it.

## Hosted NIM versus self-hosted ("Bring LLM to NIM")

This prototype calls NVIDIA's hosted inference at `integrate.api.nvidia.com/v1` because the goal is reproducibility on a free-tier API key in under 10 minutes. The alternative path, self-hosted NIM via the "Bring LLM to NIM" container, lets a customer take any HuggingFace model and serve it on their own GPU with TensorRT-LLM optimization. That is the right path for production deployments where the customer needs in-VPC inference, data-residency control, or a model fine-tuned on their proprietary data. For the receipts platform, the boundary does not move: the receipt schema, the deterministic confidence math, and the fallback decisions are identical across hosted and self-hosted NIM. Only the `model.endpoint` field on the receipt changes.

## How this fits NVIDIA's retail surface

The NVIDIA AI Blueprints for retail (Shopping Advisor, Personalized Recommendations, Customer Service, plus the agentic patterns built on the NIM Agent Toolkit) all ship the model and the orchestration. None of them ship the receipt layer. That is the gap.

The receipt layer sits between three NVIDIA components.

- **NeMo Retriever** populates `sources_queried` with the structured query, the filter, and the row IDs.
- **NIM** populates `model.provider`, `model_id`, and `endpoint`. The OpenAI-compatible interface means legacy systems can call NIM directly, and the receipt is generated by a sidecar that wraps the call.
- **NeMo Guardrails** populates `fallback` with policy decisions: confidence thresholds, PII rules, geographic restrictions, content policies.

The receipt is the artifact that ties them together and the artifact that the customer's risk committee actually reads.

## Legacy coexistence note

The receipts pattern is uniquely well-suited to legacy retail stacks. A mainframe can call a NIM-hosted model through an OpenAI-compatible HTTP endpoint with no changes to the legacy code. The receipt is generated by the sidecar, written to object storage, and surfaced through whatever audit tool the customer already uses (ServiceNow, Splunk, internal dashboards). No new auth model, no new client SDK, no new dependency in the legacy code path.

## ROI math note

The receipts layer adds roughly one JSON write per response and a deterministic computation that runs in single-digit milliseconds. The cost is epsilon. The value is binary: without the receipts, the program does not get past the risk committee, and the budget rolls into the next planning cycle without a green light. With them, the program ships and books value against the 3 to 5x return target. This is why receipts are not an enhancement. They are the unlock.
