# Real-Time Crypto Fraud Attribution System

An investigator-ready platform for tracing suspicious cryptocurrency transactions across multiple blockchains, attributing endpoints (Exchanges, VASPs, Mixers), evaluating explainable risk factors, performing continuous monitoring, and generating court-ready PDF evidence dossiers.

---

## 3-Member Responsibilities Overview

| Team Member | Role | Core Deliverables |
| :--- | :--- | :--- |
| **Member 1** | **Core Investigation Engine** | Blockchain data connectors (ETH, BTC, TRX, BSC), transaction normalization, multi-hop traversal with NetworkX, candidate wallet clustering. |
| **Member 2** *(Active Agent)* | **Intelligence Engine** | Known-address registry with data provenance, endpoint matching, explainable risk scoring, separate attribution confidence engine, continuous monitoring & duplicate-safe alerts, ReportLab PDF evidence report generator. |
| **Member 3** | **Frontend & Application Integration** | React + TypeScript dashboard, Cytoscape.js fund-flow graph visualization, Supabase Auth/PostgreSQL/Storage, API integration. |

---

## Member 2 Module Highlights

### 1. Known-Address Registry & Provenance (`backend/attribution/`)
- Pre-seeded with verified Exchange/VASP endpoints (Binance, Coinbase, Kraken, OKX), Mixers (Tornado Cash, Wasabi CoinJoin), Bridges (FixedFloat), and Sanctioned entities across Ethereum, Bitcoin, TRON, and BSC.
- **Strict Data Isolation**: Unverified community submissions are kept strictly separate from verified regulatory/attested entries.
- Unmatched addresses are labeled as `UNKNOWN`, preserving forensic neutrality.

### 2. Explainable Risk & Separate Attribution Confidence (`backend/scoring/`)
- **Risk Assessment (0–100 scale)**:
  - *Mixer Exposure*: Obfuscation indicator with hop-distance weighting.
  - *Illicit / Sanction Proximity*: Proximity to flagged addresses.
  - *Velocity & Peeling*: Fast-cadence relay detection.
  - *Service Endpoint Destination*: Actionable cash-out identification.
  - *Data Completeness*: Audit coverage accounting.
- **Attribution Confidence Assessment (0.0–1.0 scale)**:
  - *Data Provenance & Reliability*: Evaluates source authority.
  - *Graph Hop Proximity (Hop Attenuation)*: Mathematically attenuates confidence as funds pass through intermediary wallets.
  - *Flow Continuity*: Evaluates volume preservation.

### 3. Continuous Monitoring & Alert Deduplication (`backend/monitoring/`)
- Configurable per-investigation background surveillance.
- **Deterministic Event-Key Deduplication**: `SHA256(case_id : tx_hash : alert_type : target_address)` ensures repeated polling cycles never fire duplicate alerts.

### 4. PDF Evidence Report Generator (`backend/reports/`)
- Professional ReportLab-powered PDF engine.
- Formats executive summaries, risk breakdowns, confidence assessments, multi-hop transaction ledgers, alert histories, and mandatory forensic limitations disclaimers.

---

## Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
python -m pytest tests/
```

### 3. Start Backend Server
```bash
python -m uvicorn backend.main:app --reload --port 8000
```
Interactive API docs available at: `http://localhost:8000/docs`
