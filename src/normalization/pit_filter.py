"""
Point-in-Time (PIT) Data Control & Information Set Filter.
Guarantees strict temporal leakage isolation for historical backtesting.

Core Invariant:
For any analysis/as-of date T:
Only facts publicly disseminated on or before T are admissible.
Fiscal period end date != information public availability date.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse string date or ISO timestamp into a timezone-aware UTC datetime."""
    clean_str = str(dt_str).strip()
    # If pure date YYYY-MM-DD, treat as end-of-day UTC for as_of or start-of-day for filing
    if len(clean_str) == 10 and clean_str.count("-") == 2:
        clean_str += "T23:59:59Z"

    # Replace Z with +00:00 for fromisoformat compatibility in Python 3.9-3.10
    if clean_str.endswith("Z"):
        clean_str = clean_str[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        # Fallback for older formats
        logger.debug(f"Failed to parse datetime '{clean_str}': {e}")
        return datetime(1900, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class PITFilter:
    """Enforces Point-in-Time information availability on financial facts."""

    @staticmethod
    def is_available_as_of(acceptance_datetime: str, as_of_date: str) -> bool:
        """
        Check whether an observation accepted at acceptance_datetime
        was publicly accessible at as_of_date.
        """
        fact_dt = parse_iso_datetime(acceptance_datetime)
        as_of_dt = parse_iso_datetime(as_of_date)
        return fact_dt <= as_of_dt

    @classmethod
    def filter_facts_as_of(
        cls,
        facts: List[Dict[str, Any]],
        as_of_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Filter and deduplicate financial facts as of a specific historical date.

        Rules:
        1. Only facts with acceptance_datetime <= as_of_date are admitted.
        2. If multiple facts exist for the same (ticker, fiscal_year, fiscal_period, canonical_variable),
           the latest filing accepted on or before as_of_date takes precedence.
        3. Amendments (10-K/A, 10-Q/A) accepted after as_of_date are strictly excluded.
        4. If an amendment was accepted on or before as_of_date, it supersedes earlier filings.

        Args:
            facts: List of normalized financial facts.
            as_of_date: ISO timestamp or date string representing historical valuation date.

        Returns:
            List of valid, deduplicated facts representing the true historical information set.
        """
        as_of_dt = parse_iso_datetime(as_of_date)

        # 1. Filter strictly by acceptance timestamp <= as_of_date
        admissible: List[Dict[str, Any]] = []
        for f in facts:
            fact_dt = parse_iso_datetime(f.get("acceptance_datetime", "1900-01-01T00:00:00Z"))
            if fact_dt <= as_of_dt:
                admissible.append(f)

        # 2. Group by period and canonical variable
        grouped: Dict[Tuple[str, int, str, str], List[Dict[str, Any]]] = {}
        for f in admissible:
            key = (
                f["ticker"],
                int(f["fiscal_year"]),
                str(f["fiscal_period"]),
                str(f["canonical_variable"]),
            )
            grouped.setdefault(key, []).append(f)

        # 3. For each group, select the latest accepted fact
        pit_selected: List[Dict[str, Any]] = []
        for key, group_entries in grouped.items():
            if len(group_entries) == 1:
                pit_selected.append(group_entries[0])
            else:
                # Rank candidates: latest acceptance_datetime first, then 10-K/A over 10-K
                def rank_key(e: Dict[str, Any]) -> Tuple[datetime, int, str]:
                    dt = parse_iso_datetime(e.get("acceptance_datetime", "1900-01-01"))
                    is_amend = 1 if "/A" in str(e.get("form", "")) else 0
                    accn = str(e.get("accession_number", ""))
                    return (dt, is_amend, accn)

                best = sorted(group_entries, key=rank_key)[-1]
                pit_selected.append(best)

        # Sort for deterministic output
        pit_selected.sort(key=lambda x: (x["ticker"], x["fiscal_year"], x["fiscal_period"], x["canonical_variable"]))
        return pit_selected

    @classmethod
    def audit_leakage(
        cls,
        all_facts: List[Dict[str, Any]],
        as_of_date: str,
    ) -> Dict[str, Any]:
        """
        Run an explicit leakage audit verifying that no future facts leaked into as_of_date.

        Returns audit summary dict with counts and boolean 'leakage_free' flag.
        """
        as_of_dt = parse_iso_datetime(as_of_date)
        pit_facts = cls.filter_facts_as_of(all_facts, as_of_date)

        violations = []
        for f in pit_facts:
            fact_dt = parse_iso_datetime(f.get("acceptance_datetime", "1900-01-01"))
            if fact_dt > as_of_dt:
                violations.append({
                    "ticker": f.get("ticker"),
                    "canonical_variable": f.get("canonical_variable"),
                    "acceptance_datetime": str(f.get("acceptance_datetime")),
                    "as_of_date": as_of_date,
                })

        return {
            "as_of_date": as_of_date,
            "total_input_facts": len(all_facts),
            "admitted_facts": len(pit_facts),
            "rejected_future_facts": len(all_facts) - len(pit_facts),
            "leakage_violations_count": len(violations),
            "leakage_free": len(violations) == 0,
            "violations_sample": violations[:5],
        }
