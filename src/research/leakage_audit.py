"""
Automated Data Leakage Auditor for Phase 7 Research Panel.

Enforces strict temporal separation and point-in-time invariant checks across
all panel observations, feature inputs, forward targets, and walk-forward splits:

1. Financial Acceptance Invariant: financial acceptance <= observation_date
2. Filing Acceptance Invariant: filing acceptance <= observation_date
3. Target Temporal Invariant: target realization date > observation_date
4. Walk-Forward Chronological Invariant: max(train_date) < min(test_date)
5. Adversarial Leakage Rejection: verifies pipeline fails when future data is injected.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.research.panel_builder import PanelObservation, PanelTargets


class LeakageViolationError(Exception):
    """Raised when point-in-time temporal boundaries are violated."""
    pass


@dataclass
class LeakageCheckResult:
    """Outcome of an individual temporal invariant audit check."""
    audit_id: str
    observation_id: str
    ticker: str
    check_name: str
    check_status: str       # 'PASSED', 'FAILED'
    details: str


class LeakageAuditor:
    """Performs rigorous automated point-in-time audits on the research panel."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)

    def audit_observation(
        self,
        obs: PanelObservation,
        target: Optional[PanelTargets] = None,
    ) -> List[LeakageCheckResult]:
        """
        Verify all point-in-time invariants for a single observation.
        """
        results: List[LeakageCheckResult] = []
        obs_date = str(obs.observation_date)[:10]

        # 1. Financial acceptance timestamp <= observation_date
        fin_as_of = str(obs.financial_data_as_of)[:10]
        c1_passed = (fin_as_of <= obs_date)
        results.append(LeakageCheckResult(
            audit_id=str(uuid.uuid4()),
            observation_id=obs.observation_id,
            ticker=obs.ticker,
            check_name="FINANCIAL_PIT_TIMESTAMP",
            check_status="PASSED" if c1_passed else "FAILED",
            details=f"Financial as-of ({fin_as_of}) <= obs_date ({obs_date})",
        ))

        # 2. Filing acceptance timestamp <= observation_date
        filing_as_of = str(obs.filing_data_as_of)[:10]
        c2_passed = (filing_as_of <= obs_date)
        results.append(LeakageCheckResult(
            audit_id=str(uuid.uuid4()),
            observation_id=obs.observation_id,
            ticker=obs.ticker,
            check_name="FILING_PIT_TIMESTAMP",
            check_status="PASSED" if c2_passed else "FAILED",
            details=f"Filing as-of ({filing_as_of}) <= obs_date ({obs_date})",
        ))

        # 3. Target realization date > observation_date (if valid target exists)
        if obs.has_valid_target and target and target.is_valid:
            targ_realized = str(target.realization_date)[:10]
            c3_passed = (targ_realized > obs_date)
            results.append(LeakageCheckResult(
                audit_id=str(uuid.uuid4()),
                observation_id=obs.observation_id,
                ticker=obs.ticker,
                check_name="TARGET_STRICTLY_FORWARD",
                check_status="PASSED" if c3_passed else "FAILED",
                details=f"Target realization ({targ_realized}) > obs_date ({obs_date})",
            ))

            # 4. Target fiscal year > base fiscal year
            c4_passed = (obs.target_fiscal_year > obs.base_fiscal_year)
            results.append(LeakageCheckResult(
                audit_id=str(uuid.uuid4()),
                observation_id=obs.observation_id,
                ticker=obs.ticker,
                check_name="TARGET_FISCAL_YEAR_ORDERING",
                check_status="PASSED" if c4_passed else "FAILED",
                details=f"Target FY ({obs.target_fiscal_year}) > Base FY ({obs.base_fiscal_year})",
            ))

        return results

    def audit_split(
        self,
        fold_name: str,
        train_dates: List[str],
        test_dates: List[str],
    ) -> LeakageCheckResult:
        """
        Verify that a walk-forward split has zero look-ahead bias:
        assert max(train_date) < min(test_date).
        """
        if not train_dates or not test_dates:
            raise ValueError(f"Split {fold_name} has empty train or test partition.")

        max_train = max(str(d)[:10] for d in train_dates)
        min_test = min(str(d)[:10] for d in test_dates)

        is_strictly_prior = (max_train < min_test)
        status = "PASSED" if is_strictly_prior else "FAILED"
        details = f"max(train) = {max_train} < min(test) = {min_test}"

        return LeakageCheckResult(
            audit_id=str(uuid.uuid4()),
            observation_id=f"SPLIT_{fold_name}",
            ticker="PANEL",
            check_name="WALKFORWARD_CHRONOLOGICAL_SEPARATION",
            check_status=status,
            details=details,
        )

    def run_full_audit(
        self,
        observations: List[PanelObservation],
        targets: List[PanelTargets],
        splits: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full leakage audit on all observations and persist results to DuckDB.
        Raises LeakageViolationError if any critical check fails.
        """
        targets_by_id = {t.observation_id: t for t in targets}
        all_checks: List[LeakageCheckResult] = []

        for obs in observations:
            targ = targets_by_id.get(obs.observation_id)
            checks = self.audit_observation(obs, targ)
            all_checks.extend(checks)

        if splits:
            for s in splits:
                split_check = self.audit_split(
                    fold_name=s["fold_name"],
                    train_dates=s["train_dates"],
                    test_dates=s["test_dates"],
                )
                all_checks.append(split_check)

        # Check for failures
        failures = [c for c in all_checks if c.check_status == "FAILED"]
        self._persist_audit_results(all_checks)

        if failures:
            fail_details = "; ".join(f"[{f.ticker} {f.check_name}: {f.details}]" for f in failures[:5])
            raise LeakageViolationError(f"Leakage audit detected {len(failures)} violations: {fail_details}")

        return {
            "total_checks": len(all_checks),
            "passed_checks": len(all_checks),
            "failed_checks": 0,
            "status": "PASSED",
            "results": all_checks,
        }

    def _persist_audit_results(self, checks: List[LeakageCheckResult]) -> None:
        """Persist audit records to research_panel_leakage_audit table."""
        with self.db.get_connection() as con:
            con.execute("DELETE FROM research_panel_leakage_audit")
            for c in checks:
                con.execute(
                    """
                    INSERT INTO research_panel_leakage_audit (
                        audit_id, observation_id, ticker, check_name, check_status, details
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [c.audit_id, c.observation_id, c.ticker, c.check_name, c.check_status, c.details],
                )

    def verify_adversarial_leakage_rejection(self) -> bool:
        """
        Adversarial test: Deliberately constructs observations with look-ahead leakage
        and verifies that audit_observation and audit_split correctly flag and reject them.
        """
        # Test 1: Future financial timestamp
        bad_obs1 = PanelObservation(
            observation_id="BAD_OBS_1",
            company_id="US_TEST",
            ticker="TEST",
            cik="0000000000",
            sector="Technology",
            cohort="COHORT_2023",
            observation_date="2023-02-15",
            acceptance_datetime="2023-02-15 12:00:00",
            latest_filing_form="10-K",
            latest_filing_accession="0000000000-23-000001",
            financial_data_as_of="2024-02-15",  # LEAK: 1 year in future
            filing_data_as_of="2023-02-15",
            base_fiscal_year=2022,
            target_fiscal_year=2023,
            target_realization_date="2024-02-15",
            target_realization_accession="0000000000-24-000001",
            has_complete_baseline=True,
            has_complete_filing=True,
            has_valid_target=True,
        )
        res1 = self.audit_observation(bad_obs1)
        if not any(c.check_status == "FAILED" for c in res1):
            return False

        # Test 2: Target realized before or on observation date
        bad_obs2 = PanelObservation(
            observation_id="BAD_OBS_2",
            company_id="US_TEST",
            ticker="TEST",
            cik="0000000000",
            sector="Technology",
            cohort="COHORT_2023",
            observation_date="2023-02-15",
            acceptance_datetime="2023-02-15 12:00:00",
            latest_filing_form="10-K",
            latest_filing_accession="0000000000-23-000001",
            financial_data_as_of="2023-02-15",
            filing_data_as_of="2023-02-15",
            base_fiscal_year=2022,
            target_fiscal_year=2023,
            target_realization_date="2023-01-10",  # LEAK: before obs date
            target_realization_accession="0000000000-23-000002",
            has_complete_baseline=True,
            has_complete_filing=True,
            has_valid_target=True,
        )
        bad_target2 = PanelTargets(
            observation_id="BAD_OBS_2",
            ticker="TEST",
            forward_ebit_margin_change=0.02,
            forward_revenue_growth=0.05,
            earnings_deterioration=0.0,
            realization_date="2023-01-10",
            realization_accession="0000000000-23-000002",
            is_valid=True,
        )
        res2 = self.audit_observation(bad_obs2, bad_target2)
        if not any(c.check_status == "FAILED" for c in res2):
            return False

        # Test 3: Chronological split violation (train max >= test min)
        res3 = self.audit_split(
            fold_name="BAD_SPLIT",
            train_dates=["2023-01-01", "2024-03-01"],
            test_dates=["2024-01-15", "2024-06-01"],
        )
        if res3.check_status != "FAILED":
            return False

        return True
