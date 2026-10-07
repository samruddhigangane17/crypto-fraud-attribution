"""Supabase PostgreSQL Schema Contract for Real-Time Crypto Fraud Attribution System.

Agreed table schemas and field types coordinated with Member 3 (Phase 2):

Tables:
1. `profiles`:
   - id: uuid (PK, references auth.users)
   - role: text ('investigator', 'admin', 'analyst')
   - created_at: timestamptz

2. `investigations`:
   - id: text / uuid (PK)
   - user_id: uuid (references profiles.id)
   - chain: text ('ethereum', 'bitcoin', 'tron', 'bsc')
   - reported_address: text
   - status: text ('active', 'completed', 'monitoring', 'archived')
   - created_at: timestamptz

3. `transactions`:
   - id: uuid (PK)
   - chain: text
   - tx_hash: text
   - from_address: text
   - to_address: text
   - amount: numeric / text (precise decimal)
   - asset_symbol: text
   - timestamp: timestamptz
   - block_number: bigint
   - source: text

4. `trace_paths`:
   - id: uuid (PK)
   - investigation_id: text (references investigations.id)
   - path_data: jsonb (nodes, edges, volumes)
   - hop_count: integer
   - created_at: timestamptz

5. `address_labels`:
   - id: uuid (PK)
   - chain: text
   - address: text
   - entity_name: text
   - entity_category: text
   - source: text
   - source_url: text
   - confidence: numeric (0.0 to 1.0)
   - verification_status: text ('verified', 'unverified_community', 'heuristic_cluster')
   - verified_at: timestamptz
   - notes: text

6. `risk_assessments`:
   - id: uuid (PK)
   - investigation_id: text (references investigations.id)
   - score: numeric (0 to 100)
   - risk_level: text ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
   - factors: jsonb
   - confidence: numeric (0.0 to 1.0)
   - created_at: timestamptz

7. `alerts`:
   - id: uuid (PK)
   - investigation_id: text (references investigations.id)
   - event_key: text (unique deduplication hash)
   - alert_type: text
   - severity: text ('INFO', 'WARNING', 'HIGH', 'CRITICAL')
   - title: text
   - message: text
   - target_address: text
   - tx_hash: text
   - status: text ('NEW', 'READ', 'DISMISSED')
   - created_at: timestamptz

8. `evidence_reports`:
   - id: uuid (PK)
   - investigation_id: text (references investigations.id)
   - report_id: text
   - storage_path: text (path in Supabase Storage bucket 'evidence-reports')
   - file_size_bytes: bigint
   - created_at: timestamptz

9. `audit_logs`:
   - id: uuid (PK)
   - event_id: text (unique)
   - case_id: text (optional case identifier)
   - event: text
   - actor: text ('system' or user identifier)
   - parameters: jsonb
   - data_source: text
   - timestamp: timestamptz
   - entry_hash: text (SHA-256 tamper-evident chain link)
   - created_at: timestamptz
"""

SUPABASE_BUCKET_REPORTS = "evidence-reports"
