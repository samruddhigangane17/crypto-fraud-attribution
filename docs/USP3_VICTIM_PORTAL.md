# USP 3: Victim portal (backend MVP)

Victim-facing API under `/api/victim/*` and the officer intake queue under `/api/v1/intake*`.
(The plan lists `/victim/...`; we use `/api/victim/...` so it does not clash with the `/victim` page route.)

## Flow
OTP login -> consent -> draft complaint (autosave) -> submit (declaration, CAPTCHA, rate limits)
-> acknowledgement ID -> preliminary 2-hop trace (no risk score, no alerts, no clock) -> officer intake queue
tagged "Victim-reported (unverified)" -> officer verifies -> full pipeline starts -> victim tracker updates.

## Endpoints
Victim: `POST auth/otp`, `POST auth/verify`, `GET me`, `GET support`, `GET consent-notice`, `GET validate-address`,
`POST/GET complaints`, `GET/PATCH complaints/{id}`, `POST complaints/{id}/submit`,
`POST/GET complaints/{id}/evidence`, `GET .../evidence/{file}/verify|download`,
`GET cases/{id}/status`, `GET cases/{id}/requests`, `GET notifications`, `GET privacy/access-log`.
Officer (investigator auth): `GET /api/v1/intake-queue`, `GET /api/v1/intake/{id}`, `POST .../verify`,
`POST .../reject`, `POST .../stage`, `POST .../requests`, `GET .../evidence/{file}/download`.

## Safety rules implemented
- Separate auth realm: victim JWT (`aud=victim-portal`, own secret) is rejected by investigator endpoints and vice versa.
- Phone stored only as an HMAC hash + last 4 digits. OTP stored only as an HMAC; 5 min expiry, 5 tries, single use.
- Seed-phrase / private-key / password / OTP / Aadhaar-like text is blocked (422) and never echoed, stored or logged.
- Victim responses are whitelisted: no risk, clusters, attribution, case ids, notes, alerts.
- Other victims' complaints return 404. Unverified victim cases are hidden from the open `/api/v1/cases` API.
- Rate limits: OTP, verify, drafts, filing (3/day per victim, 10/day per IP), uploads. CAPTCHA at filing.
- Evidence: type + magic-byte check, 10 MB cap, heuristic malware screen, SHA-256 (client hash compared with server hash),
  append-only versions, hash-chained custody log, per-file `verify`, `restricted` flag (no preview).
- Every officer view of victim data is logged and shown to the victim (`privacy/access-log`).

## Setup
1. Run `backend/database/migrations/004_victim_portal.sql` in the Supabase SQL editor (additive, safe to re-run).
2. Add to `.env`: `VICTIM_JWT_SECRET`, `VICTIM_PHONE_PEPPER` (random 64 hex chars each), `CAPTCHA_SECRET` (production).
   For a local demo only: `VICTIM_DEV_MODE=true` (returns the OTP in the response, skips CAPTCHA).
3. `pytest` -> 211 passed.

## Known limits (be upfront about these)
- OTP delivery is a console sender. Plug an SMS provider into `OtpSender` (`backend/victim/otp.py`) for real use.
- Malware screening is heuristic only. Put ClamAV (or a scanning service) behind `BasicScanner.scan` for production.
- Evidence files are stored on local disk (`EVIDENCE_DIR`). Move to a private Supabase Storage bucket for production.
- Rate limiting is per process. Use a shared store (e.g. Redis) when running several instances.
- Phone numbers are not stored, so SMS "your case has an update" messages need an encrypted phone column (phase 2).
  Notifications are in-app only for now.
- Retention wording in `backend/victim/content.py` is a placeholder: legal/policy must confirm before launch.
- Support-centre text must be reviewed by the team before real use.
- Phase 2 items not built: officer messaging, OCR suggestions, multilingual UI, acknowledgement PDF, DPDP erasure flow.
- The frontend victim screens are NOT included yet.
