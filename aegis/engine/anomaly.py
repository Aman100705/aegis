"""ML anomaly layer. An IsolationForest catches odd combinations of signals the
hand-written rules don't enumerate. It *augments* the rules; the rules remain
the explainable backbone. Trained at startup on synthetic 'normal' behavior so
the service is self-contained and deterministic."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from .types import Features


class AnomalyModel:
    def __init__(self, model: IsolationForest, offset: float, scale: float) -> None:
        self._model = model
        self._offset = offset
        self._scale = scale

    @classmethod
    def train_default(cls, *, seed: int = 42, n: int = 2000) -> AnomalyModel:
        """Fit on synthetic 'normal' events: low geo-velocity, known device/IP,
        usual hour, near-zero amount z-score, low velocity, no failed logins."""
        rng = np.random.default_rng(seed)
        normal = np.column_stack(
            [
                np.clip(rng.normal(0.02, 0.02, n), 0, 1),   # geo velocity (scaled)
                rng.binomial(1, 0.05, n),                   # new device (rare)
                rng.binomial(1, 0.08, n),                   # new ip (rare)
                rng.binomial(1, 0.05, n),                   # unusual hour (rare)
                np.clip(np.abs(rng.normal(0.05, 0.05, n)), 0, 1),  # amount z (scaled)
                np.clip(np.abs(rng.normal(0.05, 0.05, n)), 0, 1),  # velocity (scaled)
                np.zeros(n),                                # failed attempts
            ]
        )
        model = IsolationForest(n_estimators=120, contamination=0.02, random_state=seed)
        model.fit(normal)
        scores = model.score_samples(normal)
        offset = float(scores.mean())
        scale = float(scores.std()) or 1.0
        return cls(model, offset, scale)

    def anomaly_score(self, features: Features) -> float:
        """Return an anomaly score in [0, 1] (higher = more anomalous)."""
        x = np.array([features.vector()], dtype=float)
        raw = float(self._model.score_samples(x)[0])
        # Lower score_samples => more anomalous. Convert to a 0..1 anomaly scale.
        z = (self._offset - raw) / self._scale
        return float(max(0.0, min(1.0, z / 4.0)))
