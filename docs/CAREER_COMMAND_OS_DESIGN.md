# ApplyAI Career Command OS Design System

Updated: 2026-09-02

## Product intent

ApplyAI is designed as a persistent candidate career operating system, not a generic job board or an AI chat wrapper. The interface should consistently help a candidate answer:

1. What should I do next?
2. Which opportunities deserve my attention?
3. What evidence supports my candidacy?
4. What is partial or not yet evidenced?
5. What should I prepare before pursuing the role?
6. Which active opportunities need follow-up?
7. What am I learning from my job-search process?

## Primary information architecture

The authenticated candidate workspace intentionally keeps five primary navigation areas:

- **Home** — Next Best Action, Jobs for You, Career Readiness, active opportunities.
- **Jobs** — discovery and decision-making.
- **Applications** — candidate-owned opportunity CRM.
- **Career Coach** — durable career evidence and preparation tools.
- **Profile** — canonical candidate information and account controls.

Secondary account/workflow destinations remain Plan, Settings, and Alerts.

Deep tools are grouped under these primary areas rather than flattened into the sidebar.

### Jobs workspace

Canonical routes remain stable:

| UI label | Route |
| --- | --- |
| Discover | `/jobs` |
| For You | `/matches` |
| Saved | `/saved` |
| Alerts | `/alerts` |
| Import Job | `/import-job` |

### Career Coach workspace

The design prompt used conceptual `/career/...` URLs. The repository already had stable production routes, so the redesign preserves them:

| UI label | Existing route |
| --- | --- |
| Career Memory | `/career` |
| Career Navigation | `/career/navigation` |
| Resume Studio / Resume Intelligence | `/resume/studio` |
| Opportunity-specific Interview Lab | `/interview/[jobId]` |
| Network | `/network` |
| Portfolio | `/portfolio` |
| Analytics | `/analytics` |

Resume Intelligence remains integrated with the existing résumé surfaces rather than creating a duplicate route solely for visual parity.

### Applications workspace

The repository currently has `/applications` and `/applications/[id]`. The redesign adds an opportunity-CRM navigation layer using only real destinations:

- Active → `/applications`
- Follow-ups → `/alerts`
- Resume Shares → `/resume/signals`

We deliberately do not invent empty Archived or Interviews routes. Opportunity-specific interview preparation remains available from the application workspace through `/interview/[jobId]`.

## Visual identity

The visual identity is **Career Command OS**: calm professional warmth plus high-trust intelligence.

### Light palette

- Background: `#F7F5F0`
- Surface: `#FFFFFF`
- Soft surface: `#FBFAF7`
- Warm surface: `#F1EDE5`
- Primary text: `#171717`
- Secondary text: `#525252`
- Muted text: `#8A8A8A`
- Career ink: `#172033`
- Career blue: `#315CFF`
- Indigo: `#4F46E5`
- Violet: `#7C3AED`
- Evidence green: `#16A34A`
- Gap amber: `#D97706`
- Risk red: `#DC2626`
- Portfolio teal: `#0F766E`

Gradients are intentionally limited to high-value hierarchy: primary marketing hero, Next Best Action, match/intelligence emphasis, and small brand accents.

### Typography

- Geist is the primary UI/display family already shipped by the app.
- Geist Mono is reserved for compact metadata, technical IDs, status-like values, and timestamps where appropriate.
- Large headings use tighter editorial spacing; operational copy remains highly scannable.

No font asset is bundled or exposed by the repository redesign.

## Component hierarchy

The redesign does not rewrite backend contracts. It visually upgrades existing functional components and adds a small set of reusable presentation patterns.

Key patterns:

- premium `AppShell` presentation through the existing `CandidateShell`;
- five-item desktop/mobile navigation;
- top command/search bar;
- privacy-state indicator;
- workspace pill navigation;
- Next Best Action hero card;
- evidence-support and evidence-gap semantics;
- opportunity cards and opportunity CRM rows;
- flagship Recruiter Lens perspective switcher;
- print/private-report controls;
- premium résumé upload and review treatment;
- privacy-safe engagement presentation;
- consistent empty/error/loading states.

## Home hierarchy

Home is a decision surface rather than a generic analytics dashboard:

