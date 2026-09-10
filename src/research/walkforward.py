"""
Walk-Forward / Expanding-Window Partitioning and Train-Only Preprocessing for Phase 7.

Ensures strict chronological ordering (max(train_date) < min(test_date)),
zero temporal overlap, and guarantees that all preprocessing parameters (means,
standard deviations, imputers) are calculated exclusively on training partitions.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import math
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.data.db import DatabaseManager, DEFAULT_DB_PATH
from src.research.leakage_audit import LeakageAuditor
from src.research.panel_builder import PanelObservation


@dataclass
class WalkForwardFold:
    """Represents a single chronological train/test walk-forward partition."""
    split_id: str
    fold_number: int
    fold_name: str
    train_start_date: str
    train_end_date: str
    test_start_date: str
    test_end_date: str
    train_obs_ids: List[str]
    test_obs_ids: List[str]
    n_train: int
    n_test: int


@dataclass
class PreprocessingState:
    """Stores frozen training partition scaling and imputation parameters."""
    means: List[float]
    stds: List[float]
    medians: List[float]
    feature_names: List[str]


class WalkForwardValidator:
    """Generates, validates, and persists chronological walk-forward splits."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db = db_manager or DatabaseManager(db_path=db_path)
        self.auditor = LeakageAuditor(db_manager=self.db, db_path=db_path)

    def generate_splits(
        self,
        observations: List[PanelObservation],
        complete_only: bool = True,
    ) -> List[WalkForwardFold]:
        """
        Generate chronological expanding-window splits from complete-case observations.
        Fold 1 (Primary): Train on Cohort 2023 -> Test on Cohort 2024.
        Fold 2 (Sub-Period): Train on Early 2023 -> Test on Mid-2023 to 2024.
        """
        eligible = [
            o for o in observations
            if (not complete_only or (o.has_complete_baseline and o.has_complete_filing and o.has_valid_target))
        ]
        # Sort chronologically by observation date and ticker
        eligible.sort(key=lambda o: (str(o.observation_date), o.ticker))

        cohort_2023 = [o for o in eligible if o.cohort == "COHORT_2023"]
        cohort_2024 = [o for o in eligible if o.cohort == "COHORT_2024"]

        if not cohort_2023 or not cohort_2024:
            raise ValueError(f"Insufficient observations across cohorts: 2023={len(cohort_2023)}, 2024={len(cohort_2024)}")

        folds: List[WalkForwardFold] = []

        # -------------------------------------------------------------
        # Fold 1: Primary Annual Walk-Forward (Cohort 2023 -> Cohort 2024)
        # -------------------------------------------------------------
        train_ids_f1 = [o.observation_id for o in cohort_2023]
        test_ids_f1 = [o.observation_id for o in cohort_2024]
        train_dates_f1 = [str(o.observation_date) for o in cohort_2023]
        test_dates_f1 = [str(o.observation_date) for o in cohort_2024]

        # Audit split separation
        split_check = self.auditor.audit_split("FOLD_1_ANNUAL_COHORT", train_dates_f1, test_dates_f1)
        if split_check.check_status != "PASSED":
            raise ValueError(f"Temporal separation failure in Fold 1: {split_check.details}")

        fold1 = WalkForwardFold(
            split_id=str(uuid.uuid4()),
            fold_number=1,
            fold_name="FOLD_1_ANNUAL_COHORT",
            train_start_date=min(train_dates_f1),
            train_end_date=max(train_dates_f1),
            test_start_date=min(test_dates_f1),
            test_end_date=max(test_dates_f1),
            train_obs_ids=train_ids_f1,
            test_obs_ids=test_ids_f1,
            n_train=len(train_ids_f1),
            n_test=len(test_ids_f1),
        )
        folds.append(fold1)

        # -------------------------------------------------------------
        # Fold 2: Semi-Annual Expanding Sub-Split (H1 2023 -> H2 2023 + 2024)
        # -------------------------------------------------------------
        # Early 2023: Jan to March 2023 filings
        early_2023 = [o for o in cohort_2023 if str(o.observation_date) <= "2023-05-01"]
        later_obs = [o for o in eligible if str(o.observation_date) > "2023-05-01"]

        if early_2023 and later_obs:
            train_ids_f2 = [o.observation_id for o in early_2023]
            test_ids_f2 = [o.observation_id for o in later_obs]
            train_dates_f2 = [str(o.observation_date) for o in early_2023]
            test_dates_f2 = [str(o.observation_date) for o in later_obs]

            split_check2 = self.auditor.audit_split("FOLD_2_SUBPERIOD_EXPANDING", train_dates_f2, test_dates_f2)
            if split_check2.check_status == "PASSED":
                fold2 = WalkForwardFold(
                    split_id=str(uuid.uuid4()),
                    fold_number=2,
                    fold_name="FOLD_2_SUBPERIOD_EXPANDING",
                    train_start_date=min(train_dates_f2),
                    train_end_date=max(train_dates_f2),
                    test_start_date=min(test_dates_f2),
                    test_end_date=max(test_dates_f2),
                    train_obs_ids=train_ids_f2,
                    test_obs_ids=test_ids_f2,
                    n_train=len(train_ids_f2),
                    n_test=len(test_ids_f2),
                )
                folds.append(fold2)

        self._persist_splits(folds)
        return folds

    def _persist_splits(self, folds: List[WalkForwardFold]) -> None:
        """Save walk-forward split metadata to DuckDB."""
        with self.db.get_connection() as con:
            con.execute("DELETE FROM research_walkforward_splits")
            for f in folds:
                con.execute(
                    """
                    INSERT INTO research_walkforward_splits (
                        split_id, fold_number, fold_name, train_start_date, train_end_date,
                        test_start_date, test_end_date, n_train, n_test,
                        train_observation_ids, test_observation_ids
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        f.split_id, f.fold_number, f.fold_name,
                        f.train_start_date, f.train_end_date,
                        f.test_start_date, f.test_end_date,
                        f.n_train, f.n_test,
                        json.dumps(f.train_obs_ids), json.dumps(f.test_obs_ids),
                    ],
                )

    @staticmethod
    def fit_train_preprocessor(
        train_X: List[List[float]],
        feature_names: List[str],
    ) -> PreprocessingState:
        """
        Compute standard scaling means and standard deviations strictly on training partition.
        """
        n_samples = len(train_X)
        n_features = len(feature_names)
        if n_samples == 0:
            raise ValueError("Cannot fit preprocessor on empty training set.")

        means: List[float] = []
        stds: List[float] = []
        medians: List[float] = []

        for j in range(n_features):
            col_vals = [train_X[i][j] for i in range(n_samples)]
            # Median
            sorted_vals = sorted(col_vals)
            mid = n_samples // 2
            med = sorted_vals[mid] if n_samples % 2 == 1 else 0.5 * (sorted_vals[mid - 1] + sorted_vals[mid])
            medians.append(med)

            # Mean
            mean_j = sum(col_vals) / n_samples
            means.append(mean_j)

            # Std
            var_j = sum((x - mean_j) ** 2 for x in col_vals) / max(1, n_samples - 1)
            std_j = math.sqrt(var_j)
            if std_j < 1e-8:
                std_j = 1.0  # Avoid division by zero for constant features
            stds.append(std_j)

        return PreprocessingState(
            means=means,
            stds=stds,
            medians=medians,
            feature_names=feature_names,
        )

    @staticmethod
    def transform(
        X: List[List[float]],
        state: PreprocessingState,
    ) -> List[List[float]]:
        """
        Apply pre-fitted training scaling parameters to any partition (train or test).
        Zero leakage: uses only state.means and state.stds.
        """
        n_features = len(state.feature_names)
        transformed: List[List[float]] = []

        for row in X:
            scaled_row: List[float] = []
            for j in range(n_features):
                val = row[j]
                mu = state.means[j]
                sd = state.stds[j]
                scaled_row.append((val - mu) / sd)
            transformed.append(scaled_row)

        return transformed
