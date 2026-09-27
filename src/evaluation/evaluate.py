"""
Evaluation harness — Bước 7. Split bằng GroupKFold (group=incident_id),
KHÔNG random row split. Metric: PR-AUC, Macro-F1, Recall@FPR<=1%,
false alerts/1000, calibration (Brier/ECE). CI bootstrap ở mức incident
(src/evaluation/metrics.py::bootstrap_ci_incident_level).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from src.evaluation.metrics import (
    brier_score,
    expected_calibration_error,
    false_alerts_per_1000,
    macro_f1,
    pr_auc,
    recall_at_fpr,
)
from src.models.baselines import BaselineModel


def run_groupkfold_evaluation(
    models: Dict[str, BaselineModel],
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int = 3,
    threshold: float = 0.5,
    max_fpr: float = 0.01,
) -> pd.DataFrame:
    """Chạy GroupKFold (group=incident_id) cho từng model, trả về bảng metric
    theo từng model, tính trên out-of-fold predictions gộp lại (giữ đúng
    unit-of-analysis: 1 incident chỉ ở validation của đúng 1 fold).

    n_splits bị giới hạn tự động theo số incident duy nhất để không lỗi khi
    dataset nhỏ (vd synthetic test với ít incident).
    """
    unique_groups = groups.nunique()
    n_splits_eff = max(2, min(n_splits, unique_groups))
    gkf = GroupKFold(n_splits=n_splits_eff)

    results = []
    for model_name, model in models.items():
        oof_prob = np.full(len(y), np.nan)
        for train_idx, val_idx in gkf.split(X, y, groups=groups):
            # đảm bảo không leak: incident trong val không xuất hiện trong train
            train_groups = set(groups.iloc[train_idx])
            val_groups = set(groups.iloc[val_idx])
            assert train_groups.isdisjoint(val_groups), "GroupKFold leakage: incident xuất hiện ở cả train và val"

            fold_model = _clone(model)
            fold_model.fit(X.iloc[train_idx], y.iloc[train_idx], groups.iloc[train_idx])
            oof_prob[val_idx] = fold_model.predict_proba(X.iloc[val_idx])

        row = {
            "model": model_name,
            "pr_auc": pr_auc(y, oof_prob),
            "macro_f1": macro_f1(y, oof_prob, threshold=threshold),
            f"recall_at_fpr_{max_fpr}": recall_at_fpr(y, oof_prob, max_fpr=max_fpr),
            "false_alerts_per_1000": false_alerts_per_1000(y, oof_prob, threshold=threshold),
            "brier_score": brier_score(y, oof_prob),
            "ece": expected_calibration_error(y, oof_prob),
        }
        results.append(row)

    return pd.DataFrame(results)


def _clone(model: BaselineModel) -> BaselineModel:
    """Clone nhẹ (fresh instance) để tránh rò rỉ trạng thái fit giữa các fold."""
    return type(model)()
