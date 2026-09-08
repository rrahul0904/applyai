BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 8f21ae7d52d5

CREATE TABLE companies (
    id UUID NOT NULL, 
    canonical_name VARCHAR(240) NOT NULL, 
    normalized_name VARCHAR(240) NOT NULL, 
    website_url TEXT, 
    description TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (normalized_name)
);

CREATE TABLE employer_organizations (
    id UUID NOT NULL, 
    name VARCHAR(240) NOT NULL, 
    slug VARCHAR(180) NOT NULL, 
    verification_status VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (slug)
);

CREATE TABLE job_sources (
    id UUID NOT NULL, 
    connector_key VARCHAR(80) NOT NULL, 
    external_job_id VARCHAR(255) NOT NULL, 
    source_url TEXT NOT NULL, 
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    checkpoint JSONB, 
    PRIMARY KEY (id), 
    UNIQUE (connector_key, external_job_id)
);

CREATE TABLE users (
    id UUID NOT NULL, 
    clerk_user_id VARCHAR(128) NOT NULL, 
    email VARCHAR(320) NOT NULL, 
    first_name VARCHAR(120), 
    last_name VARCHAR(120), 
    avatar_url TEXT, 
    account_status VARCHAR(32) NOT NULL, 
    onboarding_completed BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (clerk_user_id)
);

CREATE TABLE candidate_preferences (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    location_text VARCHAR(240), 
    work_modes JSONB NOT NULL, 
    employment_types JSONB NOT NULL, 
    minimum_compensation INTEGER, 
    currency VARCHAR(3) NOT NULL, 
    relocation_open BOOLEAN NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (user_id)
);

CREATE TABLE candidate_profiles (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    headline VARCHAR(240), 
    summary TEXT, 
    years_experience INTEGER, 
    discoverable BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (user_id)
);

CREATE TABLE candidate_target_roles (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    title VARCHAR(240) NOT NULL, 
    normalized_title VARCHAR(240) NOT NULL, 
    priority INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (user_id, normalized_title)
);

CREATE TABLE company_aliases (
    id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    alias VARCHAR(240) NOT NULL, 
    normalized_alias VARCHAR(240) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    UNIQUE (company_id, normalized_alias)
);

CREATE TABLE company_sources (
    id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    source_name VARCHAR(80) NOT NULL, 
    external_company_id VARCHAR(255) NOT NULL, 
    source_url TEXT, 
    last_seen_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    UNIQUE (source_name, external_company_id)
);

CREATE TABLE jobs (
    id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    title VARCHAR(280) NOT NULL, 
    normalized_title VARCHAR(280) NOT NULL, 
    description TEXT NOT NULL, 
    employment_type VARCHAR(48), 
    seniority VARCHAR(48), 
    status VARCHAR(32) NOT NULL, 
    posted_at TIMESTAMP WITH TIME ZONE, 
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    closed_at TIMESTAMP WITH TIME ZONE, 
    dedup_confidence NUMERIC(5, 4), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
);

CREATE INDEX ix_jobs_company_id ON jobs (company_id);

CREATE INDEX ix_jobs_search ON jobs (normalized_title, status, posted_at);

