"""
Period-over-Period Qualitative Change Detection Engine.

Performs structured delta analysis between two filings (e.g. 10-K 2024 vs 10-K 2023,
or 10-Q Q2 vs 10-Q Q1) using validated qualitative claims rather than raw character diffs.
Identifies:
- NEW: Risks or strategies newly disclosed in current period
- ESCALATED: Disclosures with increased severity or expanded scope
- RESOLVED: Prior concerns omitted or resolved in current period
- MODIFIED: Polarity/direction shift in ongoing disclosures
- PERSISTENT: Unchanged recurring disclosures
"""
import logging
from typing import Dict, List, Optional
import uuid

from src.filing_intelligence.schemas import (
    ChangeSignal,
    ChangeType,
    ExtractedClaim,
    Materiality,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, "UNKNOWN": 0}


class ChangeDetector:
    """Detects substantive structured shifts between consecutive SEC filings."""

    def detect_changes(
        self,
        current_claims: List[ExtractedClaim],
        previous_claims: List[ExtractedClaim],
        current_accession: str,
        previous_accession: str,
        ticker: str,
    ) -> List[ChangeSignal]:
        """
        Compare current and previous claims to generate structured change signals.
        """
        signals: List[ChangeSignal] = []

        # Index claims by category (using validated claims only)
        curr_map: Dict[str, ExtractedClaim] = {
            c.category: c for c in current_claims if c.validation_status == "VALIDATED"
        }
        prev_map: Dict[str, ExtractedClaim] = {
            c.category: c for c in previous_claims if c.validation_status == "VALIDATED"
        }

        all_categories = set(curr_map.keys()).union(set(prev_map.keys()))

        for cat in sorted(all_categories):
            curr_c = curr_map.get(cat)
            prev_c = prev_map.get(cat)

            sig_id = f"sig_{ticker}_{cat.lower()}_{uuid.uuid4().hex[:6]}"

            if curr_c and not prev_c:
                # NEW Signal
                summary = f"New {cat.replace('_', ' ').lower()} disclosure identified in current period."
                signals.append(
                    ChangeSignal(
                        signal_id=sig_id,
                        ticker=ticker,
                        current_accession=current_accession,
                        previous_accession=previous_accession,
                        category=cat,
                        change_type=ChangeType.NEW.value,
                        current_claim=curr_c.claim,
                        previous_claim=None,
                        direction_shift=f"NONE -> {curr_c.direction}",
                        severity_shift=f"NONE -> {curr_c.severity}",
                        materiality=curr_c.materiality,
                        summary=summary,
                    )
                )

            elif prev_c and not curr_c:
                # RESOLVED / OMITTED Signal
                summary = f"Prior {cat.replace('_', ' ').lower()} disclosure omitted or resolved."
                signals.append(
                    ChangeSignal(
                        signal_id=sig_id,
                        ticker=ticker,
                        current_accession=current_accession,
                        previous_accession=previous_accession,
                        category=cat,
                        change_type=ChangeType.RESOLVED.value,
                        current_claim=None,
                        previous_claim=prev_c.claim,
                        direction_shift=f"{prev_c.direction} -> NONE",
                        severity_shift=f"{prev_c.severity} -> NONE",
                        materiality=prev_c.materiality,
                        summary=summary,
                    )
                )

            elif curr_c and prev_c:
                curr_sev = SEVERITY_ORDER.get(curr_c.severity.upper(), 0)
                prev_sev = SEVERITY_ORDER.get(prev_c.severity.upper(), 0)

                if curr_sev > prev_sev:
                    # ESCALATED Signal
                    summary = f"Escalated severity in {cat.replace('_', ' ').lower()} ({prev_c.severity} -> {curr_c.severity})."
                    signals.append(
                        ChangeSignal(
                            signal_id=sig_id,
                            ticker=ticker,
                            current_accession=current_accession,
                            previous_accession=previous_accession,
                            category=cat,
                            change_type=ChangeType.ESCALATED.value,
                            current_claim=curr_c.claim,
                            previous_claim=prev_c.claim,
                            direction_shift=f"{prev_c.direction} -> {curr_c.direction}",
                            severity_shift=f"{prev_c.severity} -> {curr_c.severity}",
                            materiality=curr_c.materiality,
                            summary=summary,
                        )
                    )
                elif curr_c.direction != prev_c.direction and curr_c.direction != "UNKNOWN":
                    # MODIFIED Polarity Signal
                    summary = f"Directional shift in {cat.replace('_', ' ').lower()} ({prev_c.direction} -> {curr_c.direction})."
                    signals.append(
                        ChangeSignal(
                            signal_id=sig_id,
                            ticker=ticker,
                            current_accession=current_accession,
                            previous_accession=previous_accession,
                            category=cat,
                            change_type=ChangeType.MODIFIED.value,
                            current_claim=curr_c.claim,
                            previous_claim=prev_c.claim,
                            direction_shift=f"{prev_c.direction} -> {curr_c.direction}",
                            severity_shift=f"{prev_c.severity} -> {curr_c.severity}",
                            materiality=curr_c.materiality,
                            summary=summary,
                        )
                    )
                else:
                    # PERSISTENT Ongoing Disclosure
                    summary = f"Persistent {cat.replace('_', ' ').lower()} disclosure maintained."
                    signals.append(
                        ChangeSignal(
                            signal_id=sig_id,
                            ticker=ticker,
                            current_accession=current_accession,
                            previous_accession=previous_accession,
                            category=cat,
                            change_type=ChangeType.PERSISTENT.value,
                            current_claim=curr_c.claim,
                            previous_claim=prev_c.claim,
                            direction_shift=f"{prev_c.direction} == {curr_c.direction}",
                            severity_shift=f"{prev_c.severity} == {curr_c.severity}",
                            materiality=curr_c.materiality,
                            summary=summary,
                        )
                    )

        return signals
