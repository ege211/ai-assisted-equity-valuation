"""
Model A (Baseline Model) for Phase 6.

Constructs and evaluates benchmark models utilizing ONLY conventional
financial statement and market features available at information date T.
"""
from typing import Any, List, Optional

from src.research.math_utils import LinearRegressionOLS, LogisticRegression, RidgeRegression


class BaselineModel:
    """
    Model A: Uses conventional fundamental, accounting, and market data only.
    Zero qualitative or filing-derived information.
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

    def fit(self, X: List[List[float]], y: List[float]) -> "BaselineModel":
        self.model.fit(X, y)
        return self

    def predict(self, X: List[List[float]]) -> List[float]:
        if self.is_classification:
            # Return probabilities for continuous ranking / AUC
            return self.model.predict_proba(X)
        return self.model.predict(X)
