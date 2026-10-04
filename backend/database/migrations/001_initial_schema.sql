-- ==============================================================================
-- Migration 001: Initial Database Schema & Supabase Storage for Member 2 & 3
-- Coordinated table definitions and RLS policies
-- ==============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Profiles (Investigator profiles linked to Supabase Auth)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'investigator' CHECK (role IN ('investigator', 'lead_investigator', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Investigations
CREATE TABLE IF NOT EXISTS public.investigations (
    id TEXT PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    chain TEXT NOT NULL,
    reported_address TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'monitoring', 'archived')),
    time_window_start TIMESTAMPTZ,
    time_window_end TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Transactions (Normalized multi-chain records)
CREATE TABLE IF NOT EXISTS public.transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain TEXT NOT NULL,
    tx_hash TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    asset_symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    block_number BIGINT,
    source TEXT NOT NULL DEFAULT 'blockchain_api',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_chain_tx_hash UNIQUE (chain, tx_hash)
);

-- 4. Trace Paths
CREATE TABLE IF NOT EXISTS public.trace_paths (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id TEXT NOT NULL REFERENCES public.investigations(id) ON DELETE CASCADE,
    chain TEXT NOT NULL,
    start_address TEXT NOT NULL,
    end_address TEXT NOT NULL,
    hop_count INTEGER NOT NULL,
    path_data JSONB NOT NULL,
    total_volume NUMERIC NOT NULL DEFAULT 0,
    is_terminal_endpoint BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Address Labels & Provenance Registry
CREATE TABLE IF NOT EXISTS public.address_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain TEXT NOT NULL,
    address TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_category TEXT NOT NULL CHECK (entity_category IN (
        'exchange_vasp', 'mixer', 'bridge', 'defi_protocol',
        'scam_fraud', 'sanctioned', 'high_risk', 'merchant_payment', 'unknown'
    )),
    source TEXT NOT NULL,
    source_url TEXT,
    confidence NUMERIC NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    verification_status TEXT NOT NULL CHECK (verification_status IN ('verified', 'unverified_community', 'heuristic_cluster')),
    verified_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_chain_address UNIQUE (chain, address)
);

-- 6. Risk Assessments
CREATE TABLE IF NOT EXISTS public.risk_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id TEXT NOT NULL REFERENCES public.investigations(id) ON DELETE CASCADE,
    overall_score NUMERIC NOT NULL CHECK (overall_score >= 0.0 AND overall_score <= 100.0),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    factors JSONB NOT NULL,
    summary_rationale TEXT,
    confidence_score NUMERIC CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Alerts
CREATE TABLE IF NOT EXISTS public.alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id TEXT NOT NULL REFERENCES public.investigations(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL UNIQUE,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'HIGH', 'CRITICAL')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    target_address TEXT NOT NULL,
    tx_hash TEXT,
    hop_number INTEGER,
    metadata JSONB,
    status TEXT NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW', 'READ', 'DISMISSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Evidence Reports
CREATE TABLE IF NOT EXISTS public.evidence_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id TEXT NOT NULL REFERENCES public.investigations(id) ON DELETE CASCADE,
    report_id TEXT NOT NULL UNIQUE,
    storage_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create Indexes for fast querying
CREATE INDEX IF NOT EXISTS idx_investigations_user ON public.investigations(user_id);
CREATE INDEX IF NOT EXISTS idx_tx_from_to ON public.transactions(chain, from_address, to_address);
CREATE INDEX IF NOT EXISTS idx_address_labels_lookup ON public.address_labels(chain, address);
CREATE INDEX IF NOT EXISTS idx_alerts_case ON public.alerts(investigation_id);

-- Storage Bucket Setup for PDF Reports
INSERT INTO storage.buckets (id, name, public)
VALUES ('evidence-reports', 'evidence-reports', FALSE)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: Only authenticated users can read/write evidence reports
CREATE POLICY "Authorized investigators can view evidence reports"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'evidence-reports');

CREATE POLICY "Authorized investigators can upload evidence reports"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'evidence-reports');
