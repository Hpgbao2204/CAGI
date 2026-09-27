"""Tests for src/evaluation/loio.py: incident isolation, calibration fitted on
training folds only, pooled-prefix dedupe and the bootstrap statistics."""
import numpy as np
import pandas as pd

from src.evaluation.loio import (
    ap, bootstrap_metric, brier, dedupe_pooled_prefixes, ece, paired_bootstrap, per_incident, run_loio,
)


class _RecordingModel:
    """Predicts the training positive rate and records which groups it saw."""

    seen = []

    def fit(self, X, y, groups):
        _RecordingModel.seen.append(set(groups))
        self.rate = float(np.mean(y))
        return self

    def predict_proba(self, X):
        return np.full(len(X), self.rate) + X["x"].to_numpy() * 1e-3


def _toy(n_groups=5, per_group=20, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_groups):
        for i in range(per_group):
            y = int(i < 3)
            rows.append({"group": f"g{g}", "x": rng.normal(y * 2.0, 1.0), "y": y})
    df = pd.DataFrame(rows)
    return df[["x"]], df["y"], df["group"]


def test_held_out_group_never_used_for_fitting():
    X, y, g = _toy()
    _RecordingModel.seen = []
    res = run_loio(_RecordingModel, X, y, g, calibrate=True)
    assert set(res.folds) == set(g.unique())
    # outer fits + inner fits: none may contain the group they are scored on
    outer_fits = [s for s in _RecordingModel.seen if len(s) == g.nunique() - 1]
    assert len(outer_fits) >= g.nunique()
    assert all(len(s) < g.nunique() for s in _RecordingModel.seen)
    assert res.oof_raw.notna().all()
    for m in ("platt", "isotonic"):
        assert res.oof_cal[m].between(0, 1).all()


def test_platt_is_monotone():
    X, y, g = _toy()
    res = run_loio(_RecordingModel, X, y, g, calibrate=True)
    cal = next(iter(res.folds.values())).calibrators["platt"]
    p = np.linspace(0.01, 0.99, 50)
    assert np.all(np.diff(cal(p)) >= 0)


def test_dedupe_keeps_one_row_per_source_and_length():
    df = pd.DataFrame({
        "source_id": ["a", "a", "a", "b", "b"],
        "prefix_len": [2, 2, 3, 2, 4],
        "prefix_label": ["ratio_75", "ratio_100", "k_3", "k_2", "ratio_100"],
    })
    out = dedupe_pooled_prefixes(df)
    assert len(out) == 4
    assert not out.duplicated(["source_id", "prefix_len"]).any()
    assert out[(out.source_id == "a") & (out.prefix_len == 2)].prefix_label.item() == "ratio_75"


def test_bootstrap_and_paired_bootstrap():
    X, y, g = _toy(n_groups=8)
    good = X["x"].to_numpy()
    noise = np.random.default_rng(1).random(len(y))
    b = bootstrap_metric(y, good, g, n_boot=300)
    assert b["ci_low"] <= b["point"] <= b["ci_high"]
    pr = paired_bootstrap(y, good, noise, g, n_boot=300)
    assert pr["point"] > 0 and pr["ci_low"] > 0 and pr["p_value"] < 0.05
    same = paired_bootstrap(y, good, good, g, n_boot=100)
    assert same["point"] == 0 and same["p_value"] == 1.0


def test_metrics_basic():
    y = np.array([0, 0, 1, 1])
    assert ap(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert np.isnan(ap(np.zeros(3), np.ones(3)))
    assert brier(y, y.astype(float)) == 0.0
    assert ece(y, y.astype(float)) == 0.0
    assert set(per_incident(y, [0.1, 0.2, 0.8, 0.9], ["a", "a", "b", "b"])) == {"a", "b"}
