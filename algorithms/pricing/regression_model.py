"""Linear regression implemented from scratch via gradient descent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class LinearRegressionGD:
    learning_rate: float = 0.001
    epochs: int = 1200

    def __post_init__(self) -> None:
        self.weights: List[float] = []
        self.bias: float = 0.0

    def fit(self, X: List[List[float]], y: List[float]) -> None:
        if not X:
            return
        n_samples = len(X)
        n_features = len(X[0])
        self.weights = [0.0 for _ in range(n_features)]
        self.bias = 0.0

        for _ in range(self.epochs):
            grad_w = [0.0 for _ in range(n_features)]
            grad_b = 0.0

            for i in range(n_samples):
                pred = self._dot(X[i], self.weights) + self.bias
                err = pred - y[i]
                for j in range(n_features):
                    grad_w[j] += (2.0 / n_samples) * err * X[i][j]
                grad_b += (2.0 / n_samples) * err

            for j in range(n_features):
                self.weights[j] -= self.learning_rate * grad_w[j]
            self.bias -= self.learning_rate * grad_b

    def predict_one(self, x: List[float]) -> float:
        return self._dot(x, self.weights) + self.bias

    def evaluate_mae(self, X: List[List[float]], y: List[float]) -> float:
        if not X:
            return 0.0
        total = 0.0
        for i in range(len(X)):
            total += abs(self.predict_one(X[i]) - y[i])
        return total / len(X)

    @staticmethod
    def _dot(a: List[float], b: List[float]) -> float:
        return sum(ai * bi for ai, bi in zip(a, b))

    def to_dict(self) -> dict:
        return {"weights": self.weights, "bias": self.bias}

    @classmethod
    def from_dict(cls, payload: dict) -> "LinearRegressionGD":
        model = cls()
        model.weights = [float(w) for w in payload.get("weights", [])]
        model.bias = float(payload.get("bias", 0.0))
        return model


def train_test_split(X: List[List[float]], y: List[float], test_ratio: float = 0.2) -> Tuple:
    n = len(X)
    split = max(1, int(n * (1.0 - test_ratio)))
    return X[:split], X[split:], y[:split], y[split:]
