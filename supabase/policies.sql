-- ApplyAI Supabase defense-in-depth policies.
-- Canonical application authorization remains in FastAPI. The public application schema
-- is API-only: Supabase Auth is used for identity and Supabase Storage may use explicit
-- user-scoped policies, but PostgREST must not become a parallel application data API.

begin;

create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.applyai_current_user_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select u.id
  from public.users u
  where u.auth_user_id = (select auth.uid())
    and u.account_status <> 'DELETED'
  limit 1
$$;

revoke all on function private.applyai_current_user_id() from public;
grant execute on function private.applyai_current_user_id() to authenticated;

-- Fail closed for every current application table in public. PostgreSQL owners and
-- service_role bypass RLS, so FastAPI/server-side database access remains unaffected.
-- anon/authenticated receive no direct application table privileges.
do $$
declare
  target record;
begin
  for target in
    select schemaname, tablename
    from pg_tables
    where schemaname = 'public'
  loop
    execute format(
      'alter table %I.%I enable row level security',
      target.schemaname,
      target.tablename
    );
  end loop;
end
$$;

revoke all privileges on all tables in schema public from anon, authenticated;
revoke all privileges on all sequences in schema public from anon, authenticated;
revoke execute on all functions in schema public from public, anon, authenticated;

-- Supabase grants broad Data API access to new public objects by default. Remove those
-- defaults for objects created by ApplyAI's canonical postgres migration role.
alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated;

-- Explicit high-sensitivity table declarations remain here as readable invariants and
-- as protection if this file is selectively audited or ported.
alter table public.users enable row level security;
alter table public.candidate_profiles enable row level security;
alter table public.candidate_preferences enable row level security;
alter table public.candidate_target_roles enable row level security;
alter table public.candidate_experiences enable row level security;
alter table public.candidate_education enable row level security;
alter table public.candidate_skills enable row level security;
alter table public.resumes enable row level security;
alter table public.resume_versions enable row level security;
alter table public.saved_jobs enable row level security;
alter table public.applications enable row level security;
alter table public.application_documents enable row level security;
alter table public.application_answers enable row level security;
alter table public.application_notes enable row level security;
alter table public.resume_share_links enable row level security;
alter table public.user_roles enable row level security;
alter table public.roles enable row level security;

-- These self-read policies are deliberately privilege-inert today because the table
-- grants above are revoked. They can support a future explicitly reviewed read-only UI
-- without weakening the default API-only posture.
drop policy if exists "applyai users read self" on public.users;
create policy "applyai users read self"
on public.users for select
to authenticated
using (id = (select private.applyai_current_user_id()));

drop policy if exists "applyai users read own roles" on public.user_roles;
create policy "applyai users read own roles"
on public.user_roles for select
to authenticated
using (user_id = (select private.applyai_current_user_id()));

drop policy if exists "applyai authenticated read role names" on public.roles;
create policy "applyai authenticated read role names"
on public.roles for select
to authenticated
using (true);

-- Private resume objects use the existing storage key shape:
-- candidate/{applyai_internal_user_uuid}/resume/{resume_uuid}/{version}.{ext}
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do update set public = false;

drop policy if exists "applyai resume objects select own" on storage.objects;
create policy "applyai resume objects select own"
on storage.objects for select
to authenticated
using (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select private.applyai_current_user_id())::text
);

drop policy if exists "applyai resume objects insert own" on storage.objects;
create policy "applyai resume objects insert own"
on storage.objects for insert
to authenticated
with check (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select private.applyai_current_user_id())::text
);

drop policy if exists "applyai resume objects update own" on storage.objects;
create policy "applyai resume objects update own"
on storage.objects for update
to authenticated
using (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select private.applyai_current_user_id())::text
)
with check (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select private.applyai_current_user_id())::text
);

drop policy if exists "applyai resume objects delete own" on storage.objects;
create policy "applyai resume objects delete own"
on storage.objects for delete
to authenticated
using (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select private.applyai_current_user_id())::text
);

commit;
