-- ==============================================================================
-- Migration 004: Victim portal (USP 3)
-- Additive and idempotent: safe to run on the live project (no DROP, no data loss).
--
-- SECURITY MODEL: victims sign in through the backend's own OTP realm (not Supabase Auth),
-- and the backend reads/writes these tables with the service-role key. RLS is therefore
-- enabled with NO policies for anon/authenticated users, which denies all direct access
-- from the browser. Per-victim isolation is enforced in the API (ownership checks).
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.victims (
    id UUID PRIMARY KEY,
    phone_hash TEXT UNIQUE NOT NULL,          -- HMAC of the phone number; never the number itself
    phone_last4 TEXT,
    display_name TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.victim_consents (
    id UUID PRIMARY KEY,
    victim_id UUID NOT NULL REFERENCES public.victims(id) ON DELETE CASCADE,
    notice_version TEXT NOT NULL,
    purpose_text TEXT,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.complaints (
    id UUID PRIMARY KEY,
    ack_id TEXT UNIQUE,
    victim_id UUID NOT NULL REFERENCES public.victims(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft',            -- draft | submitted
    lifecycle TEXT NOT NULL DEFAULT 'draft',         -- draft|received|verified|in_progress|with_officer|action_taken|closed
    verification TEXT NOT NULL DEFAULT 'unverified', -- unverified | verified | rejected
    verified_by TEXT,
    rejected_reason TEXT,
    fraud_type TEXT,
    incident_time TIMESTAMPTZ,
    amount_lost NUMERIC,
    asset TEXT,
    payment_method TEXT,
    scammer_wallet TEXT,
    chain TEXT,
    tx_hash TEXT,
    platform TEXT,
    platform_detail TEXT,
    story TEXT,
    declaration_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    case_id TEXT,                                    -- internal; never returned to victims
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_complaints_victim ON public.complaints(victim_id);
CREATE INDEX IF NOT EXISTS idx_complaints_wallet ON public.complaints(chain, scammer_wallet);
CREATE INDEX IF NOT EXISTS idx_complaints_case ON public.complaints(case_id);

CREATE TABLE IF NOT EXISTS public.victim_case_link (
    id UUID PRIMARY KEY,
    victim_id UUID NOT NULL REFERENCES public.victims(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    complaint_id UUID REFERENCES public.complaints(id) ON DELETE CASCADE,
    consent_scope TEXT NOT NULL DEFAULT 'status_only',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_victim_case_link_case ON public.victim_case_link(case_id);

-- One row per file VERSION. Replacing a file adds a row; rows are never updated or deleted.
CREATE TABLE IF NOT EXISTS public.evidence_files (
    id UUID PRIMARY KEY,
    file_id UUID NOT NULL,
    complaint_id UUID NOT NULL REFERENCES public.complaints(id) ON DELETE CASCADE,
    version INT NOT NULL,
    filename TEXT NOT NULL,
    mime TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    restricted BOOLEAN NOT NULL DEFAULT FALSE,
    blob_path TEXT NOT NULL,
    supersedes UUID,
    uploaded_by TEXT,
    request_id TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (file_id, version)
);
CREATE INDEX IF NOT EXISTS idx_evidence_complaint ON public.evidence_files(complaint_id);

-- Hash-chained custody log (each entry commits to the previous entry's hash).
CREATE TABLE IF NOT EXISTS public.evidence_custody_log (
    id UUID PRIMARY KEY,
    file_id UUID NOT NULL,
    version INT NOT NULL,
    event TEXT NOT NULL,
    actor TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_custody_file ON public.evidence_custody_log(file_id);

CREATE TABLE IF NOT EXISTS public.case_messages (
    id UUID PRIMARY KEY,
    complaint_id UUID NOT NULL REFERENCES public.complaints(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'request',            -- request (officer asks) | message (phase 2)
    sender TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',             -- open | answered
    officer_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY,
    victim_id UUID NOT NULL REFERENCES public.victims(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES public.complaints(id) ON DELETE CASCADE,
    message TEXT NOT NULL DEFAULT 'Your case has an update',
    read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.pii_access_log (
    id UUID PRIMARY KEY,
    victim_id UUID NOT NULL REFERENCES public.victims(id) ON DELETE CASCADE,
    complaint_id UUID,
    accessor_role TEXT NOT NULL,
    accessor_ref TEXT NOT NULL,
    action TEXT NOT NULL,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pii_access_victim ON public.pii_access_log(victim_id);

-- Deny all direct (anon / authenticated) access. The backend uses the service-role key.
ALTER TABLE public.victims              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.victim_consents      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.complaints           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.victim_case_link     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_files       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_custody_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_messages        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pii_access_log       ENABLE ROW LEVEL SECURITY;