CREATE TABLE notifications (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    notification_type VARCHAR(80) NOT NULL, 
    payload JSONB NOT NULL, 
    read_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE organization_members (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES employer_organizations (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (organization_id, user_id)
);

CREATE TABLE raw_job_postings (
    id UUID NOT NULL, 
    job_source_id UUID NOT NULL, 
    payload JSONB NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    normalization_status VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_source_id) REFERENCES job_sources (id) ON DELETE CASCADE, 
    UNIQUE (job_source_id, content_hash)
);

CREATE TABLE resumes (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    name VARCHAR(240) NOT NULL, 
    is_master BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_resumes_user_id ON resumes (user_id);

CREATE TABLE applications (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    current_status VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE RESTRICT, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (user_id, job_id)
);

CREATE INDEX ix_applications_user_id ON applications (user_id);

CREATE TABLE candidate_education (
    id UUID NOT NULL, 
    profile_id UUID NOT NULL, 
    institution VARCHAR(240) NOT NULL, 
    degree VARCHAR(240), 
    field_of_study VARCHAR(240), 
    start_date DATE, 
    end_date DATE, 
    provenance VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(profile_id) REFERENCES candidate_profiles (id) ON DELETE CASCADE
);

CREATE TABLE candidate_experiences (
    id UUID NOT NULL, 
    profile_id UUID NOT NULL, 
    company_name VARCHAR(240) NOT NULL, 
    title VARCHAR(240) NOT NULL, 
    start_date DATE, 
    end_date DATE, 
    description TEXT, 
    provenance VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(profile_id) REFERENCES candidate_profiles (id) ON DELETE CASCADE
);

CREATE TABLE candidate_skills (
    id UUID NOT NULL, 
    profile_id UUID NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    normalized_name VARCHAR(160) NOT NULL, 
    proficiency VARCHAR(32), 
    provenance VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(profile_id) REFERENCES candidate_profiles (id) ON DELETE CASCADE, 
    UNIQUE (profile_id, normalized_name)
);

CREATE TABLE job_compensation (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    minimum INTEGER, 
    maximum INTEGER, 
    currency VARCHAR(3) NOT NULL, 
    interval VARCHAR(24) NOT NULL, 
    provenance VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX ix_job_compensation_job_id ON job_compensation (job_id);

CREATE TABLE job_locations (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    location_text VARCHAR(280) NOT NULL, 
    city VARCHAR(120), 
    region VARCHAR(120), 
    country_code VARCHAR(2), 
    work_mode VARCHAR(32) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX ix_job_locations_job_id ON job_locations (job_id);

CREATE TABLE job_requirements (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    category VARCHAR(48) NOT NULL, 
    text TEXT NOT NULL, 
    required BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX ix_job_requirements_job_id ON job_requirements (job_id);

CREATE TABLE job_skills (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    normalized_name VARCHAR(160) NOT NULL, 
    required BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    UNIQUE (job_id, normalized_name)
);

CREATE INDEX ix_job_skills_job_id ON job_skills (job_id);

CREATE TABLE job_source_links (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    job_source_id UUID NOT NULL, 
    is_primary BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_source_id) REFERENCES job_sources (id) ON DELETE CASCADE, 
    UNIQUE (job_id, job_source_id)
);

CREATE TABLE job_status_history (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    from_status VARCHAR(32), 
    to_status VARCHAR(32) NOT NULL, 
    reason VARCHAR(120), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX ix_job_status_history_job_id ON job_status_history (job_id);

CREATE TABLE job_versions (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    version_number INTEGER NOT NULL, 
    snapshot JSONB NOT NULL, 
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    UNIQUE (job_id, version_number)
);

CREATE TABLE resume_versions (
    id UUID NOT NULL, 
    resume_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    version_number INTEGER NOT NULL, 
    filename VARCHAR(255) NOT NULL, 
    content_type VARCHAR(120) NOT NULL, 
    storage_key TEXT NOT NULL, 
    file_size BIGINT NOT NULL, 
    upload_status VARCHAR(32) NOT NULL, 
    processing_status VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(resume_id) REFERENCES resumes (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (resume_id, version_number)
);

CREATE INDEX ix_resume_versions_resume_id ON resume_versions (resume_id);

CREATE INDEX ix_resume_versions_user_id ON resume_versions (user_id);

CREATE TABLE saved_jobs (
    user_id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (user_id, job_id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE application_answers (
    id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    question TEXT NOT NULL, 
    answer TEXT NOT NULL, 
    user_verified BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_application_answers_application_id ON application_answers (application_id);

CREATE TABLE application_documents (
    id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    resume_version_id UUID, 
    document_type VARCHAR(48) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(resume_version_id) REFERENCES resume_versions (id) ON DELETE SET NULL, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_application_documents_application_id ON application_documents (application_id);

CREATE TABLE application_events (
    id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    actor_user_id UUID NOT NULL, 
    from_status VARCHAR(32), 
    to_status VARCHAR(32) NOT NULL, 
    metadata_json JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE
);

CREATE INDEX ix_application_events_application_id ON application_events (application_id);

CREATE TABLE application_notes (
    id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    body TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_application_notes_application_id ON application_notes (application_id);

CREATE TABLE interviews (
    id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    interview_type VARCHAR(48) NOT NULL, 
    scheduled_at TIMESTAMP WITH TIME ZONE, 
    notes TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_interviews_application_id ON interviews (application_id);

CREATE TABLE resume_extractions (
    id UUID NOT NULL, 
    resume_version_id UUID NOT NULL, 
    parser_version VARCHAR(64) NOT NULL, 
    extracted_text TEXT, 
    structured_data JSONB, 
    status VARCHAR(32) NOT NULL, 
    error_code VARCHAR(80), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(resume_version_id) REFERENCES resume_versions (id) ON DELETE CASCADE
);

CREATE INDEX ix_resume_extractions_resume_version_id ON resume_extractions (resume_version_id);

INSERT INTO alembic_version (version_num) VALUES ('8f21ae7d52d5') RETURNING alembic_version.version_num;

-- Running upgrade 8f21ae7d52d5 -> 0db19a1adb4d

ALTER TABLE candidate_profiles ADD COLUMN current_title VARCHAR(240);

ALTER TABLE jobs ADD COLUMN search_document TEXT DEFAULT '' NOT NULL;

ALTER TABLE jobs ADD COLUMN search_vector TSVECTOR;

ALTER TABLE jobs ADD COLUMN data_origin VARCHAR(48) DEFAULT 'DEVELOPMENT_SEED' NOT NULL;

UPDATE jobs SET search_document = concat_ws(' ', title, description), search_vector = to_tsvector('english', concat_ws(' ', title, description));

CREATE INDEX ix_jobs_search_vector ON jobs USING gin (search_vector);

ALTER TABLE users ADD COLUMN onboarding_stage VARCHAR(32) DEFAULT 'ACCOUNT_CREATED' NOT NULL;

UPDATE alembic_version SET version_num='0db19a1adb4d' WHERE alembic_version.version_num = '8f21ae7d52d5';

-- Running upgrade 0db19a1adb4d -> 7b9c4d1e2f60

WITH master_versions AS (
          SELECT
            rv.id,
            ROW_NUMBER() OVER (
              PARTITION BY r.user_id
              ORDER BY rv.created_at, rv.id
            ) AS seq
          FROM resume_versions rv
          JOIN resumes r ON r.id = rv.resume_id
          WHERE r.is_master IS TRUE
        )
        UPDATE resume_versions rv
        SET version_number = -mv.seq
        FROM master_versions mv
        WHERE rv.id = mv.id;

WITH ranked_masters AS (
          SELECT
            id,
            user_id,
            FIRST_VALUE(id) OVER (
              PARTITION BY user_id
              ORDER BY created_at, id
            ) AS canonical_id
          FROM resumes
          WHERE is_master IS TRUE
        )
        UPDATE resume_versions rv
        SET resume_id = rm.canonical_id
        FROM ranked_masters rm
        WHERE rv.resume_id = rm.id
          AND rm.id <> rm.canonical_id;

WITH ranked_masters AS (
          SELECT
            id,
            ROW_NUMBER() OVER (
              PARTITION BY user_id
              ORDER BY created_at, id
            ) AS rn
          FROM resumes
          WHERE is_master IS TRUE
        )
        DELETE FROM resumes r
        USING ranked_masters rm
        WHERE r.id = rm.id AND rm.rn > 1;

WITH renumbered AS (
          SELECT
            rv.id,
            ROW_NUMBER() OVER (
              PARTITION BY rv.resume_id
              ORDER BY rv.created_at, rv.id
            ) AS seq
          FROM resume_versions rv
          JOIN resumes r ON r.id = rv.resume_id
          WHERE r.is_master IS TRUE
        )
        UPDATE resume_versions rv
        SET version_number = rn.seq
        FROM renumbered rn
        WHERE rv.id = rn.id;

CREATE UNIQUE INDEX uq_resumes_one_master_per_user ON resumes (user_id) WHERE is_master IS TRUE;

WITH ranked AS (
          SELECT
            id,
            ROW_NUMBER() OVER (
              PARTITION BY resume_version_id, parser_version
              ORDER BY
                CASE status
                  WHEN 'COMPLETED' THEN 4
                  WHEN 'NEEDS_REVIEW' THEN 3
                  WHEN 'PROCESSING' THEN 2
                  WHEN 'FAILED' THEN 1
                  ELSE 0
                END DESC,
                created_at DESC,
                id DESC
            ) AS rn
          FROM resume_extractions
        )
        DELETE FROM resume_extractions re
        USING ranked r
        WHERE re.id = r.id AND r.rn > 1;

CREATE UNIQUE INDEX uq_resume_extractions_version_parser ON resume_extractions (resume_version_id, parser_version);

CREATE TABLE task_outbox (
    id UUID NOT NULL, 
    event_type VARCHAR(80) NOT NULL, 
    aggregate_type VARCHAR(80) NOT NULL, 
    aggregate_id UUID NOT NULL, 
    payload JSONB NOT NULL, 
    idempotency_key VARCHAR(255) NOT NULL, 
    status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
    attempt_count INTEGER DEFAULT '0' NOT NULL, 
    available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    locked_at TIMESTAMP WITH TIME ZONE, 
    lock_owner VARCHAR(160), 
    published_at TIMESTAMP WITH TIME ZONE, 
    last_error TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (idempotency_key)
);

CREATE INDEX ix_task_outbox_aggregate_id ON task_outbox (aggregate_id);

CREATE INDEX ix_task_outbox_available_at ON task_outbox (available_at);

CREATE INDEX ix_task_outbox_status ON task_outbox (status);

CREATE INDEX ix_task_outbox_claim ON task_outbox (status, available_at, created_at);

CREATE TABLE resume_processing_attempts (
    id UUID NOT NULL, 
    resume_version_id UUID NOT NULL, 
    parser_version VARCHAR(64) NOT NULL, 
    attempt_number INTEGER NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    error_code VARCHAR(80), 
    PRIMARY KEY (id), 
    FOREIGN KEY(resume_version_id) REFERENCES resume_versions (id) ON DELETE CASCADE, 
    CONSTRAINT uq_resume_processing_attempt UNIQUE (resume_version_id, parser_version, attempt_number)
);

CREATE INDEX ix_resume_processing_attempts_resume_version_id ON resume_processing_attempts (resume_version_id);

CREATE TABLE job_ingestion_runs (
    id UUID NOT NULL, 
    connector VARCHAR(80) NOT NULL, 
    source_company VARCHAR(255) NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    status VARCHAR(32) DEFAULT 'RUNNING' NOT NULL, 
    fetched INTEGER DEFAULT '0' NOT NULL, 
    created INTEGER DEFAULT '0' NOT NULL, 
    updated INTEGER DEFAULT '0' NOT NULL, 
    unchanged INTEGER DEFAULT '0' NOT NULL, 
    failed INTEGER DEFAULT '0' NOT NULL, 
    stale INTEGER DEFAULT '0' NOT NULL, 
    closed INTEGER DEFAULT '0' NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_job_ingestion_runs_connector ON job_ingestion_runs (connector);

CREATE INDEX ix_job_ingestion_runs_source_company ON job_ingestion_runs (source_company);

CREATE INDEX ix_applications_user_updated_id ON applications (user_id, updated_at, id);

CREATE INDEX ix_job_source_links_job_source_id ON job_source_links (job_source_id);

CREATE OR REPLACE FUNCTION applyai_refresh_job_search_vector()
        RETURNS trigger AS $$
        BEGIN
          NEW.search_document := concat_ws(' ', NEW.title, NEW.description);
          NEW.search_vector := to_tsvector('english', coalesce(NEW.search_document, ''));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;;

CREATE TRIGGER trg_applyai_refresh_job_search_vector
        BEFORE INSERT OR UPDATE OF title, description ON jobs
        FOR EACH ROW EXECUTE FUNCTION applyai_refresh_job_search_vector();;

UPDATE jobs SET search_document = concat_ws(' ', title, description), search_vector = to_tsvector('english', concat_ws(' ', title, description));

UPDATE alembic_version SET version_num='7b9c4d1e2f60' WHERE alembic_version.version_num = '0db19a1adb4d';

-- Running upgrade 7b9c4d1e2f60 -> 8c4e91a7b2d3

CREATE TABLE resume_upload_intents (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    resume_id UUID NOT NULL, 
    resume_version_id UUID NOT NULL, 
    filename VARCHAR(255) NOT NULL, 
    content_type VARCHAR(120) NOT NULL, 
    file_size INTEGER NOT NULL, 
    storage_key TEXT NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(resume_id) REFERENCES resumes (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (resume_version_id), 
    UNIQUE (storage_key)
);

CREATE INDEX ix_resume_upload_intents_resume_id ON resume_upload_intents (resume_id);

CREATE INDEX ix_resume_upload_intents_status ON resume_upload_intents (status);

CREATE INDEX ix_resume_upload_intents_user_id ON resume_upload_intents (user_id);

CREATE INDEX ix_resume_upload_intents_user_status ON resume_upload_intents (user_id, status, created_at);

UPDATE alembic_version SET version_num='8c4e91a7b2d3' WHERE alembic_version.version_num = '7b9c4d1e2f60';

-- Running upgrade 8c4e91a7b2d3 -> 9d6f2a1c4b70

CREATE TABLE job_source_registry (
    id UUID NOT NULL, 
    company_id UUID, 
    source_type VARCHAR(48) NOT NULL, 
    source_name VARCHAR(160) NOT NULL, 
    source_identity VARCHAR(255) NOT NULL, 
    base_url TEXT, 
    careers_url TEXT, 
    configuration JSONB DEFAULT '{}'::jsonb NOT NULL, 
    trust_level VARCHAR(48) DEFAULT 'OFFICIAL_ATS' NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    crawl_allowed BOOLEAN DEFAULT true NOT NULL, 
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_attempt_at TIMESTAMP WITH TIME ZONE, 
    last_success_at TIMESTAMP WITH TIME ZONE, 
    last_failure_at TIMESTAMP WITH TIME ZONE, 
    last_job_count INTEGER DEFAULT '0' NOT NULL, 
    health_status VARCHAR(32) DEFAULT 'HEALTHY' NOT NULL, 
    consecutive_failures INTEGER DEFAULT '0' NOT NULL, 
    last_error_category VARCHAR(48), 
    last_error_summary TEXT, 
    crawl_interval_seconds INTEGER DEFAULT '21600' NOT NULL, 
    next_run_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    locked_at TIMESTAMP WITH TIME ZONE, 
    locked_by VARCHAR(160), 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
    CONSTRAINT uq_job_source_registry_identity UNIQUE (source_type, source_identity)
);

CREATE INDEX ix_job_source_registry_company_id ON job_source_registry (company_id);

CREATE INDEX ix_job_source_registry_due ON job_source_registry (enabled, next_run_at, health_status);

CREATE INDEX ix_job_source_registry_lease ON job_source_registry (lease_expires_at, locked_at);

ALTER TABLE job_ingestion_runs ADD COLUMN source_id UUID;

ALTER TABLE job_ingestion_runs ADD COLUMN source_type VARCHAR(48);

ALTER TABLE job_ingestion_runs ADD COLUMN duration_ms INTEGER;

ALTER TABLE job_ingestion_runs ADD COLUMN valid INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE job_ingestion_runs ADD COLUMN invalid INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE job_ingestion_runs ADD COLUMN deduplicated INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE job_ingestion_runs ADD COLUMN error_category VARCHAR(48);

ALTER TABLE job_ingestion_runs ADD COLUMN error_summary TEXT;

ALTER TABLE job_ingestion_runs ADD CONSTRAINT fk_job_ingestion_runs_source_id FOREIGN KEY(source_id) REFERENCES job_source_registry (id) ON DELETE SET NULL;

CREATE INDEX ix_job_ingestion_runs_source_id ON job_ingestion_runs (source_id);

CREATE INDEX ix_job_ingestion_runs_source_type ON job_ingestion_runs (source_type);

CREATE INDEX ix_job_ingestion_runs_source_started ON job_ingestion_runs (source_id, started_at);

UPDATE alembic_version SET version_num='9d6f2a1c4b70' WHERE alembic_version.version_num = '8c4e91a7b2d3';

-- Running upgrade 9d6f2a1c4b70 -> a1e7c9d4f280

CREATE TABLE job_source_discoveries (
    id UUID NOT NULL, 
    user_id UUID, 
    company_id UUID, 
    source_registry_id UUID, 
    job_id UUID, 
    request_key VARCHAR(128) NOT NULL, 
    input_url TEXT NOT NULL, 
    input_domain VARCHAR(255) NOT NULL, 
    discovered_careers_url TEXT, 
    discovered_url TEXT, 
    resolved_url TEXT, 
    canonical_url TEXT, 
    apply_url TEXT, 
    detected_provider VARCHAR(48), 
    confidence NUMERIC(5, 4), 
    status VARCHAR(32) DEFAULT 'QUEUED' NOT NULL, 
    access_policy VARCHAR(32) DEFAULT 'UNKNOWN' NOT NULL, 
    evidence JSONB DEFAULT '[]'::jsonb NOT NULL, 
    etag TEXT, 
    last_modified TEXT, 
    content_hash VARCHAR(64), 
    attempt_count INTEGER DEFAULT '0' NOT NULL, 
    error_category VARCHAR(48), 
    error_summary TEXT, 
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE SET NULL, 
    FOREIGN KEY(source_registry_id) REFERENCES job_source_registry (id) ON DELETE SET NULL, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_job_source_discoveries_request_key UNIQUE (request_key)
);

CREATE INDEX ix_job_source_discoveries_user_id ON job_source_discoveries (user_id);

CREATE INDEX ix_job_source_discoveries_company_id ON job_source_discoveries (company_id);

CREATE INDEX ix_job_source_discoveries_source_registry_id ON job_source_discoveries (source_registry_id);

CREATE INDEX ix_job_source_discoveries_job_id ON job_source_discoveries (job_id);

CREATE INDEX ix_job_source_discoveries_user_created ON job_source_discoveries (user_id, created_at);

CREATE INDEX ix_job_source_discoveries_status_created ON job_source_discoveries (status, created_at);

CREATE INDEX ix_job_source_discoveries_domain ON job_source_discoveries (input_domain, status);

UPDATE alembic_version SET version_num='a1e7c9d4f280' WHERE alembic_version.version_num = '9d6f2a1c4b70';

-- Running upgrade a1e7c9d4f280 -> b2f8d5e6a390

DROP INDEX ix_job_source_registry_due;

ALTER TABLE job_source_registry ADD COLUMN priority INTEGER DEFAULT '50' NOT NULL;

ALTER TABLE job_source_registry ADD COLUMN last_dispatch_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE job_source_registry ADD COLUMN last_change_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE job_source_registry ADD COLUMN min_interval_seconds INTEGER DEFAULT '900' NOT NULL;

ALTER TABLE job_source_registry ADD COLUMN max_interval_seconds INTEGER DEFAULT '604800' NOT NULL;

CREATE INDEX ix_job_source_registry_due ON job_source_registry (enabled, next_run_at, priority, health_status);

CREATE TABLE job_apply_url_checks (
    id UUID NOT NULL, 
    job_source_id UUID NOT NULL, 
    url TEXT NOT NULL, 
    status VARCHAR(32) DEFAULT 'UNKNOWN' NOT NULL, 
    http_status INTEGER, 
    resolved_url TEXT, 
    response_ms INTEGER, 
    error_category VARCHAR(48), 
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    next_check_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_source_id) REFERENCES job_sources (id) ON DELETE CASCADE
);

CREATE INDEX ix_job_apply_url_checks_job_source_id ON job_apply_url_checks (job_source_id);

CREATE INDEX ix_job_apply_url_checks_next_check_at ON job_apply_url_checks (next_check_at);

CREATE INDEX ix_job_apply_url_checks_due ON job_apply_url_checks (next_check_at, status);

CREATE INDEX ix_job_apply_url_checks_source_checked ON job_apply_url_checks (job_source_id, checked_at);

CREATE TABLE job_closure_evidence (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    job_source_id UUID, 
    evidence_type VARCHAR(48) NOT NULL, 
    evidence_key VARCHAR(128) NOT NULL, 
    strength VARCHAR(24) NOT NULL, 
    detail JSONB DEFAULT '{}'::jsonb NOT NULL, 
    applied BOOLEAN DEFAULT false NOT NULL, 
    observed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_source_id) REFERENCES job_sources (id) ON DELETE CASCADE, 
    CONSTRAINT uq_job_closure_evidence_identity UNIQUE (job_id, job_source_id, evidence_type, evidence_key)
);

CREATE INDEX ix_job_closure_evidence_job_id ON job_closure_evidence (job_id);

CREATE INDEX ix_job_closure_evidence_job_source_id ON job_closure_evidence (job_source_id);

CREATE INDEX ix_job_closure_evidence_job_observed ON job_closure_evidence (job_id, observed_at);

CREATE TABLE job_field_provenance (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    field_name VARCHAR(64) NOT NULL, 
    job_source_link_id UUID NOT NULL, 
    value_hash VARCHAR(64) NOT NULL, 
    selection_reason VARCHAR(120) NOT NULL, 
    selected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_source_link_id) REFERENCES job_source_links (id) ON DELETE CASCADE, 
    CONSTRAINT uq_job_field_provenance_field UNIQUE (job_id, field_name)
);

CREATE INDEX ix_job_field_provenance_job_id ON job_field_provenance (job_id);

CREATE INDEX ix_job_field_provenance_source_link ON job_field_provenance (job_source_link_id);

CREATE TABLE ingestion_cost_observations (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    source_id UUID, 
    worker_seconds NUMERIC(12, 4) NOT NULL, 
    network_bytes INTEGER DEFAULT '0' NOT NULL, 
    source_postings INTEGER DEFAULT '0' NOT NULL, 
    canonical_changes INTEGER DEFAULT '0' NOT NULL, 
    estimated_cost_usd NUMERIC(12, 6), 
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES job_ingestion_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(source_id) REFERENCES job_source_registry (id) ON DELETE SET NULL, 
    CONSTRAINT uq_ingestion_cost_observation_run UNIQUE (run_id)
);

CREATE INDEX ix_ingestion_cost_observations_source_recorded ON ingestion_cost_observations (source_id, recorded_at);

UPDATE alembic_version SET version_num='b2f8d5e6a390' WHERE alembic_version.version_num = 'a1e7c9d4f280';

-- Running upgrade b2f8d5e6a390 -> c3a7e9f1b420

CREATE TABLE ai_job_runs (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID, 
    application_id UUID, 
    task_type VARCHAR(64) NOT NULL, 
    provider VARCHAR(48) NOT NULL, 
    model VARCHAR(120) NOT NULL, 
    prompt_version VARCHAR(80) NOT NULL, 
    schema_version VARCHAR(80) NOT NULL, 
    input_hash VARCHAR(64) NOT NULL, 
    idempotency_key VARCHAR(255) NOT NULL, 
    status VARCHAR(32) DEFAULT 'QUEUED' NOT NULL, 
    input_json JSONB NOT NULL, 
    output_json JSONB, 
    evidence_refs JSONB DEFAULT '[]' NOT NULL, 
    attempt_count INTEGER DEFAULT '0' NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    latency_ms INTEGER, 
    input_tokens INTEGER, 
    output_tokens INTEGER, 
    estimated_cost_usd NUMERIC(12, 6), 
    error_code VARCHAR(80), 
    error_summary TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_ai_job_runs_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX ix_ai_job_runs_user_id ON ai_job_runs (user_id);

CREATE INDEX ix_ai_job_runs_job_id ON ai_job_runs (job_id);

CREATE INDEX ix_ai_job_runs_application_id ON ai_job_runs (application_id);

CREATE INDEX ix_ai_job_runs_task_type ON ai_job_runs (task_type);

CREATE INDEX ix_ai_job_runs_status ON ai_job_runs (status);

CREATE INDEX ix_ai_job_runs_user_created ON ai_job_runs (user_id, created_at);

CREATE INDEX ix_ai_job_runs_status_created ON ai_job_runs (status, created_at);

CREATE TABLE ai_artifacts (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID, 
    application_id UUID, 
    artifact_type VARCHAR(64) NOT NULL, 
    status VARCHAR(32) DEFAULT 'DRAFT' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    content_json JSONB NOT NULL, 
    evidence_json JSONB DEFAULT '{}' NOT NULL, 
    candidate_verified BOOLEAN DEFAULT false NOT NULL, 
    superseded_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES ai_job_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_ai_artifacts_run_type UNIQUE (run_id, artifact_type)
);

CREATE INDEX ix_ai_artifacts_run_id ON ai_artifacts (run_id);

CREATE INDEX ix_ai_artifacts_user_id ON ai_artifacts (user_id);

CREATE INDEX ix_ai_artifacts_job_id ON ai_artifacts (job_id);

CREATE INDEX ix_ai_artifacts_application_id ON ai_artifacts (application_id);

CREATE INDEX ix_ai_artifacts_user_job_type ON ai_artifacts (user_id, job_id, artifact_type);

CREATE TABLE career_matches (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    model_run_id UUID, 
    engine_version VARCHAR(80) NOT NULL, 
    deterministic_score INTEGER NOT NULL, 
    ai_score INTEGER, 
    final_score INTEGER NOT NULL, 
    fit_band VARCHAR(32) NOT NULL, 
    decision VARCHAR(32) NOT NULL, 
    confidence VARCHAR(32) NOT NULL, 
    factors_json JSONB DEFAULT '[]' NOT NULL, 
    evidence_json JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(model_run_id) REFERENCES ai_job_runs (id) ON DELETE SET NULL, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_career_matches_engine UNIQUE (user_id, job_id, engine_version)
);

CREATE INDEX ix_career_matches_user_id ON career_matches (user_id);

CREATE INDEX ix_career_matches_job_id ON career_matches (job_id);

CREATE INDEX ix_career_matches_user_score ON career_matches (user_id, final_score);

CREATE TABLE resume_tailorings (
    id UUID NOT NULL, 
    artifact_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    application_id UUID, 
    safety_policy VARCHAR(48) DEFAULT 'EVIDENCE_LOCKED' NOT NULL, 
    status VARCHAR(32) DEFAULT 'NEEDS_REVIEW' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(artifact_id) REFERENCES ai_artifacts (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_resume_tailorings_artifact UNIQUE (artifact_id)
);

CREATE INDEX ix_resume_tailorings_user_id ON resume_tailorings (user_id);

CREATE INDEX ix_resume_tailorings_job_id ON resume_tailorings (job_id);

CREATE INDEX ix_resume_tailorings_application_id ON resume_tailorings (application_id);

CREATE INDEX ix_resume_tailorings_user_job ON resume_tailorings (user_id, job_id);

CREATE TABLE resume_tailoring_revisions (
    id UUID NOT NULL, 
    tailoring_id UUID NOT NULL, 
    position INTEGER NOT NULL, 
    original_text TEXT NOT NULL, 
    suggested_text TEXT NOT NULL, 
    reason TEXT NOT NULL, 
    evidence_refs JSONB DEFAULT '[]' NOT NULL, 
    risk_flags JSONB DEFAULT '[]' NOT NULL, 
    confidence NUMERIC(5, 4) NOT NULL, 
    candidate_decision VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
    candidate_text TEXT, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tailoring_id) REFERENCES resume_tailorings (id) ON DELETE CASCADE, 
    CONSTRAINT uq_resume_tailoring_revision_position UNIQUE (tailoring_id, position)
);

CREATE INDEX ix_resume_tailoring_revisions_tailoring_id ON resume_tailoring_revisions (tailoring_id);

CREATE TABLE cover_letters (
    id UUID NOT NULL, 
    artifact_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    application_id UUID, 
    body TEXT NOT NULL, 
    evidence_refs JSONB DEFAULT '[]' NOT NULL, 
    candidate_verified BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(artifact_id) REFERENCES ai_artifacts (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_cover_letters_artifact UNIQUE (artifact_id)
);

CREATE INDEX ix_cover_letters_user_id ON cover_letters (user_id);

CREATE INDEX ix_cover_letters_job_id ON cover_letters (job_id);

CREATE INDEX ix_cover_letters_application_id ON cover_letters (application_id);

CREATE INDEX ix_cover_letters_user_job ON cover_letters (user_id, job_id);

CREATE TABLE application_question_drafts (
    id UUID NOT NULL, 
    artifact_id UUID NOT NULL, 
    application_id UUID, 
    position INTEGER NOT NULL, 
    question TEXT NOT NULL, 
    draft TEXT NOT NULL, 
    evidence_refs JSONB DEFAULT '[]' NOT NULL, 
    candidate_verified BOOLEAN DEFAULT false NOT NULL, 
    candidate_text TEXT, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(artifact_id) REFERENCES ai_artifacts (id) ON DELETE CASCADE, 
    CONSTRAINT uq_application_question_drafts_position UNIQUE (artifact_id, position)
);

CREATE INDEX ix_application_question_drafts_artifact_id ON application_question_drafts (artifact_id);

CREATE INDEX ix_application_question_drafts_application_id ON application_question_drafts (application_id);

CREATE TABLE candidate_ai_artifact_feedback (
    id UUID NOT NULL, 
    artifact_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    action VARCHAR(32) NOT NULL, 
    metadata_json JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(artifact_id) REFERENCES ai_artifacts (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_candidate_ai_artifact_feedback_artifact_id ON candidate_ai_artifact_feedback (artifact_id);

CREATE INDEX ix_candidate_ai_artifact_feedback_user_id ON candidate_ai_artifact_feedback (user_id);

CREATE INDEX ix_candidate_ai_feedback_user_created ON candidate_ai_artifact_feedback (user_id, created_at);

UPDATE alembic_version SET version_num='c3a7e9f1b420' WHERE alembic_version.version_num = 'b2f8d5e6a390';

-- Running upgrade c3a7e9f1b420 -> d4b8f0a2c531

CREATE TABLE candidate_career_facts (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    category VARCHAR(48) NOT NULL, 
    title VARCHAR(255), 
    fact_text TEXT NOT NULL, 
    source_kind VARCHAR(48) DEFAULT 'USER' NOT NULL, 
    source_ref VARCHAR(255), 
    provenance VARCHAR(48) DEFAULT 'USER_VERIFIED' NOT NULL, 
    user_verified BOOLEAN DEFAULT true NOT NULL, 
    tags JSONB DEFAULT '[]' NOT NULL, 
    occurred_at DATE, 
    archived_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_candidate_career_facts_user_id ON candidate_career_facts (user_id);

CREATE INDEX ix_candidate_career_facts_user_category ON candidate_career_facts (user_id, category);

CREATE INDEX ix_candidate_career_facts_user_verified ON candidate_career_facts (user_id, user_verified);

UPDATE alembic_version SET version_num='d4b8f0a2c531' WHERE alembic_version.version_num = 'c3a7e9f1b420';

-- Running upgrade d4b8f0a2c531 -> e5c9a1b4d642

CREATE TABLE saved_searches (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    query JSONB DEFAULT '{}' NOT NULL, 
    alerts_enabled BOOLEAN DEFAULT true NOT NULL, 
    minimum_match_score INTEGER DEFAULT '70' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (user_id, name), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_saved_searches_user_id ON saved_searches (user_id);

CREATE TABLE notification_preferences (
    user_id UUID NOT NULL, 
    email_enabled BOOLEAN DEFAULT true NOT NULL, 
    push_enabled BOOLEAN DEFAULT true NOT NULL, 
    job_match_enabled BOOLEAN DEFAULT true NOT NULL, 
    application_reminder_enabled BOOLEAN DEFAULT true NOT NULL, 
    interview_reminder_enabled BOOLEAN DEFAULT true NOT NULL, 
    recruiter_followup_enabled BOOLEAN DEFAULT true NOT NULL, 
    quiet_hours JSONB DEFAULT '{}' NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE candidate_analytics_events (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    event_type VARCHAR(80) NOT NULL, 
    entity_type VARCHAR(48), 
    entity_id VARCHAR(128), 
    metadata_json JSONB DEFAULT '{}' NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_candidate_analytics_events_user_id ON candidate_analytics_events (user_id);

CREATE INDEX ix_candidate_analytics_user_type_time ON candidate_analytics_events (user_id, event_type, occurred_at);

CREATE TABLE candidate_contacts (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    name VARCHAR(240) NOT NULL, 
    company VARCHAR(240), 
    title VARCHAR(240), 
    email VARCHAR(320), 
    linkedin_url TEXT, 
    relationship VARCHAR(80), 
    notes TEXT, 
    last_contacted_at TIMESTAMP WITH TIME ZONE, 
    followup_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_candidate_contacts_user_id ON candidate_contacts (user_id);

CREATE INDEX ix_candidate_contacts_user_followup ON candidate_contacts (user_id, followup_at);

CREATE TABLE resume_studio_documents (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID, 
    base_resume_version_id UUID, 
    title VARCHAR(240) NOT NULL, 
    content JSONB DEFAULT '{}' NOT NULL, 
    status VARCHAR(32) DEFAULT 'DRAFT' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE SET NULL, 
    FOREIGN KEY(base_resume_version_id) REFERENCES resume_versions (id) ON DELETE SET NULL
);

CREATE INDEX ix_resume_studio_documents_user_id ON resume_studio_documents (user_id);

CREATE INDEX ix_resume_studio_user_job ON resume_studio_documents (user_id, job_id);

CREATE TABLE interview_practice_sessions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    mode VARCHAR(48) DEFAULT 'BEHAVIORAL' NOT NULL, 
    responses JSONB DEFAULT '[]' NOT NULL, 
    feedback JSONB DEFAULT '{}' NOT NULL, 
    score INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX ix_interview_practice_sessions_user_id ON interview_practice_sessions (user_id);

CREATE INDEX ix_interview_practice_user_job ON interview_practice_sessions (user_id, job_id);

CREATE TABLE subscriptions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    plan VARCHAR(48) DEFAULT 'FREE' NOT NULL, 
    status VARCHAR(32) DEFAULT 'ACTIVE' NOT NULL, 
    provider VARCHAR(48) DEFAULT 'INTERNAL' NOT NULL, 
    provider_customer_id VARCHAR(255), 
    provider_subscription_id VARCHAR(255), 
    current_period_end TIMESTAMP WITH TIME ZONE, 
    usage JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_subscriptions_user_id ON subscriptions (user_id);

CREATE TABLE billing_ledger_events (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    event_type VARCHAR(80) NOT NULL, 
    amount_cents INTEGER DEFAULT '0' NOT NULL, 
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL, 
    provider_ref VARCHAR(255), 
    metadata_json JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_billing_ledger_events_user_id ON billing_ledger_events (user_id);

CREATE TABLE application_submission_requests (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    attempt_number INTEGER DEFAULT '1' NOT NULL, 
    mode VARCHAR(48) DEFAULT 'EXTERNAL_HANDOFF' NOT NULL, 
    provider VARCHAR(80) DEFAULT 'MANUAL' NOT NULL, 
    status VARCHAR(48) DEFAULT 'DRAFT' NOT NULL, 
    target_url TEXT, 
    payload JSONB DEFAULT '{}' NOT NULL, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    submitted_at TIMESTAMP WITH TIME ZONE, 
    error_code VARCHAR(80), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (application_id, attempt_number), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE
);

CREATE INDEX ix_application_submission_requests_user_id ON application_submission_requests (user_id);

CREATE INDEX ix_application_submission_requests_application_id ON application_submission_requests (application_id);

CREATE TABLE employer_jobs (
    id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    created_by_user_id UUID NOT NULL, 
    canonical_job_id UUID, 
    title VARCHAR(280) NOT NULL, 
    description TEXT NOT NULL, 
    location_text VARCHAR(280), 
    work_mode VARCHAR(32) DEFAULT 'ONSITE' NOT NULL, 
    employment_type VARCHAR(48), 
    seniority VARCHAR(48), 
    compensation_min INTEGER, 
    compensation_max INTEGER, 
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL, 
    status VARCHAR(32) DEFAULT 'DRAFT' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES employer_organizations (id) ON DELETE CASCADE, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    UNIQUE (canonical_job_id), 
    FOREIGN KEY(canonical_job_id) REFERENCES jobs (id) ON DELETE SET NULL
);

CREATE INDEX ix_employer_jobs_organization_id ON employer_jobs (organization_id);

CREATE INDEX ix_employer_jobs_org_status ON employer_jobs (organization_id, status);

CREATE TABLE employer_applicants (
    id UUID NOT NULL, 
    employer_job_id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    stage VARCHAR(48) DEFAULT 'NEW' NOT NULL, 
    rating INTEGER, 
    notes JSONB DEFAULT '[]' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (employer_job_id, application_id), 
    FOREIGN KEY(employer_job_id) REFERENCES employer_jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE
);

CREATE INDEX ix_employer_applicants_employer_job_id ON employer_applicants (employer_job_id);

CREATE INDEX ix_employer_applicants_application_id ON employer_applicants (application_id);

UPDATE alembic_version SET version_num='e5c9a1b4d642' WHERE alembic_version.version_num = 'd4b8f0a2c531';

-- Running upgrade e5c9a1b4d642 -> f6d0b2c5e753

CREATE TABLE deleted_identities (
    id UUID NOT NULL, 
    subject_hash VARCHAR(64) NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (subject_hash)
);

UPDATE alembic_version SET version_num='f6d0b2c5e753' WHERE alembic_version.version_num = 'e5c9a1b4d642';

-- Running upgrade f6d0b2c5e753 -> g7e1c3d6f864

ALTER TABLE subscriptions DROP CONSTRAINT subscriptions_user_id_key;

DROP INDEX ix_subscriptions_user_id;

CREATE UNIQUE INDEX ix_subscriptions_user_id ON subscriptions (user_id);

UPDATE alembic_version SET version_num='g7e1c3d6f864' WHERE alembic_version.version_num = 'f6d0b2c5e753';

-- Running upgrade g7e1c3d6f864 -> h8f2d4e7a975

CREATE TABLE job_source_capabilities (
    id UUID NOT NULL, 
    provider_key VARCHAR(80) NOT NULL, 
    display_name VARCHAR(160) NOT NULL, 
    access_mode VARCHAR(48) NOT NULL, 
    implementation_status VARCHAR(48) NOT NULL, 
    official_api_available BOOLEAN NOT NULL, 
    public_feed_available BOOLEAN NOT NULL, 
    partner_feed_available BOOLEAN NOT NULL, 
    public_page_access BOOLEAN NOT NULL, 
    authentication_required BOOLEAN NOT NULL, 
    robots_policy VARCHAR(48) NOT NULL, 
    recommended_strategy TEXT NOT NULL, 
    documentation_url TEXT, 
    notes TEXT, 
    metadata_json JSONB NOT NULL, 
    reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_job_source_capabilities_provider_key UNIQUE (provider_key)
);

CREATE INDEX ix_job_source_capabilities_mode_status ON job_source_capabilities (access_mode, implementation_status);

CREATE TABLE organization_profiles (
    id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    canonical_domain VARCHAR(255), 
    organization_type VARCHAR(48) NOT NULL, 
    industry VARCHAR(160), 
    country_code VARCHAR(2), 
    state_region VARCHAR(120), 
    size_band VARCHAR(48), 
    priority INTEGER NOT NULL, 
    careers_url TEXT, 
    ats_provider VARCHAR(80), 
    source_status VARCHAR(48) NOT NULL, 
    dataset_provenance JSONB NOT NULL, 
    metadata_json JSONB NOT NULL, 
    last_verified_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    CONSTRAINT uq_organization_profiles_canonical_domain UNIQUE (canonical_domain), 
    CONSTRAINT uq_organization_profiles_company_id UNIQUE (company_id)
);

CREATE INDEX ix_organization_profiles_type_priority ON organization_profiles (organization_type, priority);

CREATE INDEX ix_organization_profiles_status_priority ON organization_profiles (source_status, priority);

CREATE INDEX ix_organization_profiles_country_region ON organization_profiles (country_code, state_region);

CREATE TABLE job_dedup_candidates (
    id UUID NOT NULL, 
    left_job_id UUID NOT NULL, 
    right_job_id UUID NOT NULL, 
    reason VARCHAR(80) NOT NULL, 
    confidence_bps INTEGER NOT NULL, 
    evidence JSONB NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(left_job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(right_job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    CONSTRAINT uq_job_dedup_candidates_pair UNIQUE (left_job_id, right_job_id)
);

CREATE INDEX ix_job_dedup_candidates_left_job_id ON job_dedup_candidates (left_job_id);

CREATE INDEX ix_job_dedup_candidates_right_job_id ON job_dedup_candidates (right_job_id);

CREATE INDEX ix_job_dedup_candidates_status_score ON job_dedup_candidates (status, confidence_bps);

UPDATE alembic_version SET version_num='h8f2d4e7a975' WHERE alembic_version.version_num = 'g7e1c3d6f864';

-- Running upgrade h8f2d4e7a975 -> i9a3e5f8b086

CREATE TABLE agent_runs (
    id UUID NOT NULL, 
    candidate_id UUID NOT NULL, 
    job_id UUID, 
    agent_name VARCHAR(80) NOT NULL, 
    agent_version VARCHAR(32) NOT NULL, 
    trigger_type VARCHAR(48) NOT NULL, 
    trigger_id VARCHAR(255), 
    workflow_type VARCHAR(80), 
    workflow_id UUID, 
    status VARCHAR(32) NOT NULL, 
    execution_class VARCHAR(16) NOT NULL, 
    queue_class VARCHAR(32) NOT NULL, 
    priority INTEGER NOT NULL, 
    idempotency_key VARCHAR(512) NOT NULL, 
    input_json JSONB NOT NULL, 
    current_step VARCHAR(120), 
    max_steps INTEGER NOT NULL, 
    timeout_seconds INTEGER NOT NULL, 
    max_cost_usd NUMERIC(12, 6) NOT NULL, 
    attempt_count INTEGER NOT NULL, 
    input_tokens INTEGER NOT NULL, 
    output_tokens INTEGER NOT NULL, 
    cost_usd NUMERIC(12, 6) NOT NULL, 
    provider VARCHAR(48), 
    model VARCHAR(120), 
    prompt_version VARCHAR(80), 
    schema_version VARCHAR(80), 
    lease_owner VARCHAR(160), 
    lease_acquired_at TIMESTAMP WITH TIME ZONE, 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    heartbeat_at TIMESTAMP WITH TIME ZONE, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    failed_at TIMESTAMP WITH TIME ZONE, 
    error_code VARCHAR(80), 
    error_detail TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    CONSTRAINT uq_agent_runs_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX ix_agent_runs_candidate_id ON agent_runs (candidate_id);

CREATE INDEX ix_agent_runs_job_id ON agent_runs (job_id);

CREATE INDEX ix_agent_runs_agent_name ON agent_runs (agent_name);

CREATE INDEX ix_agent_runs_workflow_type ON agent_runs (workflow_type);

CREATE INDEX ix_agent_runs_workflow_id ON agent_runs (workflow_id);

CREATE INDEX ix_agent_runs_status ON agent_runs (status);

CREATE INDEX ix_agent_runs_lease_expires_at ON agent_runs (lease_expires_at);

CREATE INDEX ix_agent_runs_claim ON agent_runs (status, priority, created_at);

CREATE INDEX ix_agent_runs_candidate_created ON agent_runs (candidate_id, created_at);

CREATE INDEX ix_agent_runs_agent_status ON agent_runs (agent_name, status, created_at);

CREATE TABLE agent_steps (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    position INTEGER NOT NULL, 
    step_name VARCHAR(120) NOT NULL, 
    step_version VARCHAR(32) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    attempt INTEGER NOT NULL, 
    input_ref JSONB NOT NULL, 
    output_ref JSONB NOT NULL, 
    provider VARCHAR(48), 
    model VARCHAR(120), 
    input_tokens INTEGER NOT NULL, 
    output_tokens INTEGER NOT NULL, 
    cost_usd NUMERIC(12, 6) NOT NULL, 
    error_code VARCHAR(80), 
    error_detail TEXT, 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE CASCADE, 
    CONSTRAINT uq_agent_steps_run_name_attempt UNIQUE (run_id, step_name, attempt)
);

CREATE INDEX ix_agent_steps_run_id ON agent_steps (run_id);

CREATE INDEX ix_agent_steps_run_position ON agent_steps (run_id, position);

CREATE TABLE agent_events (
    id UUID NOT NULL, 
    run_id UUID, 
    candidate_id UUID NOT NULL, 
    event_type VARCHAR(100) NOT NULL, 
    payload JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE SET NULL
);

CREATE INDEX ix_agent_events_run_id ON agent_events (run_id);

CREATE INDEX ix_agent_events_candidate_id ON agent_events (candidate_id);

CREATE INDEX ix_agent_events_event_type ON agent_events (event_type);

CREATE INDEX ix_agent_events_candidate_created ON agent_events (candidate_id, created_at);

CREATE TABLE agent_artifacts (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    candidate_id UUID NOT NULL, 
    job_id UUID, 
    artifact_type VARCHAR(80) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    version INTEGER NOT NULL, 
    content_json JSONB NOT NULL, 
    evidence_json JSONB NOT NULL, 
    parent_artifact_id UUID, 
    supersedes_artifact_id UUID, 
    prompt_version VARCHAR(80), 
    schema_version VARCHAR(80), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(parent_artifact_id) REFERENCES agent_artifacts (id) ON DELETE SET NULL, 
    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(supersedes_artifact_id) REFERENCES agent_artifacts (id) ON DELETE SET NULL, 
    CONSTRAINT uq_agent_artifacts_run_type_version UNIQUE (run_id, artifact_type, version)
);

CREATE INDEX ix_agent_artifacts_run_id ON agent_artifacts (run_id);

CREATE INDEX ix_agent_artifacts_candidate_id ON agent_artifacts (candidate_id);

CREATE INDEX ix_agent_artifacts_job_id ON agent_artifacts (job_id);

CREATE INDEX ix_agent_artifacts_artifact_type ON agent_artifacts (artifact_type);

CREATE INDEX ix_agent_artifacts_candidate_job_type ON agent_artifacts (candidate_id, job_id, artifact_type);

CREATE TABLE agent_tool_calls (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    step_id UUID, 
    candidate_id UUID NOT NULL, 
    tool_name VARCHAR(120) NOT NULL, 
    tool_version VARCHAR(32) NOT NULL, 
    execution_class VARCHAR(16) NOT NULL, 
    input_json JSONB NOT NULL, 
    output_json JSONB NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    latency_ms INTEGER, 
    error_code VARCHAR(80), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(step_id) REFERENCES agent_steps (id) ON DELETE SET NULL
);

CREATE INDEX ix_agent_tool_calls_run_id ON agent_tool_calls (run_id);

CREATE INDEX ix_agent_tool_calls_candidate_id ON agent_tool_calls (candidate_id);

CREATE INDEX ix_agent_tool_calls_run_created ON agent_tool_calls (run_id, created_at);

CREATE TABLE agent_approvals (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    candidate_id UUID NOT NULL, 
    action_type VARCHAR(100) NOT NULL, 
    artifact_id UUID, 
    status VARCHAR(24) NOT NULL, 
    policy_version VARCHAR(48) NOT NULL, 
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    rejected_at TIMESTAMP WITH TIME ZONE, 
    approved_by UUID, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(artifact_id) REFERENCES agent_artifacts (id) ON DELETE SET NULL, 
    FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_agent_approvals_run_id ON agent_approvals (run_id);

CREATE INDEX ix_agent_approvals_candidate_id ON agent_approvals (candidate_id);

CREATE INDEX ix_agent_approvals_status ON agent_approvals (status);

CREATE INDEX ix_agent_approvals_candidate_status ON agent_approvals (candidate_id, status, requested_at);

CREATE TABLE agent_cost_events (
    id UUID NOT NULL, 
    run_id UUID NOT NULL, 
    candidate_id UUID NOT NULL, 
    agent_name VARCHAR(80) NOT NULL, 
    agent_version VARCHAR(32) NOT NULL, 
    provider VARCHAR(48), 
    model VARCHAR(120), 
    input_tokens INTEGER NOT NULL, 
    output_tokens INTEGER NOT NULL, 
    cost_usd NUMERIC(12, 6) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(candidate_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_agent_cost_events_run_id ON agent_cost_events (run_id);

CREATE INDEX ix_agent_cost_events_candidate_id ON agent_cost_events (candidate_id);

CREATE INDEX ix_agent_cost_events_agent_name ON agent_cost_events (agent_name);

CREATE INDEX ix_agent_cost_events_candidate_created ON agent_cost_events (candidate_id, created_at);

CREATE TABLE agent_runtime_policies (
    id UUID NOT NULL, 
    agent_name VARCHAR(80) NOT NULL, 
    agent_version VARCHAR(32) NOT NULL, 
    enabled_override BOOLEAN, 
    max_cost_usd_override NUMERIC(12, 6), 
    paused_at TIMESTAMP WITH TIME ZONE, 
    reason VARCHAR(255), 
    updated_by VARCHAR(160), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_agent_runtime_policy_definition UNIQUE (agent_name, agent_version)
);

CREATE INDEX ix_agent_runtime_policies_agent_name ON agent_runtime_policies (agent_name);

UPDATE alembic_version SET version_num='i9a3e5f8b086' WHERE alembic_version.version_num = 'h8f2d4e7a975';

-- Running upgrade i9a3e5f8b086 -> j0b4f6a9c197

CREATE TABLE application_question_memory (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    canonical_key VARCHAR(120) NOT NULL, 
    normalized_question TEXT, 
    question_variants JSONB NOT NULL, 
    answer TEXT NOT NULL, 
    answer_type VARCHAR(32) NOT NULL, 
    confidence NUMERIC(5, 4) NOT NULL, 
    sensitive BOOLEAN NOT NULL, 
    candidate_verified BOOLEAN NOT NULL, 
    source_kind VARCHAR(48) NOT NULL, 
    source_ref VARCHAR(255), 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_application_question_memory_user_key UNIQUE (user_id, canonical_key)
);

CREATE INDEX ix_application_question_memory_user_id ON application_question_memory (user_id);

CREATE INDEX ix_application_question_memory_user_verified ON application_question_memory (user_id, candidate_verified);

CREATE TABLE application_executions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    application_copilot_artifact_id UUID, 
    attempt_number INTEGER NOT NULL, 
    approval_mode VARCHAR(32) NOT NULL, 
    ats_provider VARCHAR(80) NOT NULL, 
    target_url TEXT, 
    state VARCHAR(48) NOT NULL, 
    fields JSONB NOT NULL, 
    review_items JSONB NOT NULL, 
    missing_fields JSONB NOT NULL, 
    documents JSONB NOT NULL, 
    validation JSONB NOT NULL, 
    browser_handoff JSONB NOT NULL, 
    confirmation_url TEXT, 
    confirmation_text TEXT, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    started_at TIMESTAMP WITH TIME ZONE, 
    submitted_at TIMESTAMP WITH TIME ZONE, 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    error_code VARCHAR(80), 
    error_detail TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_copilot_artifact_id) REFERENCES ai_artifacts (id) ON DELETE SET NULL, 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_application_execution_attempt UNIQUE (application_id, attempt_number)
);

CREATE INDEX ix_application_executions_user_id ON application_executions (user_id);

CREATE INDEX ix_application_executions_application_id ON application_executions (application_id);

CREATE INDEX ix_application_executions_job_id ON application_executions (job_id);

CREATE INDEX ix_application_executions_state ON application_executions (state);

CREATE INDEX ix_application_executions_user_state ON application_executions (user_id, state, created_at);

UPDATE alembic_version SET version_num='j0b4f6a9c197' WHERE alembic_version.version_num = 'i9a3e5f8b086';

-- Running upgrade j0b4f6a9c197 -> k1c5g7b0d208

CREATE TABLE resume_share_links (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    resume_id UUID NOT NULL, 
    pinned_resume_version_id UUID, 
    job_id UUID, 
    application_id UUID, 
    public_token VARCHAR(64) NOT NULL, 
    label VARCHAR(200) NOT NULL, 
    channel VARCHAR(80), 
    always_current BOOLEAN NOT NULL, 
    allow_download BOOLEAN NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE SET NULL, 
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE SET NULL, 
    FOREIGN KEY(pinned_resume_version_id) REFERENCES resume_versions (id) ON DELETE SET NULL, 
    FOREIGN KEY(resume_id) REFERENCES resumes (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_resume_share_links_user_id ON resume_share_links (user_id);

CREATE INDEX ix_resume_share_links_resume_id ON resume_share_links (resume_id);

CREATE INDEX ix_resume_share_links_job_id ON resume_share_links (job_id);

CREATE INDEX ix_resume_share_links_application_id ON resume_share_links (application_id);

CREATE UNIQUE INDEX ix_resume_share_links_public_token ON resume_share_links (public_token);

CREATE INDEX ix_resume_share_links_user_status_created ON resume_share_links (user_id, status, created_at);

CREATE INDEX ix_resume_share_links_job_created ON resume_share_links (job_id, created_at);

CREATE INDEX ix_resume_share_links_application_created ON resume_share_links (application_id, created_at);

CREATE TABLE resume_share_events (
    id UUID NOT NULL, 
    share_id UUID NOT NULL, 
    session_hash VARCHAR(64) NOT NULL, 
    event_type VARCHAR(32) NOT NULL, 
    event_value INTEGER, 
    metadata_json JSONB NOT NULL, 
    suspected_bot BOOLEAN NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(share_id) REFERENCES resume_share_links (id) ON DELETE CASCADE
);

CREATE INDEX ix_resume_share_events_share_id ON resume_share_events (share_id);

CREATE INDEX ix_resume_share_events_share_time ON resume_share_events (share_id, occurred_at);

CREATE INDEX ix_resume_share_events_share_session ON resume_share_events (share_id, session_hash, occurred_at);

UPDATE alembic_version SET version_num='k1c5g7b0d208' WHERE alembic_version.version_num = 'j0b4f6a9c197';

-- Running upgrade k1c5g7b0d208 -> l2d6h8c1e319

CREATE TABLE postgres_tasks (
    id UUID NOT NULL, 
    task_type VARCHAR(80) NOT NULL, 
    payload JSONB NOT NULL, 
    idempotency_key VARCHAR(255) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    attempt_count INTEGER NOT NULL, 
    available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    leased_at TIMESTAMP WITH TIME ZONE, 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    lease_owner VARCHAR(160), 
    completed_at TIMESTAMP WITH TIME ZONE, 
    cancelled_at TIMESTAMP WITH TIME ZONE, 
    last_error TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_postgres_tasks_task_type ON postgres_tasks (task_type);

CREATE INDEX ix_postgres_tasks_status ON postgres_tasks (status);

CREATE INDEX ix_postgres_tasks_available_at ON postgres_tasks (available_at);

CREATE UNIQUE INDEX ix_postgres_tasks_idempotency_key ON postgres_tasks (idempotency_key);

CREATE INDEX ix_postgres_tasks_claim ON postgres_tasks (status, available_at, created_at);

CREATE INDEX ix_postgres_tasks_lease ON postgres_tasks (status, lease_expires_at);

UPDATE alembic_version SET version_num='l2d6h8c1e319' WHERE alembic_version.version_num = 'k1c5g7b0d208';

-- Running upgrade l2d6h8c1e319 -> m3e7i9c2f420

CREATE TABLE database_objects (
    key TEXT NOT NULL, 
    content_type VARCHAR(120) NOT NULL, 
    size BIGINT NOT NULL, 
    content BYTEA NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (key)
);

UPDATE alembic_version SET version_num='m3e7i9c2f420' WHERE alembic_version.version_num = 'l2d6h8c1e319';

-- Running upgrade m3e7i9c2f420 -> n4f8j0d3g531

CREATE TABLE operations_certifications (
    id UUID NOT NULL, 
    certification_type VARCHAR(80) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    environment VARCHAR(48) DEFAULT 'unknown' NOT NULL, 
    git_sha VARCHAR(64), 
    evidence JSONB DEFAULT '{}'::jsonb NOT NULL, 
    notes TEXT, 
    created_by VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_operations_certifications_certification_type ON operations_certifications (certification_type);

CREATE INDEX ix_operations_certifications_status ON operations_certifications (status);

CREATE INDEX ix_operations_certifications_created ON operations_certifications (created_at, id);

CREATE INDEX ix_operations_certifications_status_created ON operations_certifications (status, created_at);

UPDATE alembic_version SET version_num='n4f8j0d3g531' WHERE alembic_version.version_num = 'm3e7i9c2f420';

-- Running upgrade n4f8j0d3g531 -> o5g9k1d4h642

ALTER TABLE users ALTER COLUMN clerk_user_id DROP NOT NULL;

ALTER TABLE users ADD COLUMN auth_user_id UUID;

ALTER TABLE users ADD COLUMN auth_provider VARCHAR(32) DEFAULT 'clerk' NOT NULL;

CREATE UNIQUE INDEX ix_users_auth_user_id ON users (auth_user_id);

CREATE TABLE roles (
    id UUID NOT NULL, 
    name VARCHAR(32) NOT NULL, 
    description VARCHAR(240), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL, 
    role_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (user_id, role_id), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

INSERT INTO roles (id, name, description) VALUES ('00000000-0000-0000-0000-000000000001', 'candidate', 'Standard candidate workspace access');

INSERT INTO roles (id, name, description) VALUES ('00000000-0000-0000-0000-000000000002', 'operator', 'Operations control-plane access');

INSERT INTO roles (id, name, description) VALUES ('00000000-0000-0000-0000-000000000003', 'admin', 'Administrative control-plane access');

UPDATE alembic_version SET version_num='o5g9k1d4h642' WHERE alembic_version.version_num = 'n4f8j0d3g531';

COMMIT;

