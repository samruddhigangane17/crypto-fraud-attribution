-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. profiles
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'investigator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own profile" ON profiles FOR SELECT USING (auth.uid() = id);

-- 2. investigations
CREATE TABLE investigations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    chain TEXT NOT NULL,
    reported_address TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Reported',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view investigations" ON investigations FOR SELECT USING (auth.uid() = user_id OR auth.uid() IS NOT NULL);
CREATE POLICY "Users can insert investigations" ON investigations FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update investigations" ON investigations FOR UPDATE USING (auth.uid() = user_id OR auth.uid() IS NOT NULL);

-- 3. transactions
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain TEXT NOT NULL,
    tx_hash TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    UNIQUE(chain, tx_hash)
);

ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read transactions" ON transactions FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can insert transactions" ON transactions FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- 4. trace_paths
CREATE TABLE trace_paths (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    path_data JSONB NOT NULL,
    hop_count INTEGER NOT NULL
);

ALTER TABLE trace_paths ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read trace_paths" ON trace_paths FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can insert trace_paths" ON trace_paths FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- 5. address_labels
CREATE TABLE address_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain TEXT NOT NULL,
    address TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence TEXT NOT NULL,
    verified_at TIMESTAMPTZ,
    UNIQUE(chain, address)
);

ALTER TABLE address_labels ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read address_labels" ON address_labels FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can insert address_labels" ON address_labels FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- 6. wallet_clusters
CREATE TABLE wallet_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    cluster_data JSONB NOT NULL,
    evidence JSONB NOT NULL
);

ALTER TABLE wallet_clusters ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read wallet_clusters" ON wallet_clusters FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can insert wallet_clusters" ON wallet_clusters FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- 7. risk_assessments
CREATE TABLE risk_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    factors JSONB NOT NULL,
    confidence TEXT NOT NULL
);

ALTER TABLE risk_assessments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read risk_assessments" ON risk_assessments FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can insert risk_assessments" ON risk_assessments FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- 8. alerts
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unread'
);

ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read alerts" ON alerts FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can insert alerts" ON alerts FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can update alerts" ON alerts FOR UPDATE USING (auth.uid() IS NOT NULL);

-- 9. evidence_reports
CREATE TABLE evidence_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE evidence_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read evidence_reports" ON evidence_reports FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated users can insert evidence_reports" ON evidence_reports FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);
