# ApplyAI Agent Approval Model

Updated: 2026-08-10

## Principle

`EXECUTE` permission and human approval are separate gates. An agent being classified `EXECUTE` never means it may execute unconditionally.

## Durable approval

`agent_approvals` records:

- run and candidate;
- action type;
- optional artifact;
- status;
- policy version;
- request/approve/reject timestamps;
- approving user;
- optional expiry.

Statuses:

`PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `CANCELLED`.

## Release 1

The first four agents are READ/PREPARE only. The approval data model and candidate APIs are implemented now so future external execution can be added without changing the trust model.

## Candidate approval checks

Before a future external action runs the server must verify:

1. approval belongs to the same candidate as AgentRun;
2. approval belongs to the exact run/action;
3. artifact ID matches when an artifact is part of the action;
4. approval is `APPROVED`;
5. approval has not expired;
6. external target remains valid;
7. action idempotency key has not executed previously.

A different candidate cannot approve the record even if they know the UUID.

## Rejection

Rejection is final for that approval record. A changed artifact/action requires a new approval rather than mutating historical consent.

## Future defaults

Initially:

- analysis/research: no approval to generate;
- resume/application drafts: no approval to generate;
- application submission: approval required;
- recruiter message send: approval required;
- withdrawal: approval required;
- interview/calendar mutation: approval required.

Candidate automation preferences may be considered later only after individual external actions have staging evidence and explicit product policy.

## UI authority

UI controls are convenience only. The backend is authoritative. An intercepted or replayed client request cannot turn a pending/expired/cross-candidate approval into permission.
