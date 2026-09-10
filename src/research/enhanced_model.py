"""
Model B (Filing-Enhanced Model) for Phase 6.

Constructs and evaluates enhanced models utilizing conventional features PLUS
SEC filing-derived qualitative features under identical hyperparameters, samples,
and cross-validation protocols.
"""
from typing import Any, List, Optional

from src.research.math_utils import LinearRegressionOLS, LogisticRegression, RidgeRegression


class EnhancedModel:
    """
    Model B: Uses conventional features + SEC filing-derived qualitative features.
    The ONLY difference between Model A and Model B is the inclusion of filing features.
    """

    def __init__(
        self,
        model_type: str = "RidgeRegression",
        alpha: float = 1.0,
        is_classification: bool = False,
    ) -> None:
        self.model_type = model_type
        self.alpha = float(alpha)
        self.is_classification = is_classification

        if is_classification:
            self.model: Any = LogisticRegression(alpha=self.alpha)
        elif model_type == "LinearRegressionOLS":
            self.model = LinearRegressionOLS()
        else:
            self.model = RidgeRegression(alpha=self.alpha)

    def fit(self, X: List[List[float]], y: List[float]) -> "EnhancedModel":
        self.model.fit(X, y)
        return self

    def predict(self, X: List[List[float]]) -> List[float]:
        if self.is_classification:
            return self.model.predict_proba(X)
        return self.model.predict(X)
