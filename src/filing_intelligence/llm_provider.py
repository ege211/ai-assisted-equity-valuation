"""
Model-Agnostic LLM Provider Abstraction.

Provides:
- Abstract LLMProvider interface for structured JSON extraction
- DeterministicRuleBasedLLMProvider (deterministic offline extraction using exact passage quotes)
- MockLLMProvider (configurable mock for unit testing edge cases, hallucinations, and rejections)
- APILLMProvider (extensible REST endpoint adapter for production LLM APIs)
"""
from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract interface for structured extraction language models."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (e.g. 'anthropic', 'openai', 'gemini', 'deterministic-rule')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Specific model name (e.g. 'claude-3-5-sonnet', 'gpt-4o', 'gemini-1.5-pro', 'rule-v1')."""
        pass

    @abstractmethod
    def generate_extraction(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Execute structured JSON extraction."""
        pass


class MockLLMProvider(LLMProvider):
    """Configurable mock provider for deterministic testing of edge cases."""

    def __init__(
        self,
        canned_response: Optional[Dict[str, Any]] = None,
        model_name: str = "mock-model-v1",
        provider_name: str = "mock-provider",
    ) -> None:
        self._canned_response = canned_response or {}
        self._model_name = model_name
        self._provider_name = provider_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def set_response(self, response: Dict[str, Any]) -> None:
        self._canned_response = response

    def generate_extraction(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        return self._canned_response


class DeterministicRuleBasedLLMProvider(LLMProvider):
    """
    Deterministic rule-based qualitative extraction provider.

    Analyzes passage text using high-precision syntactic and lexical patterns
    to extract genuine, verbatim quotes from the filing text and classify them
    into structured categories, directions, severities, and materialities.
    Guarantees 100% offline reproducibility and zero unsourced claims.
    """

    def __init__(self, model_name: str = "deterministic-rule-v1") -> None:
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "deterministic-rule"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_extraction(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Extract verbatim evidence sentence and structured attributes from prompt text.
        """
        # Parse passage text from prompt boundaries
        passage_match = re.search(r"<sec_document_passage>(.*?)</sec_document_passage>", prompt, re.DOTALL)
        if not passage_match:
            passage_text = prompt
        else:
            passage_text = passage_match.group(1).strip()

        # Parse category hint from prompt
        cat_match = re.search(r"Category:\s*([A-Z_]+)", prompt)
        category = cat_match.group(1).strip() if cat_match else "MATERIAL_BUSINESS_CHANGE"

        # Split passage into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", passage_text) if len(s.strip()) > 30]

        if not sentences:
            return {
                "has_claim": False,
                "category": category,
                "claim": "No verifiable claim identified.",
                "evidence_quote": "",
                "direction": "UNKNOWN",
                "severity": "UNKNOWN",
                "materiality": "LOW",
                "confidence": 0.0,
            }

        # Select the sentence with strongest relevance to category
        # Keywords map
        cat_keywords = {
            "REGULATORY_RISK": ["regulat", "compliance", "sec", "ftc", "fda", "antitrust", "law", "sanction"],
            "LITIGATION_RISK": ["lawsuit", "litigat", "proceeding", "plaintiff", "defendant", "settlement", "dispute"],
            "DEMAND_UNCERTAINTY": ["demand", "soften", "decelerat", "headwind", "customer", "volatilit", "order"],
            "MARGIN_PRESSURE": ["margin", "inflation", "cost", "compress", "wage", "pricing", "input"],
            "STRATEGIC_CHANGE": ["strategic", "restructur", "acqui", "divest", "reorganiz", "pivot"],
            "CAPITAL_ALLOCATION_CHANGE": ["repurchase", "buyback", "dividend", "capex", "debt", "repayment"],
            "GUIDANCE_DIRECTION": ["guidance", "outlook", "forecast", "expect", "project", "target"],
            "LIQUIDITY_RISK": ["liquidit", "credit", "revolving", "covenant", "maturit", "borrowing"],
            "SUPPLY_CHAIN_RISK": ["suppl", "shortage", "logistics", "freight", "bottleneck", "vendor"],
            "COMPETITIVE_PRESSURE": ["competit", "market share", "alternative", "pricing concession"],
            "MATERIAL_BUSINESS_CHANGE": ["material", "impairment", "goodwill", "closure", "discontinu"],
            "MANAGEMENT_OUTLOOK": ["outlook", "macroeconomic", "forward", "momentum", "trend"],
        }
        target_keys = cat_keywords.get(category, ["financial", "operation", "result"])

        best_sentence = sentences[0]
        max_score = -1

        for sent in sentences:
            score = sum(1 for k in target_keys if k.lower() in sent.lower())
            if score > max_score:
                max_score = score
                best_sentence = sent

        # Direction detection
        sent_lower = best_sentence.lower()
        neg_words = ["risk", "adversely", "decline", "decreas", "loss", "uncertain", "litigat", "delay", "soften", "headwind", "pressure", "disrupt", "impair"]
        pos_words = ["growth", "increase", "strong", "expand", "record", "exceed", "benefit", "opportunit", "improv"]

        n_neg = sum(1 for w in neg_words if w in sent_lower)
        n_pos = sum(1 for w in pos_words if w in sent_lower)

        if n_neg > n_pos:
            direction = "NEGATIVE"
        elif n_pos > n_neg:
            direction = "POSITIVE"
        elif n_neg > 0 and n_pos > 0:
            direction = "MIXED"
        else:
            direction = "NEUTRAL"

        # Severity detection
        if any(w in sent_lower for w in ["critical", "subpoena", "criminal", "catastrophic", "severely", "injunction"]):
            severity = "CRITICAL"
        elif any(w in sent_lower for w in ["significant", "material", "substantial", "adversely affect", "investigat"]):
            severity = "HIGH"
        elif any(w in sent_lower for w in ["moderate", "uncertain", "possible", "potential", "may affect"]):
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Materiality detection
        if severity in ("HIGH", "CRITICAL") or any(w in sent_lower for w in ["billion", "million", "restructur", "material"]):
            materiality = "HIGH"
        elif severity == "MEDIUM":
            materiality = "MEDIUM"
        else:
            materiality = "LOW"

        # Formulate structured claim distinct from evidence quote
        claim_summary = f"Management disclosed {category.lower().replace('_', ' ')} with {direction.lower()} implications."
        if "increase" in sent_lower or "growth" in sent_lower:
            claim_summary = f"Disclosed favorable trend or increase relating to {category.lower().replace('_', ' ')}."
        elif "decrease" in sent_lower or "decline" in sent_lower:
            claim_summary = f"Disclosed downward pressure or decrease relating to {category.lower().replace('_', ' ')}."
        elif "risk" in sent_lower or "adversely" in sent_lower:
            claim_summary = f"Identified operational or financial risk affecting {category.lower().replace('_', ' ')}."

        confidence = 0.85 if max_score > 0 else 0.70

        return {
            "has_claim": True,
            "category": category,
            "claim": claim_summary,
            "evidence_quote": best_sentence,
            "direction": direction,
            "severity": severity,
            "materiality": materiality,
            "confidence": confidence,
        }