1. **Next Best Action** — one prominent contextual action.
2. **Jobs for You** — a short list of opportunities to inspect.
3. **Career Readiness** — workflow/evidence readiness only.
4. **Active Opportunities** — existing pursuits plus truthful Resume Share engagement where available.
5. **Search** — an escape hatch when the candidate wants something specific.

Readiness is explicitly not employer interest or hiring probability.

## Job decision model

Job detail deliberately separates two actions:

- **Save for later** — passive interest.
- **Start application** — active pursuit that creates an opportunity workspace.

This prevents the candidate CRM from being filled with casual bookmarks.

The Job Detail hierarchy is:

1. source job facts;
2. Career Intelligence;
3. candidate Career System preparation;
4. Recruiter Lens;
5. company intelligence;
6. source description/requirements/skills;
7. pursue/save/share controls.

## Recruiter Lens

Recruiter Lens is a candidate preparation mirror. It visually emphasizes:

- readiness score and tier;
- selectable perspectives;
- candidate-owned reusable criteria;
- supported / partial / not-evidenced criteria;
- evidence snippets;
- potential concerns;
- questions to prepare for;
- print and private high-entropy report sharing.

Its product copy always states that it is not:

- an employer decision;
- hiring probability;
- viewer identity intelligence;
- a ranking of other candidates.

## Application CRM

Applications are framed as active opportunities. The application detail page connects:

- current stage;
- application preparation;
- submission boundary;
- history;
- notes/follow-ups;
- interview preparation;
- recruiter contacts;
- private Resume Share creation.

Resume Share copy states that engagement is anonymous unless a future user explicitly identifies themselves through a consent-based interaction.

## Onboarding and evidence honesty

The existing onboarding flow is preserved:

`Account → Résumé → Processing → Profile Review → Target Roles → Location → Work Preferences → Compensation → Review → Complete`

Visual enhancements make upload/processing feel intentional without fabricating parser progress. The product continues to state that parser output is a draft and only becomes candidate evidence after human review.

## Privacy UX

Privacy is visible near high-risk actions rather than buried only in settings.

Principles:

- candidate workspace is private by default;
- raw résumé objects remain private;
- portfolio publishing is explicit;
- Recruiter Lens report sharing is explicit and revocable;
- Resume Share reports engagement signals, not inferred human identity;
- no raw-IP/company guessing/cross-link fingerprinting UI is introduced;
- AI may transform verified evidence but must not invent career history or outcomes.

## Responsive behavior

The design is intended to remain usable at 375, 390, 768, 1024, and 1440 CSS pixels.

- desktop: fixed left navigation and sticky top command bar;
- <=900px: sidebar disappears and the five primary areas become bottom navigation;
- mobile job filters use the existing dialog flow;
- complex grids collapse to a single column;
- Recruiter Lens perspective pills fall back to a native select on narrow screens;
- action controls expand to full width when needed;
- reduced-motion preference disables decorative floating/scanning animation.

## Accessibility

The redesign preserves semantic links/buttons and adds/retains:

- visible `:focus-visible` treatment;
- semantic navigation landmarks and `aria-current`;
- accessible native-select fallback for Recruiter Lens on mobile;
- descriptive labels for illustrative marketing visuals;
- reduced-motion handling;
- no color-only explanation for the core evidence states;
- high-contrast light and system-dark palettes.

## Dark mode

The application remains light-first. `prefers-color-scheme: dark` provides an automatic dark presentation without introducing a new settings dependency or blocking launch. A persisted user appearance toggle can be added later if desired.

## Route and behavior preservation

This redesign intentionally avoids unnecessary route changes and backend rewrites. Existing API queries, mutations, Clerk auth boundaries, evidence rules, job provenance, application state, Resume Share privacy controls, and deterministic/AI-provider behavior remain authoritative.

The UI is expected to show graceful empty/error/loading states rather than manufacture metrics or success states when data is absent.

## Release boundary

The visual redesign is implemented on `agent/career-command-os-redesign`, stacked on `agent/reverse-engineering-gap-closure`. It must pass exact-head repository gates before integration.

The upstream reverse-engineering branch itself must still be reconciled with the current `agent/lean-production-wave-1` release branch before ApplyAI production release. A visual green build is not a substitute for the separate live Clerk/Vercel/backend/storage candidate-journey acceptance gate.
