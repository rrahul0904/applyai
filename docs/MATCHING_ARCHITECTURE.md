# Matching Architecture

## Status

Matching is NOT STARTED by design. No percentage match is displayed.

## Preconditions

- verified candidate profile;
- canonical structured job;
- role and skill taxonomies;
- candidate preference and eligibility rules;
- tested retrieval;
- evaluation and calibration dataset.

## Planned staged model

1. **Eligibility:** location, authorization, employment type, compensation,
   work mode, excluded companies.
2. **Role fit:** title family, seniority, management scope, domain.
3. **Experience fit:** responsibilities, skill coverage, leadership, industry.
4. **Retrieval:** keyword, semantic, recency, quality, preference.
5. **Deep analysis:** only for promising candidates/jobs.

Outputs will show factor-level evidence and gaps. Formulas and feature versions
will be stored. LLM output will never be the sole score.
