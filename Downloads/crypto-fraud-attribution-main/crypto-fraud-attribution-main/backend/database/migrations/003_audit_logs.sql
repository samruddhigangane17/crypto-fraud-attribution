-- ==============================================================================
-- Migration 003: Immutable Audit Logs Table
-- Idempotent: safe to run whether or not an older schema was applied.
-- Stores tamper-evident, hash-chained forensic audit logs for chain of custody.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id TEXT UNIQUE NOT NULL,
    case_id TEXT,
    event TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_source TEXT NOT NULL DEFAULT 'internal',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entry_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_case ON public.audit_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON public.audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event ON public.audit_logs(event);
