"""
Document Retrieval and Caching Client for SEC EDGAR Filings.

Provides rate-limited, point-in-time verified retrieval of primary filing documents:
- Forms: 10-K, 10-Q, 10-K/A, 10-Q/A
- Local disk caching under data/raw_filings/
- Strict PIT temporal isolation: ensures no filings after as_of_date are accessed
"""
import hashlib
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

from src.data.sec_client import SECClient

logger = logging.getLogger(__name__)

DEFAULT_FILINGS_CACHE_DIR = "data/raw_filings"


class DocumentFetcher:
    """Retrieves and caches raw SEC EDGAR HTML/text filings."""

    def __init__(
        self,
        cache_dir: str = DEFAULT_FILINGS_CACHE_DIR,
        user_agent: Optional[str] = None,
        rate_limit_interval: float = 0.12,  # ~8 req/sec
        timeout: float = 20.0,
    ) -> None:
        self.cache_dir = cache_dir
        self.user_agent = user_agent or SECClient.DEFAULT_USER_AGENT
        self.min_interval = rate_limit_interval
        self.timeout = timeout
        self._last_request_time: float = 0.0

        os.makedirs(self.cache_dir, exist_ok=True)

    def _rate_limit(self) -> None:
        """Enforce fair-access interval between calls."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()

    def get_cache_path(self, cik: str, accession_number: str, primary_document: str) -> str:
        """Generate deterministic file path for caching."""
        acc_clean = accession_number.replace("-", "")
        cik_clean = str(int(str(cik).strip()))
        safe_doc = primary_document.replace("/", "_").replace("\\", "_")
        filename = f"{cik_clean}_{acc_clean}_{safe_doc}"
        return os.path.join(self.cache_dir, filename)

    def fetch_document(
        self,
        cik: str,
        accession_number: str,
        primary_document: str,
        filing_date: Optional[str] = None,
        acceptance_datetime: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Fetch primary filing document from local cache or SEC EDGAR.

        Parameters
        ----------
        cik : str
            Central Index Key.
        accession_number : str
            SEC Accession Number (e.g. 0000320193-24-000123).
        primary_document : str
            Document file name (e.g. aapl-20240928.htm).
        filing_date : Optional[str]
            Date filing was submitted.
        acceptance_datetime : Optional[str]
            Exact timestamp of SEC acceptance.
        as_of_date : Optional[str]
            Point-in-time valuation/research date constraint.

        Returns
        -------
        Tuple[str, str, str]
            (raw_html_text, file_path, content_sha256_hash)

        Raises
        ------
        ValueError
            If filing acceptance_datetime or filing_date violates as_of_date constraint.
        """
        # Strict Point-in-Time Enforcement
        if as_of_date:
            cutoff = str(as_of_date)[:10]
            if acceptance_datetime and str(acceptance_datetime)[:10] > cutoff:
                raise ValueError(
                    f"Look-ahead violation: filing acceptance ({acceptance_datetime}) "
                    f"is after as_of_date ({as_of_date})"
                )
            elif filing_date and str(filing_date)[:10] > cutoff:
                raise ValueError(
                    f"Look-ahead violation: filing date ({filing_date}) "
                    f"is after as_of_date ({as_of_date})"
                )

        cache_path = self.get_cache_path(cik, accession_number, primary_document)

        # Check Cache
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            return content, cache_path, content_hash

        # Construct SEC EDGAR URL
        cik_int = str(int(str(cik).strip()))
        acc_clean = accession_number.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{primary_document}"

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }

        self._rate_limit()
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_bytes = resp.read()
                if raw_bytes.startswith(b"\x1f\x8b"):
                    import gzip
                    raw_bytes = gzip.decompress(raw_bytes)
                content = raw_bytes.decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            logger.error("HTTP error %d fetching %s: %s", e.code, url, e.reason)
            raise
        except Exception as e:
            logger.error("Network error fetching %s: %s", url, e)
            raise

        # Write to Cache
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(content)

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return content, cache_path, content_hash
