"""Test-wide environment: no real pacing sleeps, and the dev auth stub explicitly enabled."""

import os

os.environ.setdefault("ETHERSCAN_MIN_INTERVAL", "0")
os.environ.setdefault("ETHERSCAN_RETRY_DELAY", "0.01")
os.environ.setdefault("ALLOW_DEV_AUTH_STUB", "true")
os.environ.pop("SUPABASE_JWT_SECRET", None)
os.environ.pop("SUPABASE_URL", None)

try:
    from backend.database.supabase_client import global_supabase_client
    global_supabase_client.is_configured = False
except Exception:
    pass
