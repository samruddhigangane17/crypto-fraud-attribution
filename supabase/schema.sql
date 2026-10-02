-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Clean up any partial tables so the full schema runs cleanly
DROP TABLE IF EXISTS evidence_reports CASCADE;
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS risk_assessments CASCADE;
DROP TABLE IF EXISTS wallet_clusters CASCADE;
DROP TABLE IF EXISTS address_labels CASCADE;
DROP TABLE IF EXISTS trace_paths CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS investigations CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;

-- 1. profiles
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'investigator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. investigations
CREATE TABLE investigations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    chain TEXT NOT NULL,
    reported_address TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. transactions
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain TEXT NOT NULL,
    tx_hash TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount TEXT NOT NULL,
    asset_symbol TEXT,
    timestamp TIMESTAMPTZ NOT NULL,
    block_number BIGINT,
    source TEXT
);

-- 4. trace_paths
CREATE TABLE trace_paths (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    path_data JSONB NOT NULL,
    hop_count INT NOT NULL DEFAULT 1
);

-- 5. address_labels
CREATE TABLE address_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain TEXT NOT NULL,
    address TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    source TEXT,
    confidence TEXT,
    verified_at TIMESTAMPTZ
);

-- 6. wallet_clusters
CREATE TABLE wallet_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    cluster_data JSONB NOT NULL,
    evidence TEXT
);

-- 7. risk_assessments
CREATE TABLE risk_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    score NUMERIC NOT NULL,
    factors JSONB NOT NULL,
    confidence TEXT NOT NULL
);

-- 8. alerts
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. evidence_reports
CREATE TABLE evidence_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Row Level Security (RLS) on all 9 tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trace_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE address_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallet_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_reports ENABLE ROW LEVEL SECURITY;

-- Policies for authenticated investigators
CREATE POLICY "Authenticated access profiles" ON profiles FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access investigations" ON investigations FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access transactions" ON transactions FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access trace_paths" ON trace_paths FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access address_labels" ON address_labels FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access wallet_clusters" ON wallet_clusters FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access risk_assessments" ON risk_assessments FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access alerts" ON alerts FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated access evidence_reports" ON evidence_reports FOR ALL USING (auth.uid() IS NOT NULL);

-- ==========================================
-- SUPABASE STORAGE CONFIGURATION
-- ==========================================

-- Insert the private 'reports' bucket for evidence PDFs
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('reports', 'reports', false, 52428800, ARRAY['application/pdf'])
ON CONFLICT (id) DO NOTHING;

-- Enable RLS on storage objects
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- Allow authenticated investigators to upload reports
CREATE POLICY "Investigators can upload reports" 
ON storage.objects FOR INSERT 
WITH CHECK (bucket_id = 'reports' AND auth.role() = 'authenticated');

-- Allow authenticated investigators to download/read reports
CREATE POLICY "Investigators can view reports" 
ON storage.objects FOR SELECT 
USING (bucket_id = 'reports' AND auth.role() = 'authenticated');
