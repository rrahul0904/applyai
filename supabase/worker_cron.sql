-- Apply only after the Vercel FastAPI production URL is verified.
-- Store these values in Supabase Vault first:
--   applyai_api_url             -> https://<verified-api-domain>
--   applyai_worker_drain_secret -> a random >=24-character server secret

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net;
create extension if not exists supabase_vault with schema vault;

select cron.schedule(
  'applyai-bounded-worker-drain',
  '* * * * *',
  $$
  select net.http_post(
    url := (
      select decrypted_secret
      from vault.decrypted_secrets
      where name = 'applyai_api_url'
      limit 1
    ) || '/api/v1/internal/worker/drain',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'applyai_worker_drain_secret'
        limit 1
      )
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 55000
  ) as request_id;
  $$
);
