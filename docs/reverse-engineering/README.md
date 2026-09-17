# ApplyAI reverse-engineering intake

Every clean-room reverse-engineering summary must answer one product question before implementation work begins:

> Does the observed capability strengthen ApplyAI's candidate journey, strengthen the platform that serves that journey, belong behind an integration boundary, or belong outside ApplyAI?

The canonical candidate journey is:

**Discover jobs → understand fit → improve resume/profile → apply → track → learn skill gaps → prepare for interviews → practice/mock → measure readiness → manage career intelligence**

## ApplyAI Fit taxonomy

| Classification | Meaning | Default scope | Default destination |
| --- | --- | --- | --- |
| `CORE` | Direct candidate experience | `FULL` | `candidate-core` |
| `PREPARE` | Learning and interview preparation | `FULL` | `prepare` |
| `INTELLIGENCE` | Job, company, recruiter, salary, and career decision intelligence | `FULL` | `career-intelligence` |
| `INFRASTRUCTURE` | Evaluation, provenance, guardrails, observability, and agent quality | `PARTIAL` | `platform-infrastructure` |
| `INTEGRATION` | Specialist/external systems ApplyAI should consume instead of duplicate | `PARTIAL` | `external-integration` |
| `NOT_APPLYAI` | Different product domain | `NONE` | `separate-product` |

The taxonomy is a product-boundary decision, not a quality ranking.

## Required summary contract

Every summary in this directory, except this README, must include YAML frontmatter:

```yaml
---
applyai_fit: INFRASTRUCTURE
fit_scope: PARTIAL
destination: platform-infrastructure
---
```

and all of these headings:

```text
## ApplyAI Fit
## Why this qualifies
## Candidate journey stages
## Absorb into ApplyAI
## Keep separate
## Implementation destination
## Implementation status
```

`python scripts/validate_reverse_engineering_summaries.py` enforces this contract in CI.

## Classification workflow

1. Record publicly observable behavior and evidence.
2. State the clean-room boundary. Never copy proprietary source, hidden APIs, private prompts, or non-public implementation details.
3. Run the deterministic, versioned ApplyAI Fit classifier.
4. Review the result against the candidate journey.
5. Record an operator override only when the auto-classification misses material product context.
6. Split the research into capabilities to absorb and capabilities to keep separate.
7. Set the implementation destination and status.
8. Implement only the qualifying behavior through ApplyAI's existing architecture and safety boundaries.
9. Preserve repository, test, hosted-release, and browser evidence as separate certification gates.

The operator registry at `/admin/reverse-engineering` persists the same decision model. Its `classification_source` makes automatic decisions and human overrides distinguishable.

For AI agent/skill/workflow changes, a baseline/candidate evidence file can be evaluated as an executable release gate:

```bash
cd services/api
uv run python scripts/evaluate_release.py path/to/evidence.json --receipt-out artifacts/eval-receipt.json
```

The command exits non-zero when evidence is partial, the candidate crosses the configured regression threshold, or trigger precision/recall miss their configured floors. No synthetic performance evidence is checked into the repository; callers must supply real run evidence.

## Clean-room rule

Reverse engineering means reproducing useful observable behavior from public evidence through an independent implementation. It does **not** mean copying proprietary code, bypassing access controls, extracting secrets, reproducing protected assets, or claiming hidden behavior that has not been observed.
