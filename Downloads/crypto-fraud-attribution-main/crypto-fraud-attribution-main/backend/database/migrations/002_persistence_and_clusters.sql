-- ==============================================================================
-- Migration 002: durable case storage + wallet_clusters
-- Idempotent: safe to run whether or not an older schema was applied.
-- Canonical schema = 001 + 002 (the former supabase/schema.sql has been removed).
-- ==============================================================================

-- Columns the API now writes when persisting a traced case
ALTER TABLE public.investigations ADD COLUMN IF NOT EXISTS data_source TEXT;
ALTER TABLE public.investigations ADD COLUMN IF NOT EXISTS notice TEXT;
ALTER TABLE public.investigations ADD COLUMN IF NOT EXISTS graph_data JSONB;
ALTER TABLE public.investigations ADD COLUMN IF NOT EXISTS analysis JSONB;

-- Wallet clusters (plan table; populated once clustering heuristics are implemented)
CREATE TABLE IF NOT EXISTS public.wallet_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id TEXT NOT NULL REFERENCES public.investigations(id) ON DELETE CASCADE,
    cluster_data JSONB NOT NULL,
    evidence TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trace_paths_case ON public.trace_paths(investigation_id);
CREATE INDEX IF NOT EXISTS idx_wallet_clusters_case ON public.wallet_clusters(investigation_id);
