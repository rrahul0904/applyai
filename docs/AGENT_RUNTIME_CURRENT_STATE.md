# ApplyAI Agent Runtime Current State

Updated: 2026-08-10

This is the repository-grounded gap audit performed before implementation on `main` commit `1b776ca236bdb1b662af7805f5db6eb830fc1371`.

| Capability | Starting classification | Release-1 action |
|---|---|---|
| AI provider abstraction / deterministic and OpenAI clients | EXISTS_AND_REUSABLE | Reused under Agent Runtime; agents do not import provider SDKs. |
| Career Intelligence artifacts/evidence | EXISTS_AND_REUSABLE | Reused for structured/evidence-first design. |
| Career Memory | EXISTS_AND_REUSABLE | Read through scoped Tool Gateway; arbitrary agent prose is not written directly to memory. |
| Canonical job/job-supply platform | EXISTS_AND_REUSABLE | Remains responsible for ingestion; agents consume canonical jobs. |
| Candidate profile/preferences/evidence | EXISTS_AND_REUSABLE | Exposed only through candidate-scoped tools. |
| Evidence-locked resume capability | EXISTS_AND_REUSABLE | Wrapped by Resume Tailor/Verifier workflow rather than duplicated. |
| PostgreSQL transactional outbox | EXISTS_AND_REUSABLE | `AGENT_RUN` is now a routed outbox task family. |
| SQS worker pattern | EXISTS_NEEDS_EXTENSION | Added dedicated agent queue/DLQ and generic Agent Worker. |
| Operator `/admin` | EXISTS_NEEDS_EXTENSION | Extended with agent definitions/runs/failures/approvals/cost controls. |
| Staging Terraform/ECS | EXISTS_NEEDS_EXTENSION | Added dormant Agent Worker service and queue infrastructure. |
| Clean-room | EXISTS_NEEDS_EXTENSION | Added LocalStack agent queue/DLQ, Agent Worker, deterministic demo/acceptance. |
| Durable agent state machine | MISSING | Implemented. |
| Agent Registry | MISSING | Implemented. |
| Tool Registry/Gateway | MISSING | Implemented. |
| READ/PREPARE/EXECUTE permission model | MISSING | Implemented. |
| Approval primitive | MISSING | Implemented; no external EXECUTE agent enabled in release 1. |
| Agent budgets/cost telemetry | MISSING | Implemented. |
| Agent leasing/idempotency/retry | MISSING | Implemented. |
| Job Scout / Job Research / Resume Tailor / Resume Verifier | MISSING | Implemented as release-1 agents. |
| Live staging queue/worker/model evidence | EXTERNAL_DEPENDENCY | Must be proven through `AGENT_STAGING_ACCEPTANCE.md`; not fabricated in source control. |
| Automatic application submission | OUT_OF_RELEASE_1_SCOPE | Future EXECUTE-class release after approval/idempotency staging evidence. |

The implementation intentionally does not introduce LangChain/LangGraph/CrewAI/AutoGen or a microservice per agent. The existing ApplyAI architecture is extended rather than replaced.
