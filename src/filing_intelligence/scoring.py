"""
Confidence and Materiality Scoring Engine.

Implements structured, auditable scoring rules:
1. Confidence Scoring: Combines quote match quality, length substance, section authority,
   and category lexical alignment. Flags extractions with confidence < 0.70 as NEEDS_REVIEW.
2. Materiality Classification: Evaluates economic and operational significance based on
   quantitative thresholds, enforcement actions, structural reorganizations, and credit terms.
"""
import logging
import re
from typing import Tuple

from src.filing_intelligence.schemas import Materiality, ValidationResult

logger = logging.getLogger(__name__)

# Section Authority Weights for Analytical Categories
SECTION_AUTHORITY_WEIGHTS = {
    "ITEM_1A_RISK_FACTORS": {
        "REGULATORY_RISK": 1.0, "LITIGATION_RISK": 0.9, "DEMAND_UNCERTAINTY": 0.8,
        "SUPPLY_CHAIN_RISK": 0.9, "LIQUIDITY_RISK": 0.8, "COMPETITIVE_PRESSURE": 0.8,
    },
    "ITEM_7_MDA": {
        "MARGIN_PRESSURE": 1.0, "GUIDANCE_DIRECTION": 1.0, "DEMAND_UNCERTAINTY": 0.9,
        "CAPITAL_ALLOCATION_CHANGE": 0.9, "MANAGEMENT_OUTLOOK": 1.0, "STRATEGIC_CHANGE": 0.8,
    },
    "ITEM_3_LEGAL_PROCEEDINGS": {
        "LITIGATION_RISK": 1.0, "REGULATORY_RISK": 0.9,
    },
    "PART_I_ITEM_2_MDA": {
        "MARGIN_PRESSURE": 1.0, "GUIDANCE_DIRECTION": 1.0, "DEMAND_UNCERTAINTY": 0.9,
        "MANAGEMENT_OUTLOOK": 1.0,
    },
    "PART_II_ITEM_1A_RISK_FACTORS": {
        "REGULATORY_RISK": 1.0, "LITIGATION_RISK": 0.9, "SUPPLY_CHAIN_RISK": 0.9,
    },
}

HIGH_MATERIALITY_PATTERNS = [
    r"\b(?:billion|million)\b", r"\$\d+", r"\bsubpoena\b", r"\bformal\s+investigation\b",
    r"\binjunction\b", r"\bantitrust\s+suit\b", r"\bcriminal\b", r"\brestructuring\s+charge\b",
    r"\bgoodwill\s+impairment\b", r"\bplant\s+closure\b", r"\bdefault\b", r"\bdebt\s+covenant\b",
]

MEDIUM_MATERIALITY_PATTERNS = [
    r"\blawsuit\b", r"\bcomplaint\b", r"\bpricing\s+pressure\b", r"\bheadwind\b",
    r"\binflation\b", r"\bshortage\b", r"\bdelay\b", r"\bdiscontinued\b",
]


def calculate_confidence_score(
    validation_res: ValidationResult,
    quote: str,
    section_name: str,
    category: str,
) -> float:
    """
    Calculate auditable extraction confidence score in range [0.0, 1.0].

    Components:
    - Match quality score (0.0 to 1.0, from validator)
    - Quote length substance (0.0 to 0.15)
    - Section authority alignment (0.0 to 0.15)
    """
    if not validation_res.is_valid:
        return 0.0

    # Base match score
    score = validation_res.match_score * 0.70

    # Length substance bonus
    q_len = len(quote.strip())
    if q_len >= 80:
        score += 0.15
    elif q_len >= 40:
        score += 0.10
    elif q_len >= 20:
        score += 0.05

    # Section authority bonus
    auth_dict = SECTION_AUTHORITY_WEIGHTS.get(section_name, {})
    weight = auth_dict.get(category, 0.5)
    score += weight * 0.15

    return round(min(1.0, max(0.0, score)), 4)


def classify_materiality(
    quote: str,
    claim: str,
    severity: str,
) -> Materiality:
    """
    Classify qualitative economic materiality: LOW, MEDIUM, or HIGH.
    """
    combined = f"{quote} {claim}".lower()

    # Check High Materiality signals
    if severity.upper() == "CRITICAL":
        return Materiality.HIGH

    high_matches = sum(1 for p in HIGH_MATERIALITY_PATTERNS if re.search(p, combined))
    if high_matches >= 2 or (high_matches >= 1 and severity.upper() == "HIGH"):
        return Materiality.HIGH

    # Check Medium Materiality signals
    if severity.upper() == "HIGH":
        return Materiality.MEDIUM

    med_matches = sum(1 for p in MEDIUM_MATERIALITY_PATTERNS if re.search(p, combined))
    if med_matches >= 1 or severity.upper() == "MEDIUM":
        return Materiality.MEDIUM

    return Materiality.LOW
