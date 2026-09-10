"""
SEC EDGAR REST API Client.
Provides rate-limited, cached, deterministic programmatic access to:
- Company submissions (metadata, filing dates, accession numbers, acceptanceDateTime)
- Company facts (complete XBRL facts repository)
- Company concepts (individual concept time-series)

Complies strictly with SEC EDGAR Fair Access policy:
- Declarative User-Agent header (Sample Company Name AdminContact@domain.com)
- Maximum rate limiting <= 10 requests/second (default: 8 req/sec)
- Exponential backoff retry logic on HTTP 429/5xx
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SECClientError(Exception):
    """Base exception for SEC EDGAR client errors."""
    pass


class SECRateLimitError(SECClientError):
    """Raised when SEC rate limit is exceeded (HTTP 429)."""
    pass


class SECObjectNotFoundError(SECClientError):
    """Raised when the requested CIK or concept is not found (HTTP 404)."""
    pass


class SECClient:
    """Production-grade rate-limited client for SEC EDGAR REST APIs."""

    BASE_DATA_URL = "https://data.sec.gov"
    DEFAULT_USER_AGENT = "AcademicResearch valuation_audit@university.edu"

    def __init__(
        self,
        user_agent: Optional[str] = None,
        max_requests_per_second: float = 8.0,
        timeout: float = 15.0,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        cache_dir: Optional[str] = None,
    ) -> None:
        """
        Initialize SEC EDGAR client.

        Args:
            user_agent: User-Agent string adhering to SEC guidelines.
            max_requests_per_second: Maximum requests allowed per second (<= 10.0).
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retries for transient errors.
            backoff_factor: Multiplier for exponential backoff between retries.
            cache_dir: Optional local directory for caching raw JSON payloads.
        """
        self.user_agent = user_agent or os.environ.get("SEC_USER_AGENT", self.DEFAULT_USER_AGENT)
        if "@" not in self.user_agent:
            logger.warning("SEC EDGAR requires User-Agent to contain an email contact address.")

        self.min_interval = 1.0 / min(max(max_requests_per_second, 0.1), 10.0)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.cache_dir = cache_dir
        self._last_request_time: float = 0.0

        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _rate_limit(self) -> None:
        """Enforce minimum interval between consecutive requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()

    def _get_cache_path(self, cache_key: str) -> Optional[str]:
        """Return file path for a cached resource if cache_dir is enabled."""
        if not self.cache_dir:
            return None
        safe_name = cache_key.replace("/", "_").replace(":", "_") + ".json"
        return os.path.join(self.cache_dir, safe_name)

    def _request_json(self, endpoint: str, cache_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute an HTTP GET request to data.sec.gov with rate limiting and retry logic.

        Args:
            endpoint: URL path starting with '/'
            cache_key: Optional key to check/store cached JSON

        Returns:
            Parsed JSON dictionary
        """
        # Check disk cache first
        if cache_key:
            cache_path = self._get_cache_path(cache_key)
            if cache_path and os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Error reading cache at {cache_path}: {e}")

        url = f"{self.BASE_DATA_URL}{endpoint}"
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

        last_exception: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                    if raw_bytes.startswith(b"\x1f\x8b"):
                        import gzip
                        raw_bytes = gzip.decompress(raw_bytes)
                    raw_data = raw_bytes.decode("utf-8")
                    data = json.loads(raw_data)

                    # Save to cache if enabled
                    if cache_key:
                        cache_path = self._get_cache_path(cache_key)
                        if cache_path:
                            try:
                                with open(cache_path, "w", encoding="utf-8") as f:
                                    json.dump(data, f)
                            except Exception as e:
                                logger.warning(f"Failed to write cache at {cache_path}: {e}")

                    return data

            except urllib.error.HTTPError as e:
                last_exception = e
                if e.code == 404:
                    raise SECObjectNotFoundError(f"SEC resource not found: {url} (HTTP 404)") from e
                elif e.code == 429:
                    sleep_time = (self.backoff_factor ** attempt) * 2.0
                    logger.warning(f"SEC HTTP 429 rate limit reached. Backing off for {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                elif 500 <= e.code < 600:
                    sleep_time = self.backoff_factor ** attempt
                    logger.warning(f"SEC server error HTTP {e.code}. Retrying in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                else:
                    raise SECClientError(f"HTTP error {e.code} for {url}: {e.reason}") from e

            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as e:
                last_exception = e
                sleep_time = self.backoff_factor ** attempt
                logger.warning(f"Network error accessing {url} (attempt {attempt}/{self.max_retries}): {e}. Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)

        raise SECClientError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exception}")

    def get_company_submissions(self, cik: str) -> Dict[str, Any]:
        """
        Fetch company submission history and metadata.

        Args:
            cik: Central Index Key (numeric or zero-padded string).

        Returns:
            Dictionary with entity details and recent filings metadata.
        """
        padded_cik = str(cik).strip().zfill(10)
        endpoint = f"/submissions/CIK{padded_cik}.json"
        return self._request_json(endpoint, cache_key=f"submissions_CIK{padded_cik}")

    def get_company_facts(self, cik: str) -> Dict[str, Any]:
        """
        Fetch all XBRL company facts for an entity across all taxonomies.

        Args:
            cik: Central Index Key (numeric or zero-padded string).

        Returns:
            Dictionary containing 'facts' categorized by taxonomy ('us-gaap', 'dei', etc.).
        """
        padded_cik = str(cik).strip().zfill(10)
        endpoint = f"/api/xbrl/companyfacts/CIK{padded_cik}.json"
        return self._request_json(endpoint, cache_key=f"CIK{padded_cik}")

    def get_company_concept(self, cik: str, taxonomy: str, concept: str) -> Dict[str, Any]:
        """
        Fetch time series facts for a specific taxonomy concept.

        Args:
            cik: Central Index Key.
            taxonomy: Taxonomy name (e.g., 'us-gaap', 'dei').
            concept: Concept name (e.g., 'Revenues', 'Assets').

        Returns:
            Dictionary containing concept units and fact records.
        """
        padded_cik = str(cik).strip().zfill(10)
        endpoint = f"/api/xbrl/companyconcept/CIK{padded_cik}/{taxonomy}/{concept}.json"
        return self._request_json(endpoint, cache_key=f"concept_CIK{padded_cik}_{taxonomy}_{concept}")

    @staticmethod
    def extract_recent_filings_catalog(submissions_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract structured list of recent filings from submissions JSON.

        Returns list of dicts with keys:
        accessionNumber, filingDate, reportDate, acceptanceDateTime, act, form,
        fileNumber, filmNumber, items, size, isXBRL, isInlineXBRL, primaryDocument
        """
        recent = submissions_data.get("filings", {}).get("recent", {})
        if not recent or "accessionNumber" not in recent:
            return []

        keys = list(recent.keys())
        n_rows = len(recent["accessionNumber"])
        filings = []
        for i in range(n_rows):
            filing = {k: recent[k][i] if i < len(recent[k]) else None for k in keys}
            filings.append(filing)
        return filings
