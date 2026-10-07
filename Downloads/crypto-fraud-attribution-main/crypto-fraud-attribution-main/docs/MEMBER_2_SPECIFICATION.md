# Member 2: Intelligence Engine Specification & Documentation

## Overview
**Member 2** owns the Intelligence Engine of the **Real-Time Crypto Fraud Attribution System**.

### Primary Responsibilities
1. **Known-Address Registry & Provenance**: Curated database of Exchange/VASP, Mixer, Bridge, and Flagged entities across ETH, BTC, TRX, and BSC. Strict isolation between verified sources and unverified community labels. All verified addresses are verified against official OFAC SDN releases (e.g. Treasury Release jy1934 for Sinbad.io), Etherscan Public Directory tags, and TronScan Public Name Tags with authentic historical dates.
2. **Endpoint Matching Engine**: Resolves transaction hops against the registry. Unmatched addresses are classified as `UNKNOWN` (never assumed suspicious).
3. **Live Case Assessment & Scoring (`POST /api/investigations/{id}/assess`)**: Evaluates real trace paths from Member 1's tracing engine using Decimal token amounts, datetime timestamps, and flat transaction lists, computing explainable risk scores (0–100) and separate attribution confidence ratings (0.0–1.0).
4. **Attribution Confidence Assessment**: Separate 0.0–1.0 confidence rating evaluating label provenance, hop attenuation (mathematical graph decay: $c = c_0 \times (0.85)^{\text{hop}-1}$), and fund volume continuity.
5. **Continuous Monitoring & Alert Deduplication**: Background monitoring configuration, an async background polling worker (`BackgroundMonitoringWorker`) using `asyncio.to_thread` for non-blocking provider calls, and deterministic SHA256 event-key deduplication (`investigation_id + tx_hash + alert_type + target_address`). Supports `INFO`, `WARNING`, `HIGH`, and `CRITICAL` severity tiers.
6. **ReportLab PDF Evidence Generator & Investigator Auth**: Professional, court/compliance-ready dossier generation with multi-hop ledgers, risk rationales, confidence scores, and legal disclaimers. Endpoints changing state (`/assess`, `/monitor`, `POST /registry/labels`) and report generation/downloads are protected with investigator authentication (with real Supabase JWT signature verification or development stub mode).
7. **Supabase Database & Storage Contract**: Full SQL DDL migrations (`001_initial_schema.sql` + `002_persistence_and_clusters.sql`, which together are the single canonical schema) and client adapter (`supabase_client.py` and `repository.py`) covering all 8 tables and the `evidence-reports` Supabase Storage bucket.
8. **Demo Data Isolation**: Mock data is accessible only when `ENABLE_DEMO_CASES=true` and using an explicit `DEMO-` prefix (e.g. `DEMO-INVESTIGATION-001`). Real-style case IDs (e.g. `INV-2026-9041`) must be assessed through `/assess` or return HTTP 404.

---

## Directory Structure
```
crypto-fraud-attribution/
├── pytest.ini                      # Configures pythonpath = . for pytest
├── backend/
│   ├── main.py                     # FastAPI entrypoint with dotenv, lifespan worker & CORS
│   ├── api/
│   │   ├── auth.py                 # Investigator auth with Supabase JWT & stub fallback
│   │   └── routes.py               # REST API endpoints for Member 2
│   ├── database/                   # Phase 2 Supabase coordination
│   │   ├── migrations/
│   │   │   ├── 001_initial_schema.sql # PostgreSQL DDL for tables, indexes & storage
│   │   │   └── 002_persistence_and_clusters.sql # durable case columns + wallet_clusters
│   │   ├── repository.py           # InvestigationRepository with Supabase bridge
│   │   ├── schema_contract.py      # Schema definitions
│   │   └── supabase_client.py      # Supabase REST and Storage API client
│   ├── schemas/
│   │   ├── transaction.py          # Shared schema: Decimal amounts, datetime timestamps, flat tx list
│   │   ├── attribution.py          # Address labels, categories, match results
│   │   ├── risk.py                 # Risk factors and attribution confidence models
│   │   ├── monitoring.py           # Monitoring configs, alert types (INFO, WARNING, HIGH, CRITICAL)
│   │   ├── report.py               # PDF report requests and metadata
│   │   └── assessment.py           # Live case assessment request and response
│   ├── attribution/
│   │   ├── registry.py             # Address registry with provenance & separation
│   │   ├── matcher.py              # Multi-hop endpoint matcher (marks unmapped as UNKNOWN)
│   │   └── seed_data.py            # Authentic verified labels (OFAC SDN, Etherscan, TronScan)
│   ├── scoring/
│   │   ├── risk_engine.py          # Explainable rule-based risk calculator
│   │   └── confidence_engine.py    # Attribution confidence & hop attenuation
│   ├── monitoring/
│   │   ├── alerts.py               # Alert engine with event-key deduplication
│   │   ├── scheduler.py            # Async BackgroundMonitoringWorker loop (via asyncio.to_thread)
│   │   └── service.py              # Continuous monitoring case manager
│   ├── reports/
│   │   └── pdf_generator.py        # ReportLab PDF evidence report generator
│   └── mock_data/
│       └── mock_case.py            # End-to-end 3-hop demonstration case (DEMO-INVESTIGATION-001)
├── tests/
│   ├── mock_data.py                # Shared mock test fixtures with Decimal & datetime
│   ├── test_schema.py              # Unit tests for Decimal, datetime & flat transactions
│   ├── test_health.py              # Unit tests for /health endpoint
│   ├── test_attribution.py         # Registry & matching tests
│   ├── test_risk_and_confidence.py # Risk factors & confidence tests
│   ├── test_monitoring_and_alerts.py # Monitoring, severity tiers & deduplication tests
│   ├── test_pdf_report.py          # ReportLab generation tests
│   └── test_api_endpoints.py       # FastAPI HTTP integration & access control tests
```

---

## API Endpoints Reference

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/investigations/{id}/assess` | Computes risk, confidence, endpoints, and alerts on Member 1's `TracePath` list | **Yes** (`Bearer <token>`) |
| `GET` | `/api/investigations/{id}/risk` | Returns explainable risk score and attribution confidence (404 if not found) | No (Read-only) |
| `POST` | `/api/investigations/{id}/monitor` | Configures continuous background monitoring for an investigation | **Yes** (`Bearer <token>`) |
| `GET` | `/api/investigations/{id}/alerts` | Retrieves deduplicated investigation alerts (404 if not found) | No (Read-only) |
| `POST` | `/api/investigations/{id}/report` | Generates a ReportLab PDF evidence report dossier | **Yes** (`Bearer <token>`) |
| `GET` | `/api/investigations/{id}/report` | Retrieves report metadata reference | **Yes** (`Bearer <token>`) |
| `GET` | `/api/investigations/{id}/report/download` | Direct PDF binary download | **Yes** (`Bearer <token>`) |
| `GET` | `/api/registry/labels` | Lists or searches address label registry | No (Read-only) |
| `POST` | `/api/registry/labels` | Registers new address label with data provenance fields | **Yes** (`Bearer <token>`) |
| `GET` | `/api/attribution/match` | Looks up a single address (marks unknown if not found) | No (Read-only) |
