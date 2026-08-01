# Search Architecture

## Provider boundary

Product APIs depend on `SearchProvider`, not a specific engine.

## CURRENT

`PostgresSearchProvider` supports keyword matching across title, description,
and company plus structured location, work-mode, employment-type, seniority,
and company filters. Results come only from canonical active jobs.

This is a foundation implementation. It does not yet claim complete full-text,
faceting, autocomplete, geographic, or semantic behavior.

## PLANNED

- PostgreSQL `tsvector` full-text index and ranked `tsquery`.
- Structured filters and keyset pagination.
- pgvector candidate/job retrieval once representation and evaluation datasets
  exist.
- Search state represented in web URLs.
- Query latency, relevance, freshness, save, and apply-start metrics.

## FUTURE SCALE

`OpenSearchSearchProvider` may be introduced when query volume, facets,
autocomplete, or hybrid retrieval justify it. PostgreSQL remains canonical.
Search indexes are rebuildable derived state.
