-- ApplyAI Supabase defense-in-depth policies.
-- Canonical application authorization remains in FastAPI. These policies prevent the
-- Supabase Data API / Storage API from becoming a parallel authorization bypass.

begin;

create or replace function public.applyai_current_user_id()
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

revoke all on function public.applyai_current_user_id() from public;
grant execute on function public.applyai_current_user_id() to authenticated;

-- Candidate-owned application tables remain API-only. RLS is enabled and direct
-- anon/authenticated table privileges are revoked. This is deliberate: browser traffic
-- reaches these records through FastAPI, where business authorization and audit behavior live.
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

revoke all on table
  public.users,
  public.candidate_profiles,
  public.candidate_preferences,
  public.candidate_target_roles,
  public.candidate_experiences,
  public.candidate_education,
  public.candidate_skills,
  public.resumes,
  public.resume_versions,
  public.saved_jobs,
  public.applications,
  public.application_documents,
  public.application_answers,
  public.application_notes,
  public.resume_share_links,
  public.user_roles,
  public.roles
from anon, authenticated;

-- Self-readable identity/role metadata can be exposed safely if a future UI needs it.
grant select on public.users, public.user_roles, public.roles to authenticated;

drop policy if exists "applyai users read self" on public.users;
create policy "applyai users read self"
on public.users for select
to authenticated
using (id = (select public.applyai_current_user_id()));

drop policy if exists "applyai users read own roles" on public.user_roles;
create policy "applyai users read own roles"
on public.user_roles for select
to authenticated
using (user_id = (select public.applyai_current_user_id()));

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
  and (storage.foldername(name))[2] = (select public.applyai_current_user_id())::text
);

drop policy if exists "applyai resume objects insert own" on storage.objects;
create policy "applyai resume objects insert own"
on storage.objects for insert
to authenticated
with check (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select public.applyai_current_user_id())::text
);

drop policy if exists "applyai resume objects update own" on storage.objects;
create policy "applyai resume objects update own"
on storage.objects for update
to authenticated
using (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select public.applyai_current_user_id())::text
)
with check (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select public.applyai_current_user_id())::text
);

drop policy if exists "applyai resume objects delete own" on storage.objects;
create policy "applyai resume objects delete own"
on storage.objects for delete
to authenticated
using (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = 'candidate'
  and (storage.foldername(name))[2] = (select public.applyai_current_user_id())::text
);

commit;
