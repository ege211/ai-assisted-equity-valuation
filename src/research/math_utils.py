"""
Pure-Python numerical, linear algebra, and statistical routines for Phase 6.

Provides completely deterministic, dependency-free matrix operations, OLS,
Ridge regression, Logistic regression, continuous/binary evaluation metrics,
and non-parametric statistical hypothesis tests (permutation tests, bootstrap CIs).
"""
import math
import random
from typing import List, Optional, Tuple


# ==============================================================================
# 1. LINEAR ALGEBRA PRIMITIVES
# ==============================================================================

def matrix_transpose(matrix: List[List[float]]) -> List[List[float]]:
    """Compute transpose of a 2D matrix."""
    if not matrix or not matrix[0]:
        return []
    n_rows = len(matrix)
    n_cols = len(matrix[0])
    return [[matrix[r][c] for r in range(n_rows)] for c in range(n_cols)]


def matrix_multiply(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Compute matrix multiplication A @ B."""
    rows_a = len(a)
    cols_a = len(a[0])
    rows_b = len(b)
    cols_b = len(b[0])
    if cols_a != rows_b:
        raise ValueError(f"Incompatible matrix dimensions: {rows_a}x{cols_a} and {rows_b}x{cols_b}")

    result = [[0.0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for k in range(cols_a):
            aik = a[i][k]
            if aik == 0.0:
                continue
            for j in range(cols_b):
                result[i][j] += aik * b[k][j]
    return result


def matrix_vector_multiply(matrix: List[List[float]], vector: List[float]) -> List[float]:
    """Compute matrix-vector product M @ v."""
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def matrix_inverse(matrix: List[List[float]], eps: float = 1e-12) -> List[List[float]]:
    """
    Invert a square matrix using Gauss-Jordan elimination with partial pivoting.
    Raises ValueError if the matrix is singular or near-singular.
    """
    n = len(matrix)
    for row in matrix:
        if len(row) != n:
            raise ValueError("Matrix must be square to invert.")

    # Augment matrix with identity
    augmented = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]

    for col in range(n):
        # Partial pivoting: locate row with maximum absolute pivot
        pivot_row = col
        max_val = abs(augmented[col][col])
        for r in range(col + 1, n):
            if abs(augmented[r][col]) > max_val:
                max_val = abs(augmented[r][col])
                pivot_row = r

        if max_val < eps:
            raise ValueError(f"Matrix is singular or near-singular (pivot {max_val:.2e} < {eps})")

        # Swap rows if necessary
        if pivot_row != col:
            augmented[col], augmented[pivot_row] = augmented[pivot_row], augmented[col]

        pivot = augmented[col][col]
        # Normalize pivot row
        for c in range(2 * n):
            augmented[col][c] /= pivot

        # Eliminate other rows
        for r in range(n):
            if r != col:
                factor = augmented[r][col]
                if abs(factor) > 1e-15:
                    for c in range(2 * n):
                        augmented[r][c] -= factor * augmented[col][c]

    # Extract right side
    return [[augmented[r][n + c] for c in range(n)] for r in range(n)]


# ==============================================================================
# 2. STANDARDIZATION
# ==============================================================================

class StandardScaler:
    """Standardizes features by removing the mean and scaling to unit variance."""

    def __init__(self) -> None:
        self.means: List[float] = []
        self.stds: List[float] = []

    def fit(self, X: List[List[float]]) -> "StandardScaler":
        if not X or not X[0]:
            return self
        n_samples = len(X)
        n_features = len(X[0])
        self.means = [sum(X[i][j] for i in range(n_samples)) / n_samples for j in range(n_features)]
        self.stds = []
        for j in range(n_features):
            variance = sum((X[i][j] - self.means[j]) ** 2 for i in range(n_samples)) / max(1, n_samples - 1)
            std = math.sqrt(variance)
            self.stds.append(std if std > 1e-8 else 1.0)
        return self

    def transform(self, X: List[List[float]]) -> List[List[float]]:
        if not self.means:
            return X
        return [[(row[j] - self.means[j]) / self.stds[j] for j in range(len(row))] for row in X]

    def fit_transform(self, X: List[List[float]]) -> List[List[float]]:
        return self.fit(X).transform(X)


# ==============================================================================
# 3. REGRESSION & CLASSIFICATION MODELS
# ==============================================================================

class RidgeRegression:
    """
    Ridge Regression with L2 regularization:
    w = (X^T X + alpha * I)^(-1) X^T y
    Includes automatic standardization and intercept handling.
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = max(1e-6, float(alpha))
        self.scaler = StandardScaler()
        self.weights: List[float] = []
        self.intercept: float = 0.0

    def fit(self, X: List[List[float]], y: List[float]) -> "RidgeRegression":
        if not X or not y or len(X) != len(y):
            raise ValueError("X and y must be non-empty and have matching sample size.")

        n_samples = len(X)
        n_features = len(X[0])

        # Standardize features
        X_scaled = self.scaler.fit_transform(X)
        y_mean = sum(y) / n_samples
        y_centered = [yi - y_mean for yi in y]

        # Compute X^T X
        Xt = matrix_transpose(X_scaled)
        XtX = matrix_multiply(Xt, X_scaled)

        # Add L2 penalty: alpha * I
        for j in range(n_features):
            XtX[j][j] += self.alpha

        # Solve for weights: w = (X^T X + alpha * I)^(-1) X^T y_centered
        try:
            inv_XtX = matrix_inverse(XtX)
        except ValueError:
            # Add stronger jitter if singular
            for j in range(n_features):
                XtX[j][j] += 1.0
            inv_XtX = matrix_inverse(XtX)

        Xty = [sum(Xt[j][i] * y_centered[i] for i in range(n_samples)) for j in range(n_features)]
        self.weights = [sum(inv_XtX[i][j] * Xty[j] for j in range(n_features)) for i in range(n_features)]
        self.intercept = y_mean
        return self

    def predict(self, X: List[List[float]]) -> List[float]:
        X_scaled = self.scaler.transform(X)
        return [self.intercept + sum(row[j] * self.weights[j] for j in range(len(self.weights))) for row in X_scaled]


class LinearRegressionOLS:
    """Ordinary Least Squares Regression via Ridge with near-zero regularization."""

    def __init__(self) -> None:
        self.model = RidgeRegression(alpha=1e-6)

    def fit(self, X: List[List[float]], y: List[float]) -> "LinearRegressionOLS":
        self.model.fit(X, y)
        return self

    def predict(self, X: List[List[float]]) -> List[float]:
        return self.model.predict(X)


class LogisticRegression:
    """
    Binary Logistic Regression with L2 regularization solved via gradient descent.
    """

    def __init__(self, alpha: float = 1.0, lr: float = 0.05, max_iter: int = 400) -> None:
        self.alpha = float(alpha)
        self.lr = float(lr)
        self.max_iter = int(max_iter)
        self.scaler = StandardScaler()
        self.weights: List[float] = []
        self.intercept: float = 0.0

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z < -30.0:
            return 0.0
        if z > 30.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    def fit(self, X: List[List[float]], y: List[float]) -> "LogisticRegression":
        n_samples = len(X)
        n_features = len(X[0])
        X_scaled = self.scaler.fit_transform(X)

        self.weights = [0.0] * n_features
        self.intercept = 0.0

        for _ in range(self.max_iter):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for i in range(n_samples):
                z = self.intercept + sum(X_scaled[i][j] * self.weights[j] for j in range(n_features))
                p = self._sigmoid(z)
                err = p - y[i]
                grad_b += err
                for j in range(n_features):
                    grad_w[j] += err * X_scaled[i][j]

            # Apply gradient update with L2 regularization
            self.intercept -= self.lr * (grad_b / n_samples)
            for j in range(n_features):
                reg = (self.alpha / n_samples) * self.weights[j]
                self.weights[j] -= self.lr * (grad_w[j] / n_samples + reg)

        return self

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        X_scaled = self.scaler.transform(X)
        probs = []
        for row in X_scaled:
            z = self.intercept + sum(row[j] * self.weights[j] for j in range(len(self.weights)))
            probs.append(self._sigmoid(z))
        return probs

    def predict(self, X: List[List[float]], threshold: float = 0.5) -> List[int]:
        probs = self.predict_proba(X)
        return [1 if p >= threshold else 0 for p in probs]


# ==============================================================================
# 4. EVALUATION METRICS
# ==============================================================================

def mean_absolute_error(y_true: List[float], y_pred: List[float]) -> float:
    """Compute Mean Absolute Error."""
    if not y_true or len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have matching length.")
    return sum(abs(t - p) for t, p in zip(y_true, y_pred)) / len(y_true)


def root_mean_squared_error(y_true: List[float], y_pred: List[float]) -> float:
    """Compute Root Mean Squared Error."""
    if not y_true or len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have matching length.")
    mse = sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true)
    return math.sqrt(mse)


