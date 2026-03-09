"""Train demand prediction LSTM model.

Usage:
    python train_demand_model.py

Output:
    models/demand_lstm.pkl
"""

from __future__ import annotations

import os
from typing import Tuple

import joblib
import numpy as np
from dotenv import load_dotenv


def _load_training_data() -> Tuple[np.ndarray, np.ndarray]:
    """Load demand series from DB if possible, otherwise synthesize realistic data."""
    try:
        import databases

        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            database = databases.Database(db_url)

            import asyncio

            async def _fetch():
                await database.connect()
                rows = await database.fetch_all(
                    "SELECT hour, day_of_week, predicted_requests AS rides, zone_id "
                    "FROM predicted_demand ORDER BY created_at ASC LIMIT 4000"
                )
                await database.disconnect()
                return rows

            rows = asyncio.run(_fetch())
            if rows:
                X = []
                y = []
                for r in rows:
                    h = int(r["hour"])
                    dow = int(r["day_of_week"])
                    prev = float(r["rides"])
                    cluster = float(int(r["zone_id"] or 0) % 10)
                    X.append([h, dow, prev, cluster])
                    y.append(prev)
                return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)
    except Exception:
        pass

    rng = np.random.default_rng(2026)
    n = 3000
    hours = rng.integers(0, 24, n).astype(np.float32)
    dows = rng.integers(0, 7, n).astype(np.float32)
    prev_rides = rng.integers(8, 60, n).astype(np.float32)
    clusters = rng.integers(0, 8, n).astype(np.float32)

    peak = ((hours >= 7) & (hours <= 9)) | ((hours >= 17) & (hours <= 20))
    weekday = dows <= 4
    y = prev_rides * (1.0 + 0.35 * peak.astype(np.float32) + 0.1 * weekday.astype(np.float32))
    y += rng.normal(0.0, 3.0, n).astype(np.float32)
    y = np.clip(y, 1.0, None)

    X = np.column_stack([hours, dows, prev_rides, clusters]).astype(np.float32)
    return X, y.astype(np.float32)


def train_and_save() -> str:
    try:
        import torch
        import torch.nn as nn
    except Exception as exc:
        raise RuntimeError(
            "PyTorch is required for LSTM training. Install dependencies from requirements.txt"
        ) from exc

    X, y = _load_training_data()

    # Standardize inputs for stable LSTM convergence.
    mu = X.mean(axis=0)
    sigma = X.std(axis=0) + 1e-6
    Xn = (X - mu) / sigma

    seq_len = 6
    if len(Xn) <= seq_len + 1:
        raise RuntimeError("Insufficient data for sequence training")

    seq_X = []
    seq_y = []
    for i in range(seq_len, len(Xn)):
        seq_X.append(Xn[i - seq_len : i])
        seq_y.append(y[i])

    Xt = torch.tensor(np.asarray(seq_X), dtype=torch.float32)
    yt = torch.tensor(np.asarray(seq_y), dtype=torch.float32)

    class DemandLSTM(nn.Module):
        def __init__(self, feature_size: int) -> None:
            super().__init__()
            self.lstm = nn.LSTM(input_size=feature_size, hidden_size=48, num_layers=1, batch_first=True)
            self.head = nn.Sequential(nn.Linear(48, 24), nn.ReLU(), nn.Linear(24, 1))

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(1)

    model = DemandLSTM(feature_size=Xt.shape[-1])
    loss_fn = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    model.train()
    for _ in range(45):
        optimizer.zero_grad()
        pred = model(Xt)
        loss = loss_fn(pred, yt)
        loss.backward()
        optimizer.step()

    os.makedirs("models", exist_ok=True)
    out_path = "models/demand_lstm.pkl"
    artifact = {
        "state_dict": model.state_dict(),
        "feature_mean": mu,
        "feature_std": sigma,
        "seq_len": seq_len,
        "feature_size": int(Xt.shape[-1]),
    }
    joblib.dump(artifact, out_path)
    return out_path


if __name__ == "__main__":
    load_dotenv()
    path = train_and_save()
    print(f"Demand LSTM model saved: {path}")
