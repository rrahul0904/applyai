# Code Audit

| Previous component | Classification | Decision |
|---|---|---|
| REST profile/save/application contract concepts | MIGRATE | Preserved as versioned FastAPI routes |
| Candidate ownership intent | KEEP | Strengthened with token-derived internal UUID filters |
| Resume validation and object metadata concepts | MIGRATE | Moved to `ObjectStorageProvider` plus PostgreSQL metadata |
| Application status event concept | KEEP | Implemented transactionally and tested |
| D1 Drizzle schema/routes | REMOVE | SQLite semantics conflicted with approved PostgreSQL architecture |
| Vinext/Vite/Worker runtime | REMOVE | Replaced with official Next.js App Router |
| OpenAI workspace-header authentication | REMOVE | Replaced with Clerk JWT verification |
| Starter loading skeleton | REMOVE | It was temporary infrastructure, not working product capability |
| Cloudflare Sites deployment metadata | REMOVE | Deployment is now Vercel/AWS portable |
| Static job-card proposal | REMOVE | UI must consume canonical backend records |

No complete candidate screen was removed. The visible application was still the
starter placeholder when the correction began.
