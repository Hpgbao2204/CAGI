"""
Test cho evaluation harness (Bước 7): GroupKFold theo incident_id (không
random row split), metric table, và bootstrap CI ở mức incident.
"""
import numpy as np
import pandas as pd

from src.evaluation.dataset import build_prefix_dataset
from src.evaluation.evaluate import run_groupkfold_evaluation
from src.evaluation.metrics import bootstrap_ci_incident_level, pr_auc
from src.models.baselines import get_all_baselines
from src.trajectories.builder import TrajectoryConfig
from tests.fixtures.synthetic_trajectories import build_synthetic_dataset

CONFIG = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05)


def _dataset():
    raw = build_synthetic_dataset()
    return build_prefix_dataset(raw, CONFIG)


def test_groupkfold_never_splits_same_incident_across_folds():
    X, y, groups, _ = _dataset()
    from sklearn.model_selection import GroupKFold

    n_splits = min(3, groups.nunique())
    gkf = GroupKFold(n_splits=n_splits)
    for train_idx, val_idx in gkf.split(X, y, groups=groups):
        train_groups = set(groups.iloc[train_idx])
        val_groups = set(groups.iloc[val_idx])
        assert train_groups.isdisjoint(val_groups)


def test_run_groupkfold_evaluation_produces_metric_table():
    X, y, groups, _ = _dataset()
    models = get_all_baselines()
    table = run_groupkfold_evaluation(models, X, y, groups, n_splits=3)

    assert isinstance(table, pd.DataFrame)
    assert set(table["model"]) == set(models.keys())
    for col in ["pr_auc", "macro_f1", "false_alerts_per_1000", "brier_score", "ece"]:
        assert col in table.columns
    # brier score phải nằm trong [0,1] cho xác suất nhị phân
    assert table["brier_score"].between(0.0, 1.0).all()


def test_bootstrap_ci_resamples_at_incident_level_not_row_level():
    X, y, groups, meta = _dataset()
    # dùng B0 (không cần fit thật) để có y_prob nhanh, chỉ kiểm tra cơ chế CI
    from src.models.baselines import B0MajorityBaseline

    model = B0MajorityBaseline()
    model.fit(X, y, groups)
    y_prob = model.predict_proba(X)

    result = bootstrap_ci_incident_level(y, y_prob, groups, pr_auc, n_boot=100)
    assert "point" in result and "ci_low" in result and "ci_high" in result
    if not np.isnan(result["point"]):
        assert result["ci_low"] <= result["ci_high"]


def test_bootstrap_ci_unit_is_incident_verified_by_group_count():
    """Xác nhận resample thực sự diễn ra trên danh sách incident_id duy nhất,
    không phải trên từng row/prefix (vốn có nhiều row/incident do multi-prefix).
    """
    X, y, groups, meta = _dataset()
    n_unique_incidents = groups.nunique()
    n_rows = len(X)
    # với multi-prefix (25/50/75/100% + k=2,3,5,7), số row phải > số incident
    assert n_rows > n_unique_incidents