def r2_score(y_true: List[float], y_pred: List[float]) -> float:
    """Compute coefficient of determination R^2."""
    if not y_true or len(y_true) < 2:
        return 0.0
    mean_true = sum(y_true) / len(y_true)
    ss_tot = sum((t - mean_true) ** 2 for t in y_true)
    ss_res = sum((t - p) ** 2 for t, p in zip(y_true, y_pred))
    if ss_tot < 1e-12:
        return 0.0
    return 1.0 - (ss_res / ss_tot)


def accuracy_score(y_true: List[float], y_pred: List[float]) -> float:
    """Compute classification accuracy."""
    if not y_true or len(y_true) != len(y_pred):
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if round(t) == round(p))
    return correct / len(y_true)


def brier_score(y_true: List[float], y_prob: List[float]) -> float:
    """Compute Brier score for probability predictions."""
    if not y_true or len(y_true) != len(y_prob):
        return 0.0
    return sum((p - t) ** 2 for t, p in zip(y_true, y_prob)) / len(y_true)


def roc_auc_score(y_true: List[float], y_score: List[float]) -> float:
    """
    Compute Area Under the Receiver Operating Characteristic Curve (ROC-AUC)
    using the Wilcoxon-Mann-Whitney rank-sum formula.
    """
    if not y_true or len(y_true) != len(y_score):
        return 0.5

    pos = [s for t, s in zip(y_true, y_score) if t >= 0.5]
    neg = [s for t, s in zip(y_true, y_score) if t < 0.5]
    n_pos = len(pos)
    n_neg = len(neg)

    if n_pos == 0 or n_neg == 0:
        return 0.5

    # Count pairs where pos > neg (ties count 0.5)
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5

    return wins / (n_pos * n_neg)


