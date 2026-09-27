"""Leave-one-incident-out (LOIO) engine dung cho toan bo thuc nghiem cua
paper (scripts/run_experiments.py).

Khac src/evaluation/nested_eval.py::evaluate_model_nested o 2 diem:
1. Giu lai model + calibrator cua TUNG fold de cham diem prefix bat ky cua
   incident bi giu lai (online scoring moi k, moc thoi gian, stress test) —
   khong chi cac dong checkpoint co san.
2. Vong inner LOIO (sinh OOF tren tap train de fit Platt) la tuy chon, bo
   qua duoc cho baseline khong can calibration (nhanh hon).

Khong dong nao cua incident bi giu lai duoc dung de fit model, calibrator
hay chon nguong.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score

_EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), _EPS, 1 - _EPS)
    return np.log(p / (1 - p)).reshape(-1, 1)


class PlattCalibrator:
    def fit(self, prob: np.ndarray, y: np.ndarray) -> "PlattCalibrator":
        self.lr = LogisticRegression().fit(_logit(prob), np.asarray(y))
        return self

    def __call__(self, prob: np.ndarray) -> np.ndarray:
        return self.lr.predict_proba(_logit(prob))[:, 1]


class IsotonicCalibrator:
    def fit(self, prob: np.ndarray, y: np.ndarray) -> "IsotonicCalibrator":
        from sklearn.isotonic import IsotonicRegression
        self.iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(prob, y)
        return self

    def __call__(self, prob: np.ndarray) -> np.ndarray:
        return self.iso.predict(prob)


@dataclass
class FoldModel:
    group: str
    model: object
    calibrators: Dict[str, Callable] = field(default_factory=dict)

    def score(self, X: pd.DataFrame, method: Optional[str] = "platt") -> np.ndarray:
        raw = self.model.predict_proba(X)
        if method is None or method == "raw":
            return raw
        return self.calibrators[method](raw)


@dataclass
class LOIOResult:
    oof_raw: pd.Series
    oof_cal: Dict[str, pd.Series]
    folds: Dict[str, FoldModel]


def run_loio(
    factory: Callable[[], object],
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    calibrate: bool = False,
) -> LOIOResult:
    oof_raw = pd.Series(np.nan, index=X.index)
    oof_cal = {m: pd.Series(np.nan, index=X.index) for m in ("platt", "isotonic")} if calibrate else {}
    folds: Dict[str, FoldModel] = {}
    uniq = list(pd.unique(groups))
    for g in uniq:
        te = groups == g
        tr = ~te
        Xtr, ytr, gtr = X[tr], y[tr], groups[tr]
        model = factory().fit(Xtr, ytr, gtr)
        fm = FoldModel(group=str(g), model=model)
        raw_te = model.predict_proba(X[te])
        oof_raw[te] = raw_te
        if calibrate:
            inner = np.full(len(ytr), np.nan)
            for h in pd.unique(gtr):
                vi = (gtr == h).to_numpy()
                m = factory().fit(Xtr[~vi], ytr[~vi], gtr[~vi])
                inner[vi] = m.predict_proba(Xtr[vi])
            fm.calibrators["platt"] = PlattCalibrator().fit(inner, ytr.to_numpy())
            fm.calibrators["isotonic"] = IsotonicCalibrator().fit(inner, ytr.to_numpy())
            for mth, cal in fm.calibrators.items():
                oof_cal[mth][te] = cal(raw_te)
        folds[str(g)] = fm
    return LOIOResult(oof_raw=oof_raw, oof_cal=oof_cal, folds=folds)


# ----------------------------------------------------------------------
# Metric + bootstrap muc incident
# ----------------------------------------------------------------------
def ap(y, p) -> float:
    y = np.asarray(y)
    if y.min() == y.max():
        return float("nan")
    return float(average_precision_score(y, p))


def _incident_index(groups: Sequence) -> Dict[str, np.ndarray]:
    g = np.asarray(groups)
    return {k: np.where(g == k)[0] for k in np.unique(g)}


def bootstrap_metric(y, p, groups, metric=ap, n_boot: int = 2000, seed: int = 42) -> Dict[str, float]:
    y, p = np.asarray(y), np.asarray(p)
    idx_by = _incident_index(groups)
    keys = list(idx_by)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        s = rng.choice(len(keys), size=len(keys), replace=True)
        idx = np.concatenate([idx_by[keys[i]] for i in s])
        v = metric(y[idx], p[idx])
        if not np.isnan(v):
            vals.append(v)
    vals = np.asarray(vals)
    return {"point": metric(y, p), "ci_low": float(np.percentile(vals, 2.5)),
            "ci_high": float(np.percentile(vals, 97.5)), "n_boot_valid": int(len(vals))}


def paired_bootstrap(y, pa, pb, groups, metric=ap, n_boot: int = 2000, seed: int = 42) -> Dict[str, float]:
    """Resample 15 incident co hoan lai; thong ke = metric(A) - metric(B) tren
    CUNG tap dong resample. p hai phia = 2*min(P[d<=0], P[d>=0]) (Todo T1)."""
    y, pa, pb = np.asarray(y), np.asarray(pa), np.asarray(pb)
    idx_by = _incident_index(groups)
    keys = list(idx_by)
    rng = np.random.default_rng(seed)
    d = []
    for _ in range(n_boot):
        s = rng.choice(len(keys), size=len(keys), replace=True)
        idx = np.concatenate([idx_by[keys[i]] for i in s])
        a, b = metric(y[idx], pa[idx]), metric(y[idx], pb[idx])
        if not (np.isnan(a) or np.isnan(b)):
            d.append(a - b)
    d = np.asarray(d)
    p_two = min(1.0, 2 * min(float(np.mean(d <= 0)), float(np.mean(d >= 0))))
    return {"point": metric(y, pa) - metric(y, pb), "boot_mean": float(d.mean()),
            "ci_low": float(np.percentile(d, 2.5)), "ci_high": float(np.percentile(d, 97.5)),
            "p_value": p_two, "n_boot_valid": int(len(d))}


def brier(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def ece(y, p, n_bins: int = 10) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, bins[1:-1]), 0, n_bins - 1)
    out = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            out += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(out)


def per_incident(y, p, groups, metric=ap) -> Dict[str, float]:
    y, p, g = np.asarray(y), np.asarray(p), np.asarray(groups)
    return {str(k): metric(y[g == k], p[g == k]) for k in np.unique(g)}
