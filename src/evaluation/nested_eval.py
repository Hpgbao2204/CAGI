"""Danh gia leave-one-incident-out VOI chon threshold dung cach (Tuan 6,
theo yeu cau nguoi dung + configs/model.yaml::threshold_policy):
"Threshold khong duoc chon tren test — chon tren validation trong moi fold".

Thiet ke: voi moi outer fold (group bi giu lai lam test), threshold duoc
chon tren OUT-OF-FOLD PREDICTIONS cua CHINH tap train (qua 1 vong inner
leave-one-group-out NAM TRONG 10 group con lai) — khong bao gio dung du
lieu cua outer test fold de chon threshold. Model CUOI CUNG cho outer fold
do duoc fit lai tren TOAN BO 10 group train (khong chi 9 group cua 1 inner
fold), roi du doan tren outer test fold voi threshold da chon.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut

from src.evaluation.metrics import false_alerts_per_1000, macro_f1, pr_auc, recall_at_fpr

# Thu tu uu tien nhan khi dedupe (Buoc 1, Tuan 6 rerun v2) - KHOP DUNG thu tu
# ma generate_prefixes() cu (buggy, setdefault) tung dung de chon nhan "song
# sot" khi nhieu moc trung length: ratio truoc k, ratio nho truoc lon. Chi
# de co 1 quy tac xac dinh/tai lap duoc khi chon dong nao giu lai trong 1
# nhom trung (trajectory_id, prefix_len) - feature cua ca nhom giong het
# nhau (cung length) nen chon dong nao KHONG anh huong ket qua, chi anh
# huong nhan hien thi trong meta cot prefix_label.
DEDUPE_LABEL_PRIORITY = ["ratio_25", "ratio_50", "ratio_75", "ratio_100", "k_2", "k_3", "k_5", "k_7"]


def dedupe_pooled_prefixes(
    df: "pd.DataFrame",
    id_col: str = "source_id",
    length_col: str = "prefix_len",
    label_col: str = "prefix_label",
    priority: Sequence[str] = DEDUPE_LABEL_PRIORITY,
) -> "pd.DataFrame":
    """Dedupe TRUOC KHI POOL nhieu prefix bucket vao 1 tap train (thiet ke RQ1
    goc - Tuan 6): sau khi sua bug generate_prefixes() (Tuan 7, xem
    rq2_ratio100_fix_v1.md), 1 do dai (length) co the mang NHIEU nhan
    (vd trajectory 3-action: ca ratio_75 VA ratio_100 deu = length 3).
    Voi RQ2 (danh gia TUNG bucket rieng) dieu nay dung (moi bucket la 1 model
    rieng). Nhung voi RQ1 (pool CA 8 bucket vao 1 tap train/eval mot fold)
    giu nguyen ca 4 nhan se lam CUNG 1 diem quan sat that (cung feature, vi
    cung length) bi dem lap 2-4 lan mot cach gia tao - thien vi trong so cho
    trajectory ngan (hard-negative da so rat ngan).

    QUAN TRONG: mac dinh dung `source_id` lam khoa dinh danh TRAJECTORY VAT
    LY, KHONG PHAI `trajectory_id` — trong codebase nay `trajectory_id` thuc
    ra la TEN INCIDENT/GROUP (vd "paraluni_2022", gan trong
    src/pipeline/incident_pipeline.py: `trajectory_id=incident_id`), dung
    chung cho MOI hard-negative candidate cua incident do (vd 47 hard-negative
    khac nhau cua "paraluni_2022" deu co cung trajectory_id="paraluni_2022").
    Neu dedupe theo `trajectory_id` se GOM NHAM nhieu trajectory VAT LY KHAC
    NHAU (khac source_id, khac feature that) chi vi chung trung prefix_len -
    da phat hien bug nay khi thu (2681 dong -> chi con 277, qua manh tay).
    `source_id` moi la dinh danh DUY NHAT cho 1 trajectory vat ly (525 gia
    tri distinct, khop dung so trajectory that trong load_rq1_trajectories).

    Nhom theo (source_id, prefix_len) - MOI NHOM la 1 diem quan sat that,
    giu dung 1 dong. Chon dong giu lai theo `priority` (mac dinh khop thu tu
    ma logic setdefault CU tung dung, de dedupe co the tai lap/doi chieu duoc
    voi ket qua truoc khi sua bug) - feature cua ca nhom deu giong het nhau
    (cung length) nen viec chon dong nao KHONG anh huong gia tri feature,
    chi anh huong nhan `prefix_label` hien thi trong meta.
    """
    df = df.reset_index(drop=True)
    prio_map = {label: i for i, label in enumerate(priority)}
    prio = df[label_col].map(prio_map).fillna(len(priority))

    keep_positions: List[int] = []
    seen = set()
    order = prio.sort_values(kind="stable").index  # duyet theo uu tien tang dan
    for pos in order:
        key = (df.at[pos, id_col], df.at[pos, length_col])
        if key not in seen:
            seen.add(key)
            keep_positions.append(pos)
    keep_positions.sort()  # giu thu tu dong ban dau (khong xao tron)
    return df.loc[keep_positions].reset_index(drop=True)


def select_threshold(y_true: np.ndarray, y_prob: np.ndarray, target_fpr: float = 0.01) -> float:
    """Chon threshold theo dung configs/model.yaml::threshold_policy ("FPR<=1%
    hoac max 10 false alerts/1000") — threshold THAP NHAT sao cho FPR<=target_fpr
    (toi da hoa recall trong rang buoc FPR). Neu KHONG co threshold nao dat
    FPR<=target_fpr (mau qua nho/qua nhieu positive trong validation), fallback
    ve threshold toi da hoa macro-F1 — ghi ro day la fallback, khong phai
    chinh sach chinh.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    if len(set(y_true.tolist())) < 2:
        return 0.5  # khong the danh gia FPR neu chi co 1 lop trong validation

    candidate_thresholds = np.unique(np.concatenate([y_prob, [0.0, 1.0]]))
    best_threshold = None
    best_recall = -1.0
    for t in candidate_thresholds:
        y_pred = (y_prob >= t).astype(int)
        neg_mask = y_true == 0
        fpr = float((y_pred[neg_mask] == 1).sum()) / neg_mask.sum() if neg_mask.sum() else 0.0
        if fpr <= target_fpr:
            pos_mask = y_true == 1
            recall = float((y_pred[pos_mask] == 1).sum()) / pos_mask.sum() if pos_mask.sum() else 0.0
            if recall > best_recall:
                best_recall = recall
                best_threshold = float(t)

    if best_threshold is not None:
        return best_threshold

    # Fallback: khong dat FPR<=target o bat ky threshold nao -> chon theo macro-F1
    best_f1 = -1.0
    best_threshold = 0.5
    for t in candidate_thresholds:
        f1 = macro_f1(y_true, y_prob, threshold=float(t))
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(t)
    return best_threshold


def _fit_calibrator(y_inner: np.ndarray, prob_inner: np.ndarray, method: str):
    """Fit calibrator TREN INNER-TRAIN OOF (cung du lieu dung chon threshold
    — khong bao gio dung outer test). "platt" = logistic regression 1 chieu
    tren logit(prob) (Platt scaling kinh dien); "isotonic" = IsotonicRegression
    (non-parametric, don dieu tang) — ca 2 tu sklearn.
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression

    if len(set(y_inner.tolist())) < 2:
        return None  # khong the calibrate voi 1 lop duy nhat trong inner-OOF
    if method == "isotonic":
        cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        cal.fit(prob_inner, y_inner)
        return cal
    if method == "platt":
        eps = 1e-6
        p_clipped = np.clip(prob_inner, eps, 1 - eps)
        logit = np.log(p_clipped / (1 - p_clipped)).reshape(-1, 1)
        cal = LogisticRegression()
        cal.fit(logit, y_inner)
        return cal
    raise ValueError(f"method khong hop le: {method} (chi ho tro 'platt'/'isotonic')")


def _apply_calibrator(cal, prob: np.ndarray, method: str) -> np.ndarray:
    if cal is None:
        return np.full(len(prob), np.nan)
    if method == "isotonic":
        return cal.predict(prob)
    eps = 1e-6
    p_clipped = np.clip(prob, eps, 1 - eps)
    logit = np.log(p_clipped / (1 - p_clipped)).reshape(-1, 1)
    return cal.predict_proba(logit)[:, 1]


def evaluate_model_nested(
    model_factory: Callable[[], object],
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    target_fpr: float = 0.01,
    calibration: Optional[str] = None,
) -> Dict:
    """Outer leave-one-group-out (group=incident/parent_incident). Voi moi
    outer fold: inner leave-one-group-out TRONG tap train de sinh OOF
    predictions -> chon threshold tren OOF train (KHONG dung outer test) ->
    fit model CUOI tren TOAN BO train -> du doan + danh gia tren outer test
    voi threshold da chon.

    `calibration` (mac dinh None = KHONG hieu chinh, giu nguyen hanh vi cu,
    khong pha vo bat ky ham goi cu nao): "platt" hoac "isotonic" - neu dat,
    fit calibrator TREN inner-train OOF (cung du lieu voi buoc chon
    threshold, KHONG BAO GIO dung outer test de fit calibrator) roi ap dung
    len prob_test - ket qua luu them vao "oof_prob_calibrated".

    Tra ve dict: "fold_rows" (list per-fold metric), "oof_prob" (Series,
    index khop X, gia tri = xac suat du doan LUC group cua dong do la outer
    test — dung cho bootstrap CI muc incident), "oof_threshold" (Series
    cung do dai, threshold da ap dung cho dong do), "oof_prob_calibrated"
    (Series, NaN neu calibration=None hoac fold khong calibrate duoc).
    """
    outer_logo = LeaveOneGroupOut()
    fold_rows: List[Dict] = []
    oof_prob = np.full(len(y), np.nan)
    oof_threshold = np.full(len(y), np.nan)
    oof_prob_calibrated = np.full(len(y), np.nan)

    for train_idx, test_idx in outer_logo.split(X, y, groups=groups):
        held_out_group = groups.iloc[test_idx].iloc[0]
        X_train, y_train, g_train = X.iloc[train_idx], y.iloc[train_idx], groups.iloc[train_idx]
        X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]

        # --- Inner LOGO tren train de sinh OOF-train predictions (chon threshold) ---
        inner_logo = LeaveOneGroupOut()
        inner_oof_prob = np.full(len(y_train), np.nan)
        for inner_train_idx, inner_val_idx in inner_logo.split(X_train, y_train, groups=g_train):
            inner_model = model_factory()
            inner_model.fit(
                X_train.iloc[inner_train_idx], y_train.iloc[inner_train_idx], g_train.iloc[inner_train_idx],
            )
            inner_oof_prob[inner_val_idx] = inner_model.predict_proba(X_train.iloc[inner_val_idx])

        valid_inner = ~np.isnan(inner_oof_prob)
        threshold = select_threshold(
            y_train.to_numpy()[valid_inner], inner_oof_prob[valid_inner], target_fpr=target_fpr,
        )

        # --- Fit model CUOI tren TOAN BO train, du doan tren outer test ---
        final_model = model_factory()
        final_model.fit(X_train, y_train, g_train)
        prob_test = final_model.predict_proba(X_test)

        oof_prob[test_idx] = prob_test
        oof_threshold[test_idx] = threshold

        if calibration is not None:
            cal = _fit_calibrator(y_train.to_numpy()[valid_inner], inner_oof_prob[valid_inner], calibration)
            oof_prob_calibrated[test_idx] = _apply_calibrator(cal, prob_test, calibration)

        y_test_arr = y_test.to_numpy()
        fold_rows.append({
            "held_out_group": held_out_group,
            "n_val_rows": len(test_idx),
            "n_val_positive": int((y_test_arr == 1).sum()),
            "n_val_negative": int((y_test_arr == 0).sum()),
            "threshold_chosen_on_inner_train_oof": threshold,
            "pr_auc": pr_auc(y_test_arr, prob_test),
            f"recall_at_fpr_{target_fpr}": recall_at_fpr(y_test_arr, prob_test, max_fpr=target_fpr),
            "macro_f1": macro_f1(y_test_arr, prob_test, threshold=threshold),
            "false_alerts_per_1000": false_alerts_per_1000(y_test_arr, prob_test, threshold=threshold),
        })

    return {
        "fold_rows": fold_rows,
        "oof_prob": pd.Series(oof_prob, index=X.index),
        "oof_threshold": pd.Series(oof_threshold, index=X.index),
        "oof_prob_calibrated": pd.Series(oof_prob_calibrated, index=X.index),
    }


def bootstrap_incident_level(
    y_true: Sequence[int], y_prob: Sequence[float], incident_ids: Sequence, metric_fn: Callable,
    n_boot: int = 1000, alpha: float = 0.05, random_state: int = 42,
) -> Dict[str, float]:
    """Bootstrap CI resample O MUC INCIDENT (khong phai row/prefix) — vi cac
    prefix cung 1 incident KHONG doc lap voi nhau (xem research_questions.md
    muc 6.7)."""
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
        return {"point": point_estimate, "ci_low": float("nan"), "ci_high": float("nan"), "n_boot_valid": 0}
    scores = np.asarray(scores)
    return {
        "point": point_estimate,
        "ci_low": float(np.percentile(scores, 100 * alpha / 2)),
        "ci_high": float(np.percentile(scores, 100 * (1 - alpha / 2))),
        "n_boot_valid": len(scores),
    }


def per_incident_metric(
    y_true: Sequence[int], y_prob: Sequence[float], incident_ids: Sequence, metric_fn: Callable,
) -> Dict[str, float]:
    """Tra ve {incident_id: metric} — dung cho so sanh paired (Wilcoxon/bootstrap
    tren hieu so) giua 2 model."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    incident_ids = np.asarray(incident_ids)
    out = {}
    for inc in np.unique(incident_ids):
        mask = incident_ids == inc
        out[str(inc)] = metric_fn(y_true[mask], y_prob[mask])
    return out
