"""
Deterministic Feature Alignment and Aggregation Module for Phase 6.

Transforms granular point-in-time qualitative claims and change signals
into standardized, numerical filing features and aligns them with conventional
financial statement features.
"""
from typing import Any, Dict, List, Optional

from src.research.models import BaselineFeatures, FilingFeatures


def aggregate_filing_claims(
    ticker: str,
    fiscal_year: int,
    accession_number: str,
    extractions: List[Dict[str, Any]],
    change_signals: Optional[List[Dict[str, Any]]] = None,
) -> FilingFeatures:
    """
    Deterministically aggregate qualitative claims for a given company and filing
    into normalized numerical features.
    """
    change_signals = change_signals or []

    if not extractions:
        return FilingFeatures(
            ticker=ticker,
            fiscal_year=fiscal_year,
            accession_number=accession_number,
        )

    # Weights for severity and direction
    sev_weights = {"LOW": 0.33, "MEDIUM": 0.67, "HIGH": 1.0}
    mat_weights = {"LOW": 0.33, "MEDIUM": 0.67, "HIGH": 1.0}
    dir_signs = {"POSITIVE": 1.0, "NEUTRAL": 0.0, "MIXED": -0.3, "NEGATIVE": -1.0}

    # Category buckets
    category_scores: Dict[str, List[float]] = {
        "MARGIN_PRESSURE": [],
        "SUPPLY_CHAIN_RISK": [],
        "REGULATORY_RISK": [],
        "LITIGATION_RISK": [],
        "DEMAND_UNCERTAINTY": [],
        "GUIDANCE_DIRECTION": [],
        "CAPITAL_ALLOCATION_CHANGE": [],
    }

    pos_count = 0
    neg_count = 0
    total_risk_claims = 0
    high_mat_count = 0

    for ext in extractions:
        cat = ext.get("category", "")
        direction = ext.get("direction", "NEUTRAL")
        severity = ext.get("severity", "LOW")
        materiality = ext.get("materiality", "LOW")
        conf = float(ext.get("confidence", 0.90))

        s_weight = sev_weights.get(severity, 0.33)
        m_weight = mat_weights.get(materiality, 0.33)
        d_sign = dir_signs.get(direction, 0.0)

        # Risk intensity: positive magnitude if negative direction or risk category
        risk_intensity = s_weight * m_weight * conf

        if cat in category_scores:
            if cat in ("GUIDANCE_DIRECTION", "CAPITAL_ALLOCATION_CHANGE"):
                # Signed directional score
                category_scores[cat].append(d_sign * s_weight * conf)
            else:
                # Risk intensity
                category_scores[cat].append(risk_intensity)

        if direction == "POSITIVE":
            pos_count += 1
        elif direction in ("NEGATIVE", "MIXED"):
            neg_count += 1
            total_risk_claims += 1

        if materiality == "HIGH":
            high_mat_count += 1

    # Escalated risks from change signals
    escalated_count = sum(1 for sig in change_signals if sig.get("change_type") == "ESCALATED")

    total_claims = len(extractions)
    net_sentiment = (pos_count - neg_count) / max(1, total_claims)

    def avg_or_zero(scores: List[float]) -> float:
        return sum(scores) / len(scores) if scores else 0.0

    return FilingFeatures(
        ticker=ticker,
        fiscal_year=fiscal_year,
        accession_number=accession_number,
        margin_pressure_score=avg_or_zero(category_scores["MARGIN_PRESSURE"]),
        supply_chain_risk_score=avg_or_zero(category_scores["SUPPLY_CHAIN_RISK"]),
        regulatory_risk_score=avg_or_zero(category_scores["REGULATORY_RISK"]),
        litigation_risk_score=avg_or_zero(category_scores["LITIGATION_RISK"]),
        demand_uncertainty_score=avg_or_zero(category_scores["DEMAND_UNCERTAINTY"]),
        guidance_sentiment_score=avg_or_zero(category_scores["GUIDANCE_DIRECTION"]),
        capital_allocation_score=avg_or_zero(category_scores["CAPITAL_ALLOCATION_CHANGE"]),
        total_risk_claims=float(total_risk_claims),
        high_materiality_risk_count=float(high_mat_count),
        escalated_risk_count=float(escalated_count),
        net_qualitative_sentiment=float(net_sentiment),
    )


def extract_baseline_features(
    ticker: str,
    fiscal_year: int,
    feature_rows: List[Dict[str, Any]],
    beta: float = 1.0,
    wacc: float = 0.08,
) -> BaselineFeatures:
    """
    Extract conventional fundamental features for a company and fiscal year
    from historical financial_features table records.
    """
    feat_map = {r["feature_name"]: float(r["feature_value"]) for r in feature_rows if r.get("feature_value") is not None}

    return BaselineFeatures(
        ticker=ticker,
        fiscal_year=fiscal_year,
        revenue_growth_yoy=feat_map.get("revenue_growth_yoy", 0.0),
        ebit_margin=feat_map.get("ebit_margin", 0.0),
        gross_margin=feat_map.get("gross_margin", 0.0),
        roic=feat_map.get("roic", 0.0),
        fcf_margin=feat_map.get("fcf_margin", 0.0),
        net_debt_to_revenue=feat_map.get("net_debt", 0.0) / max(1.0, feat_map.get("revenue", 1e9)) if "net_debt" in feat_map else 0.0,
        owc_to_revenue=feat_map.get("owc_to_revenue", 0.0),
        beta=beta,
        wacc=wacc,
    )
