"""Supabase REST and Storage Client Adapter.

Handles communication with Supabase PostgreSQL (via PostgREST) and
Supabase Storage API for PDF evidence reports in Phase 2.
"""

import logging
import os
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("crypto_attribution.supabase")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "evidence-reports")


class SupabaseClient:
    """HTTP client interface for Supabase REST tables and Storage API."""

    def __init__(
        self,
        base_url: Optional[str] = SUPABASE_URL,
        api_key: Optional[str] = SUPABASE_KEY,
        bucket_name: str = SUPABASE_BUCKET,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.bucket = bucket_name
        self.is_configured = bool(self.base_url and self.api_key and "supabase.co" in self.base_url)

        if not self.is_configured:
            logger.info("Supabase credentials not configured in .env. Running in local repository mode.")

    def _headers(self, content_type: str = "application/json") -> Dict[str, str]:
        return {
            "apikey": self.api_key or "",
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": content_type,
            "Prefer": "return=representation",
        }

    async def insert_record(self, table: str, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Inserts a record into a Supabase PostgREST table."""
        if not self.is_configured:
            return None

        url = f"{self.base_url}/rest/v1/{table}"
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(url, headers=self._headers(), json=record, timeout=10.0)
                if res.status_code in (200, 201):
                    data = res.json()
                    return data[0] if isinstance(data, list) and data else record
                logger.warning(f"Supabase insert into {table} failed: {res.status_code} {res.text}")
            except Exception as e:
                logger.error(f"Error inserting into Supabase table {table}: {e}")
        return None

    async def upload_evidence_pdf(self, storage_path: str, pdf_bytes: bytes) -> Optional[str]:
        """Uploads evidence report PDF bytes to Supabase Storage bucket."""
        if not self.is_configured:
            return None

        filename = os.path.basename(storage_path)
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{filename}"
        headers = self._headers(content_type="application/pdf")

        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(url, headers=headers, content=pdf_bytes, timeout=15.0)
                if res.status_code in (200, 201):
                    logger.info(f"Report uploaded to Supabase Storage: {self.bucket}/{filename}")
                    return f"{self.bucket}/{filename}"
                logger.warning(f"Supabase Storage upload failed: {res.status_code} {res.text}")
            except Exception as e:
                logger.error(f"Error uploading to Supabase Storage: {e}")
        return None


global_supabase_client = SupabaseClient()