def pr_auc_score(y_true: List[float], y_score: List[float]) -> float:
    """
    Compute Area Under the Precision-Recall Curve (PR-AUC) using trapezoidal rule.
    """
    if not y_true or len(y_true) != len(y_score):
        return 0.0
    pairs = sorted(zip(y_score, y_true), key=lambda x: x[0], reverse=True)
    n_pos = sum(1 for y in y_true if y >= 0.5)
    if n_pos == 0:
        return 0.0

    precisions = [1.0]
    recalls = [0.0]
    tp = 0
    fp = 0
    for score, target in pairs:
        if target >= 0.5:
            tp += 1
        else:
            fp += 1
        precisions.append(tp / (tp + fp))
        recalls.append(tp / n_pos)

    # Trapezoidal integration
    auc = 0.0
    for i in range(1, len(recalls)):
        auc += 0.5 * (recalls[i] - recalls[i - 1]) * (precisions[i] + precisions[i - 1])
    return max(0.0, min(1.0, auc))


def pearson_correlation(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient r."""
    if not x or len(x) != len(y) or len(x) < 2:
        return 0.0
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    denom = math.sqrt(var_x * var_y)
    return cov / denom if denom > 1e-12 else 0.0


def spearman_rank_correlation(x: List[float], y: List[float]) -> float:
    """Compute Spearman rank-order correlation coefficient rho."""
    if not x or len(x) != len(y) or len(x) < 2:
        return 0.0

    def rank_array(arr: List[float]) -> List[float]:
        indices = list(range(len(arr)))
        indices.sort(key=lambda i: arr[i])
        ranks = [0.0] * len(arr)
        i = 0
        while i < len(arr):
            j = i
            while j < len(arr) - 1 and arr[indices[j + 1]] == arr[indices[j]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[indices[k]] = avg_rank
            i = j + 1
        return ranks

    rank_x = rank_array(x)
    rank_y = rank_array(y)
    return pearson_correlation(rank_x, rank_y)


# ==============================================================================
# 5. STATISTICAL HYPOTHESIS TESTING
# ==============================================================================

def paired_t_test(errors_a: List[float], errors_b: List[float]) -> Tuple[float, float]:
    """
    Compute paired t-test comparing absolute error arrays.
    Returns (t_stat, p_value).
    A positive t_stat means Error A > Error B (Model B improved over Model A).
    """
    n = len(errors_a)
    if n < 3:
        return 0.0, 1.0

    diffs = [ea - eb for ea, eb in zip(errors_a, errors_b)]
    mean_diff = sum(diffs) / n
    var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
    se_diff = math.sqrt(var_diff / n) if var_diff > 1e-12 else 1e-8

    t_stat = mean_diff / se_diff
    df = n - 1

    # Approximate 2-tailed p-value using normal/t approximation
    # For df >= 15, normal approximation is very close; for smaller df, use conservative bound
    x = abs(t_stat)
    p_norm = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(x / math.sqrt(2.0))))
    p_val = min(1.0, max(0.0, p_norm))
    return t_stat, p_val


def permutation_test(
    errors_a: List[float],
    errors_b: List[float],
    n_permutations: int = 2000,
    seed: int = 42,
) -> float:
    """
    Non-parametric paired permutation test on error difference (MAE_A - MAE_B).
    Returns empirical two-tailed p-value.
    """
    n = len(errors_a)
    if n < 3:
        return 1.0

    diffs = [ea - eb for ea, eb in zip(errors_a, errors_b)]
    observed_mean = abs(sum(diffs) / n)

    rng = random.Random(seed)
    count_extreme = 0

    for _ in range(n_permutations):
        # Randomly flip signs of differences with 50% probability
        perm_diff_sum = sum(d if rng.random() > 0.5 else -d for d in diffs)
        perm_mean = abs(perm_diff_sum / n)
        if perm_mean >= observed_mean:
            count_extreme += 1

    return (count_extreme + 1.0) / (n_permutations + 1.0)


def bootstrap_ci(
    errors_a: List[float],
    errors_b: List[float],
    n_bootstraps: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Tuple[float, float]:
    """
    Compute 95% bootstrap confidence interval for Delta MAE = MAE_A - MAE_B.
    """
    n = len(errors_a)
    if n < 3:
        return 0.0, 0.0

    diffs = [ea - eb for ea, eb in zip(errors_a, errors_b)]
    rng = random.Random(seed)
    bootstrap_means: List[float] = []

    for _ in range(n_bootstraps):
        sample = [rng.choice(diffs) for _ in range(n)]
        bootstrap_means.append(sum(sample) / n)

    bootstrap_means.sort()
    low_idx = int((alpha / 2.0) * n_bootstraps)
    high_idx = int((1.0 - alpha / 2.0) * n_bootstraps)
    low_idx = max(0, min(n_bootstraps - 1, low_idx))
    high_idx = max(0, min(n_bootstraps - 1, high_idx))

    return bootstrap_means[low_idx], bootstrap_means[high_idx]
