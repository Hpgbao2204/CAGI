"""
Metrics cho evaluation — xem research_questions.md (bảng tóm tắt metric theo RQ).

PR-AUC, Macro-F1, Recall@FPR<=1%, false alerts/1000 trajectories, lead time
(median/IQR), Brier score/ECE cho calibration. Bootstrap CI PHẢI resample ở
mức incident_id, không phải mức prefix/row — các prefix của cùng incident
không độc lập (xem threat_model.md mục 8).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    roc_curve,
)


def pr_auc(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    y_true = np.asarray(y_true)
    if len(set(y_true.tolist())) < 2:
        return float("nan")
    return float(average_precision_score(y_true, y_prob))


def macro_f1(y_true: Sequence[int], y_prob: Sequence[float], threshold: float = 0.5) -> float:
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    return float(f1_score(y_true, y_pred, average="macro", zero_division=0))


def recall_at_fpr(y_true: Sequence[int], y_prob: Sequence[float], max_fpr: float = 0.01) -> float:
    """Recall (TPR) tại ngưỡng lớn nhất mà FPR <= max_fpr."""
    y_true = np.asarray(y_true)
    if len(set(y_true.tolist())) < 2:
        return float("nan")
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    valid = fpr <= max_fpr
    if not valid.any():
        return 0.0
    return float(tpr[valid].max())


def false_alerts_per_1000(y_true: Sequence[int], y_prob: Sequence[float], threshold: float) -> float:
    y_true = np.asarray(y_true)
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    n = len(y_true)
    if n == 0:
        return 0.0
    false_alerts = int(((y_pred == 1) & (y_true == 0)).sum())
    return float(false_alerts) / n * 1000.0


def brier_score(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(y_true: Sequence[int], y_prob: Sequence[float], n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < n_bins - 1 else y_prob <= hi)
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_prob[mask].mean()
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def lead_time_stats(lead_times: Sequence[float]) -> Dict[str, float]:
    """lead_times: số action (hoặc giờ) còn lại trước endpoint tại thời điểm
    alert được kích hoạt lần đầu, tính riêng cho các trajectory dương tính đã
    được phát hiện đúng (true positive).
    """
    arr = np.asarray([lt for lt in lead_times if lt is not None], dtype=float)
    if len(arr) == 0:
        return {"median": float("nan"), "iqr_low": float("nan"), "iqr_high": float("nan")}
    return {
        "median": float(np.median(arr)),
        "iqr_low": float(np.percentile(arr, 25)),
        "iqr_high": float(np.percentile(arr, 75)),
    }


def bootstrap_ci_incident_level(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    incident_ids: Sequence,
    metric_fn: Callable[[Sequence[int], Sequence[float]], float],
    n_boot: int = 500,
    alpha: float = 0.05,
    random_state: Optional[int] = 42,
) -> Dict[str, float]:
    """Bootstrap CI resample Ở MỨC INCIDENT (không phải mức row/prefix).

    Mỗi vòng lặp: resample-with-replacement danh sách incident_id duy nhất,
    rồi gộp lại toàn bộ row (mọi prefix) thuộc các incident được chọn ->
    tính metric trên tập gộp đó.
    """
    rng = np.random.default_rng(random_state)
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    incident_ids = np.asarray(incident_ids)
    unique_incidents = np.unique(incident_ids)

    point_estimate = metric_fn(y_true, y_prob)

    scores = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_incidents, size=len(unique_incidents), replace=True)
        idx = np.concatenate([np.where(incident_ids == inc)[0] for inc in sampled])
        score = metric_fn(y_true[idx], y_prob[idx])
        if not np.isnan(score):
            scores.append(score)

    if not scores:
        return {"point": point_estimate, "ci_low": float("nan"), "ci_high": float("nan")}

    scores = np.asarray(scores)
    lo = float(np.percentile(scores, 100 * alpha / 2))
    hi = float(np.percentile(scores, 100 * (1 - alpha / 2)))
    return {"point": point_estimate, "ci_low": lo, "ci_high": hi}
