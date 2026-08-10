# ApplyAI Agent Permission Model

Updated: 2026-08-10

## Execution classes

ApplyAI agents use three explicit classes.

### READ

May inspect allow-listed resources. Examples: Job Scout, Job Research, Resume Verifier.

### PREPARE

May create a proposed artifact but cannot create an external side effect. Example: Resume Tailor.

### EXECUTE

May affect an external system only after separate approval-policy validation. No release-1 agent has automatic external execute rights.

## Definitions are versioned

Every agent definition pins:

- name/version;
- execution class;
- allowed and denied tools;
- input/output schemas;
- max steps/timeout/tokens/cost;
- queue class/priority;
- provider strategy;
- prompt/schema versions;
- approval requirement.

Historical runs keep their definition version even after a newer version is introduced.

## Release-1 permissions

| Agent | Class | Core tools | Explicitly denied |
|---|---|---|---|
| Job Scout v1 | READ | candidate profile/evidence, Career Memory, job, application read | application submit, email send, evidence write |
| Job Research v1 | READ | candidate evidence, Career Memory, job/company | application submit, email send |
| Resume Tailor v1 | PREPARE | candidate evidence, Career Memory, job, master resume, prior agent artifacts | application submit, email send, evidence write |
| Resume Verifier v1 | READ | candidate evidence, job, master resume, tailored artifact | application submit, email send, evidence write |

## Tool Gateway decision

```text
requested tool
  -> registered?
  -> explicitly allowed?
  -> not explicitly denied?
  -> tool class <= agent class?
  -> candidate/resource scope valid?
  -> execute and audit
```

Any failed condition denies the call.

## Operator overrides

`agent_runtime_policies` provides a durable operator override. Operators can pause or re-enable a version without changing source code. Worker execution re-checks the persisted policy before a handler runs, so admin state is enforced rather than cosmetic.

## Cost override

An operator may lower an agent's configured max cost. Runtime uses the stricter of the source definition and persistent override. An operator override cannot silently increase a source-controlled maximum.

## Future EXECUTE tools

Examples such as `application.submit`, `email.send`, `calendar.create` are intentionally absent from the release-1 Tool Registry. When introduced, each must define its own idempotency and approval contract and must be classified `EXECUTE`.
