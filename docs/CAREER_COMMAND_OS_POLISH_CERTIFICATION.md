# Career Command OS — Final UI Polish & Responsive Certification

This document records the final refinement wave layered on top of the Career Command OS redesign. It is intentionally a polish/certification pass, not another product redesign.

## Product contract preserved

The five primary candidate areas remain:

1. Home
2. Jobs
3. Applications
4. Career Coach
5. Profile

The product continues to frame candidate data as verified, candidate-reported, parser draft, or not evidenced. Recruiter Lens remains candidate preparation guidance and never claims employer scoring, employer interest, viewer identity, or hiring probability.

## What changed

### Progressive disclosure

Recruiter Lens now presents:

- a concise “What matters first” summary;
- the first three evidence criteria by default;
- an explicit “show more” control for the remaining criteria;
- collapsed concerns and preparation-question panels;
- the full privacy/data-honesty disclaimer at all times.

This reduces initial reading length on mobile and short laptops without hiding the underlying evidence.

### Touch ergonomics

The final polish layer uses a 44px touch target baseline and raises key mobile controls to 48px. This applies to:

- save/bookmark actions;
- filter controls;
- dialog close controls;
- workspace tabs;
- top-bar icon actions;
- mobile navigation;
- Recruiter Lens perspective/report actions;
- primary job/application actions.

Icon glyphs may remain visually small, but their hit area does not.

### Contrast and typography

Important secondary text moved to a stronger neutral token so job metadata, explanations, helper text, application activity, and empty/error descriptions remain legible on lower-quality laptop displays and outdoor mobile screens.

Important UI copy should not rely on tiny decorative metadata. Core explanatory text remains at readable body sizes and line heights.

### Human states

The shared error state no longer defaults to “Something went wrong.” Its default language explains that the requested information is unavailable and gives a useful retry/return path.

Product-specific empty states remain responsible for explaining what will appear, why it is empty, and what the candidate can do next.

### Mobile-native behavior

At phone widths:

- the dedicated five-item bottom navigation remains primary;
- job cards become single-column decision cards;
- bookmark controls keep a large hit target;
- Review Role expands to the available action width;
- Job Detail moves decision context before long body copy;
- sticky desktop decisions become normal-flow sections;
- filter dialogs become bottom-sheet style panels;
- form controls use at least 48px height and 16px input text to avoid unwanted iOS zoom;
- workspace tabs become horizontally scrollable rather than compressing labels;
- long titles and company names wrap safely;
- no product surface should depend on a hover-only interaction.

### Tablet behavior

Tablet is treated as a distinct layout class rather than a stretched phone.

For portrait-ish tablet widths, content becomes single-column where reading benefits from it while Applications uses card grids where density helps. For larger tablet/compact-laptop widths, the sidebar is narrowed and Job Detail uses a balanced content/decision split.

### Laptop behavior

For 13-inch and short-height laptops:

- main vertical padding is reduced;
- page-heading spacing is tightened;
- dashboard grid gaps are slightly reduced;
- the Next Best Action card is shortened without losing hierarchy;
- dialogs are height-constrained and scroll internally;
- main content remains capped rather than stretching across ultrawide screens.

## Automated responsive certification

`apps/web/e2e/responsive-certification.spec.ts` validates representative candidate surfaces at:

| Classification | Viewport |
| --- | --- |
| Mobile | 375 × 812 |
| Mobile | 390 × 844 |
| Mobile | 430 × 932 |
| Tablet | 768 × 1024 |
| Tablet | 820 × 1180 |
| Tablet landscape / compact desktop | 1024 × 768 |
| Laptop | 1280 × 800 |
| Desktop | 1440 × 900 |

The automated checks cover:

- no document-level horizontal overflow;
- correct desktop sidebar vs mobile navigation mode;
- mobile navigation touch height;
- Home hierarchy;
- Jobs results;
- mobile filter visibility;
- bookmark minimum hit area;
- Applications CRM rendering;
- a 390px Job Detail + Recruiter Lens journey;
- mobile perspective selector visibility;
- Start Application touch size;
- privacy/hiring-probability disclaimer visibility.

When `DEMO_CAPTURE_DIR` is present, the same spec captures breakpoint-specific Home, Jobs, Applications, and mobile Recruiter Lens screenshots for visual review.

## Accessibility behavior

The existing UI primitive layer continues to use Radix dialogs/selects/tabs, retaining keyboard behavior, Escape-to-close, modal focus management, and accessible semantics. The polish layer adds stronger focus/touch treatment and maintains reduced-motion overrides.

Status is not communicated by color alone: Recruiter Lens labels supported, partial, and not-evidenced states in text.

## Visual QA checklist

For each certified screenshot verify:

- no horizontal overflow;
- no clipped buttons;
- no bottom-nav overlap;
- no hidden primary action;
- no tiny icon-only tap targets;
- no awkward title/company wrapping;
- no unreadable helper/metadata text;
- no dialog extending beyond the usable viewport;
- no sticky desktop element covering mobile content;
- no overly dense Recruiter Lens initial state.

## Not changed

This wave does not:

- alter authentication architecture;
- change backend contracts;
- invent candidate evidence;
- add employer ranking;
- infer named résumé viewers or companies;
- add hiring-probability claims;
- create paid frontend dependencies;
- change the five-area information architecture.

## Release gate

This polish branch is stacked on `agent/career-command-os-redesign`. It must remain separate from `main` until the stacked release chain is reconciled and exact-head CI is green.

Source-level responsive readiness is not the same as real-device production acceptance. Before calling the interface fully certified in production, repeat visual/browser checks against the real Vercel Preview with actual Clerk and backend integration.
