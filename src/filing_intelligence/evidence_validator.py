"""
Evidence Verification Engine.

Enforces the foundational project rule: NO UNSOURCED AI CLAIMS.
Verifies that every proposed evidence quote exists verbatim or near-verbatim
in the underlying source filing passage. If verification fails, the extraction
is strictly REJECTED.
"""
import difflib
import logging
import re
from typing import Optional, Tuple

from src.filing_intelligence.schemas import ValidationResult, ValidationStatus

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text for fuzzy whitespace/punctuation comparison."""
    if not text:
        return ""
    # Lowercase, unescape quotes, replace unicode dashes and spaces
    t = text.lower().replace("\u00a0", " ").replace("\u200b", "")
    t = t.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    # Collapse whitespace and strip punctuation edges
    t = re.sub(r"\s+", " ", t).strip()
    return t


class EvidenceValidator:
    """Rigorous validator verifying quotes against source SEC filing passages."""

    def __init__(self, min_fuzzy_ratio: float = 0.92) -> None:
        self.min_fuzzy_ratio = min_fuzzy_ratio

    def validate_quote(
        self,
        evidence_quote: Optional[str],
        source_passage: str,
        full_document_text: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate that the proposed evidence quote is genuinely present in the source text.

        Parameters
        ----------
        evidence_quote : Optional[str]
            The quote generated/extracted by the LLM.
        source_passage : str
            The specific text chunk given to the LLM.
        full_document_text : Optional[str]
            The entire document text as fallback verification.

        Returns
        -------
        ValidationResult
            Validation outcome, status, offsets, and diagnostic reason.
        """
        if not evidence_quote or not evidence_quote.strip():
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.NO_EVIDENCE,
                reason="Proposed evidence quote is empty or missing.",
                match_score=0.0,
            )

        quote = evidence_quote.strip()

        # 1. Exact Substring Search in Passage
        exact_idx = source_passage.find(quote)
        if exact_idx != -1:
            return ValidationResult(
                is_valid=True,
                status=ValidationStatus.VALIDATED,
                reason="Exact substring match verified in passage.",
                matched_quote=quote,
                start_char=exact_idx,
                end_char=exact_idx + len(quote),
                match_score=1.0,
            )

        # 2. Exact Substring Search in Full Document (if passage boundary truncated)
        if full_document_text:
            doc_idx = full_document_text.find(quote)
            if doc_idx != -1:
                return ValidationResult(
                    is_valid=True,
                    status=ValidationStatus.VALIDATED,
                    reason="Exact substring match verified in document.",
                    matched_quote=quote,
                    start_char=doc_idx,
                    end_char=doc_idx + len(quote),
                    match_score=1.0,
                )

        # 3. Normalized Punctuation / Whitespace Match in Passage
        norm_quote = _normalize_text(quote)
        norm_passage = _normalize_text(source_passage)

        if norm_quote in norm_passage:
            norm_idx = norm_passage.find(norm_quote)
            return ValidationResult(
                is_valid=True,
                status=ValidationStatus.VALIDATED,
                reason="Normalized punctuation/whitespace match verified.",
                matched_quote=quote,
                start_char=norm_idx,
                end_char=norm_idx + len(norm_quote),
                match_score=0.98,
            )

        # 4. Fuzzy Substring Matching for Minor Token Boundary Splitting
        # Look for best matching window of similar character length in passage
        q_len = len(norm_quote)
        best_ratio = 0.0
        best_window = ""

        words = norm_passage.split()
        q_words_len = len(norm_quote.split())

        for i in range(max(1, len(words) - q_words_len + 1)):
            window = " ".join(words[i:i + q_words_len])
            matcher = difflib.SequenceMatcher(None, norm_quote, window)
            ratio = matcher.ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_window = window

        if best_ratio >= self.min_fuzzy_ratio:
            return ValidationResult(
                is_valid=True,
                status=ValidationStatus.VALIDATED,
                reason=f"Near-exact fuzzy match verified (score: {best_ratio:.3f}).",
                matched_quote=best_window,
                match_score=best_ratio,
            )

        # 5. Mandatory Rejection: Quote Cannot Be Sourced
        return ValidationResult(
            is_valid=False,
            status=ValidationStatus.REJECTED,
            reason=f"REJECTED: Proposed quote not found in source text (best similarity: {best_ratio:.2f} < {self.min_fuzzy_ratio:.2f}). Fabricated or hallucinated quote.",
            match_score=best_ratio,
        )
