# Data Contract (must be approved by all 3 members)

Status: DRAFT -> change to APPROVED once everyone signs off in the PR.

## 1. Normalized transaction
Defined in `backend/schemas/transaction.py`. Any change requires all 3 approvals.

| Field | Rule |
|---|---|
| chain | `bitcoin` / `ethereum` / `tron` / `bsc` |
| amount | `Decimal`, never float. DB type `NUMERIC` |
| timestamp | UTC, ISO 8601 |
| addresses | Lowercased for ethereum/bsc; case preserved for bitcoin/tron |
| contract_address | Only for token transfers |
| raw_ref | Enough info to re-fetch the original record |

## 2. Module interfaces
- **Member 1 output:** `list[NormalizedTransaction]` and `TracePath` (`backend/schemas/path.py`).
- **Member 2 input:** `TracePath` objects. **Output:** attribution results, risk score + factors, and a separate attribution confidence.

## 3. Open decisions (fill in)
- [ ] First chain: ______ (plan suggests Ethereum)
- [ ] Bitcoin multi-input/multi-output flattening rule (Member 1 proposes): ______
- [ ] Confidence scale (e.g. low/medium/high or 0-1): ______

## 4. Sign-off
- [ ] Member 1  - [ ] Member 2  - [ ] Member 3
