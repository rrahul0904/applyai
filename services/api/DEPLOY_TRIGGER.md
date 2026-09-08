# ApplyAI backend deployment trigger

Production provider activation: Supabase Auth project `hgrmgbukjmpwnuwpyids`.

This file intentionally lives under `services/api` so Railway's configured
`/services/api/**` watch pattern rebuilds the existing API and worker services
from the finalization branch after provider-variable changes.
