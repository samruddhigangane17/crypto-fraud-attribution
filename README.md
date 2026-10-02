# Real-Time Crypto Fraud Attribution System

Modular investigator tool: accepts a reported suspicious wallet, traces fund movements, identifies potential exchange/VASP endpoints, calculates explainable risk indicators, monitors for new activity, and generates an evidence report.

> A labeled exchange endpoint does not prove who owns the receiving wallet. Treat outputs as observed evidence with stated limitations.

## Stack
React + TypeScript - FastAPI - Supabase (Postgres/Auth/Storage/Realtime) - NetworkX - Cytoscape.js - ReportLab - Pytest

## Module owners
| Folder | Owner |
|---|---|
| `backend/tracing/` | Member 1 |
| `backend/attribution/`, `monitoring/`, `reports/` | Member 2 |
| `frontend/`, `backend/database/`, Supabase | Member 3 |
| `backend/schemas/` | Shared - all 3 must approve changes |

## Run the backend (from repo root)
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in values
uvicorn backend.main:app --reload
# open http://localhost:8000/health
```

## Run tests (from repo root)
```bash
pytest
```

## Run the frontend
See `docs/frontend-setup.md`.

## Git rules
- Never commit to `main` directly; use your feature branch + pull request (1 reviewer).
- Never commit `.env` or any key.
- Changes in `backend/schemas/` need all 3 approvals.
- Pull `main` into your branch daily.
