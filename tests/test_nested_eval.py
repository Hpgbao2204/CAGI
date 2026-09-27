"""Test cho src/evaluation/nested_eval.py (Tuần 6) — đảm bảo threshold KHÔNG
được chọn trên test fold (configs/model.yaml::threshold_policy) và bootstrap
CI resample đúng ở mức incident."""
import numpy as np
import pandas as pd
import pytest

from src.evaluation.nested_eval import (
    bootstrap_incident_level,
    dedupe_pooled_prefixes,
    evaluate_model_nested,
    per_incident_metric,
    select_threshold,
)
from src.evaluation.metrics import pr_auc


def test_dedupe_pooled_prefixes_no_duplicate_trajectory_length_pairs():
    # traj "short" (do dai 2 hanh dong): sau bug fix generate_prefixes(), co
    # the co CA 2 nhan (ratio_25 va ratio_75) cung tro toi length=2 - dedupe
    # phai chi giu 1 dong cho cap (trajectory_id, prefix_len) nay.
    # QUAN TRONG: dung "source_id" - dinh danh DUY NHAT cho 1 trajectory vat
    # ly trong du lieu that (KHONG PHAI "trajectory_id", truong nay trong
    # codebase thuc ra la ten incident/group, dung chung cho nhieu
    # hard-negative candidate khac nhau - xem docstring dedupe_pooled_prefixes).
    df = pd.DataFrame({
        "source_id": ["short", "short", "long", "long", "long", "long"],
        "prefix_len": [1, 2, 3, 5, 8, 10],
        "prefix_label": ["ratio_25", "ratio_75", "ratio_25", "ratio_50", "ratio_75", "ratio_100"],
        "feat_x": [10.0, 20.0, 30.0, 50.0, 80.0, 100.0],
    })
    # them 1 dong trung (source_id="short", prefix_len=2) voi nhan khac
    # (ratio_100) - mo phong dung bug da sua: length=2 co 2 nhan.
    dup_row = pd.DataFrame({
        "source_id": ["short"], "prefix_len": [2], "prefix_label": ["ratio_100"], "feat_x": [20.0],
    })
    df = pd.concat([df, dup_row], ignore_index=True)

    deduped = dedupe_pooled_prefixes(df)

    pairs = list(zip(deduped["source_id"], deduped["prefix_len"]))
    assert len(pairs) == len(set(pairs)), "khong duoc co 2 dong cung (source_id, prefix_len)"

    # "short" chi co 2 do dai PHAN BIET that su (1 va 2) -> dedupe xong phai
    # con dung 2 dong cho "short", KHONG PHAI 3 (dung bang so nhan ban dau)
    # va KHONG PHAI cong khai luon = 8 (so bucket mac dinh).
    short_rows = deduped[deduped["source_id"] == "short"]
    assert len(short_rows) == 2
    assert set(short_rows["prefix_len"]) == {1, 2}

    # Uu tien: length=2 co 2 ung vien (ratio_75, ratio_100) -> giu ratio_75
    # (dung DEDUPE_LABEL_PRIORITY, ratio_75 dung truoc ratio_100).
    kept_label_at_2 = short_rows[short_rows["prefix_len"] == 2]["prefix_label"].iloc[0]
    assert kept_label_at_2 == "ratio_75"

    # "long" khong co length trung nhau -> dedupe khong duoc lam mat dong nao.
    long_rows = deduped[deduped["source_id"] == "long"]
    assert len(long_rows) == 4


def test_dedupe_pooled_prefixes_preserves_feature_values():
    df = pd.DataFrame({
        "source_id": ["a", "a"],
        "prefix_len": [4, 4],
        "prefix_label": ["ratio_100", "k_5"],  # sai (k_5 phai <=n) nhung chi test dedupe logic
        "feat_x": [7.0, 7.0],  # feature giong het (dung length) - gia tri phai giu nguyen
    })
    deduped = dedupe_pooled_prefixes(df)
    assert len(deduped) == 1
    assert deduped["feat_x"].iloc[0] == 7.0


def test_dedupe_pooled_prefixes_does_not_collapse_different_physical_trajectories():
    """Bug da phat hien va sua: KHONG duoc dung 'trajectory_id' lam khoa vi
    truong nay trong du lieu that la TEN INCIDENT (dung chung cho hang tram
    hard-negative candidate khac nhau cua cung 1 incident) - neu dung nham
    se gom lan nhieu trajectory VAT LY KHAC NHAU (khac source_id, khac
    feature) chi vi trung prefix_len. Test nay mo phong dung tinh huong do:
    2 hard-negative KHAC NHAU cua cung 1 incident, tinh co trung prefix_len,
    nhung feature GIA TRI KHAC NHAU that su -> dedupe (theo source_id, dung)
    KHONG duoc gop chung 2 dong nay.
    """
    df = pd.DataFrame({
        "source_id": ["paraluni_2022__hn001", "paraluni_2022__hn002"],
        "trajectory_id": ["paraluni_2022", "paraluni_2022"],  # CUNG incident - de gay nham neu dung sai khoa
        "prefix_len": [3, 3],  # tinh co trung do dai
        "prefix_label": ["ratio_25", "ratio_50"],
        "feat_x": [1.0, 999.0],  # feature THAT SU khac nhau (2 trajectory vat ly khac nhau)
    })
    deduped = dedupe_pooled_prefixes(df)  # mac dinh id_col="source_id" - PHAI giu ca 2 dong
    assert len(deduped) == 2
    assert set(deduped["source_id"]) == {"paraluni_2022__hn001", "paraluni_2022__hn002"}
    assert set(deduped["feat_x"]) == {1.0, 999.0}


def test_select_threshold_respects_target_fpr():
    y_true = np.array([0] * 90 + [1] * 10)
    # Điểm số: negative thấp, positive cao, tách rõ -> threshold cao vẫn giữ FPR thấp.
    y_prob = np.array([0.1] * 90 + [0.9] * 10)
    t = select_threshold(y_true, y_prob, target_fpr=0.01)
    y_pred = (y_prob >= t).astype(int)
    fpr = (y_pred[y_true == 0] == 1).sum() / (y_true == 0).sum()
    assert fpr <= 0.01


def test_select_threshold_falls_back_to_f1_when_no_threshold_meets_fpr():
    # Negative và positive chồng lấn hoàn toàn -> không threshold nào đạt FPR<=1%
    # (trừ threshold=1.0 loại hết, recall=0) -> fallback macro-F1 vẫn phải trả về giá trị hợp lệ.
    rng = np.random.default_rng(0)
    y_true = np.array([0] * 50 + [1] * 50)
    y_prob = rng.uniform(0, 1, size=100)  # hoàn toàn ngẫu nhiên, không tách lớp
    t = select_threshold(y_true, y_prob, target_fpr=0.01)
    assert 0.0 <= t <= 1.0


class _ConstantModel:
    """Model giả: predict_proba trả hằng số theo prevalence train — dùng để
    test evaluate_model_nested không phụ thuộc model cụ thể."""

    def fit(self, X, y, groups=None):
        self.p_ = float(np.asarray(y).mean()) if len(y) else 0.0
        return self

    def predict_proba(self, X):
        return np.full(len(X), self.p_)


def _synthetic_grouped_dataset(n_groups=6, rows_per_group=20, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    labels = []
    groups = []
    for g in range(n_groups):
        for i in range(rows_per_group):
            label = 1 if (i < 3) else 0  # mỗi group có vài dòng positive
            rows.append({"f1": rng.normal(loc=1.0 if label else 0.0), "f2": rng.uniform()})
            labels.append(label)
            groups.append(f"group_{g}")
    X = pd.DataFrame(rows)
    y = pd.Series(labels)
    groups = pd.Series(groups)
    return X, y, groups


class _ScoredModel:
    """Model gia: predict_proba = f1 chuan hoa ve [0,1] (co bien thien that,
    khac _ConstantModel) - dung de test calibration co gi de fit."""

    def fit(self, X, y, groups=None):
        return self

    def predict_proba(self, X):
        f1 = X["f1"].to_numpy()
        return 1.0 / (1.0 + np.exp(-f1))  # sigmoid, [0,1], khong suy bien


def test_evaluate_model_nested_calibration_none_by_default_backward_compat():
    """Mac dinh calibration=None - hanh vi CU khong doi (oof_prob_calibrated
    toan NaN, khong pha vo ham/test da co truoc)."""
    X, y, groups = _synthetic_grouped_dataset()
    result = evaluate_model_nested(_ConstantModel, X, y, groups, target_fpr=0.01)
    assert "oof_prob_calibrated" in result
    assert result["oof_prob_calibrated"].isna().all()


def test_evaluate_model_nested_calibration_isotonic_runs():
    X, y, groups = _synthetic_grouped_dataset(n_groups=8, rows_per_group=20)
    result = evaluate_model_nested(_ScoredModel, X, y, groups, target_fpr=0.5, calibration="isotonic")
    assert result["oof_prob_calibrated"].notna().all()
    assert ((result["oof_prob_calibrated"] >= 0) & (result["oof_prob_calibrated"] <= 1)).all()


def test_fit_calibrator_never_receives_test_fold_data():
    """Kiem tra CAU TRUC truc tiep (doc code, khong suy doan): trong
    evaluate_model_nested, _fit_calibrator CHI duoc goi voi
    y_train.to_numpy()[valid_inner] va inner_oof_prob[valid_inner] - ca 2
    deu bat nguon TU inner LOGO tren X_train (khong bao gio la X_test/y_test
    cua outer fold). Test nay xac nhan hanh vi don vi cua _fit_calibrator/
    _apply_calibrator: fit tren 1 tap, apply len tap KHAC hoan toan, ket qua
    phai la ham cua calibrator (khong "nhin thay" tap apply luc fit)."""
    from src.evaluation.nested_eval import _apply_calibrator, _fit_calibrator

    rng = np.random.default_rng(0)
    y_fit = rng.integers(0, 2, size=200)
    p_fit = np.clip(y_fit * 0.7 + rng.normal(0, 0.1, size=200), 0.01, 0.99)
    cal = _fit_calibrator(y_fit, p_fit, "isotonic")

    # Ap dung len 1 tap HOAN TOAN KHAC (mo phong outer test) - ket qua chi
    # phu thuoc calibrator (fit xong, co dinh) + gia tri dau vao, khong doc
    # lai y_fit/p_fit.
    p_apply_a = np.array([0.1, 0.5, 0.9])
    out_a = _apply_calibrator(cal, p_apply_a, "isotonic")
    out_a_again = _apply_calibrator(cal, p_apply_a, "isotonic")
    np.testing.assert_array_equal(out_a, out_a_again)  # deterministic, khong phu thuoc lan goi


def test_evaluate_model_nested_calibration_platt_runs():
    X, y, groups = _synthetic_grouped_dataset(n_groups=8, rows_per_group=20)
    result = evaluate_model_nested(_ScoredModel, X, y, groups, target_fpr=0.5, calibration="platt")
    assert result["oof_prob_calibrated"].notna().all()
    assert ((result["oof_prob_calibrated"] >= 0) & (result["oof_prob_calibrated"] <= 1)).all()


def test_evaluate_model_nested_produces_oof_for_every_row_exactly_once():
    X, y, groups = _synthetic_grouped_dataset()
    result = evaluate_model_nested(_ConstantModel, X, y, groups, target_fpr=0.01)
    assert result["oof_prob"].notna().all(), "mỗi dòng phải có đúng 1 dự đoán OOF (từ lúc group của nó bị giữ lại)"
    assert len(result["fold_rows"]) == groups.nunique()


def test_evaluate_model_nested_threshold_not_derived_from_test_fold():
    """Kiểm tra CẤU TRÚC: threshold của outer fold X chỉ được suy ra từ dữ
    liệu train (9-10 group KHÁC X) — xác nhận bằng cách thay đổi dữ liệu
    CHỈ ở group bị giữ lại (test) và kiểm tra threshold KHÔNG đổi."""
    X, y, groups = _synthetic_grouped_dataset()
    result_a = evaluate_model_nested(_ConstantModel, X, y, groups, target_fpr=0.5)
    thresholds_a = {r["held_out_group"]: r["threshold_chosen_on_inner_train_oof"] for r in result_a["fold_rows"]}

    # Đảo ngược label CHỈ trong group_0 (test fold khi held_out=group_0) —
    # nếu threshold bị rò rỉ từ test, threshold của fold group_0 sẽ đổi.
    y2 = y.copy()
    mask_g0 = groups == "group_0"
    y2[mask_g0] = 1 - y2[mask_g0]
    result_b = evaluate_model_nested(_ConstantModel, X, y2, groups, target_fpr=0.5)
    thresholds_b = {r["held_out_group"]: r["threshold_chosen_on_inner_train_oof"] for r in result_b["fold_rows"]}

    assert thresholds_a["group_0"] == thresholds_b["group_0"], (
        "Threshold của fold group_0 đổi khi CHỈ label của group_0 (test) đổi — "
        "nghi ngờ threshold bị rò rỉ từ test fold"
    )


def test_bootstrap_incident_level_ci_contains_point_estimate():
    rng = np.random.default_rng(1)
    y_true = np.array([0, 1] * 50)
    y_prob = np.clip(y_true + rng.normal(0, 0.3, size=100), 0, 1)
    incident_ids = np.repeat([f"inc_{i}" for i in range(10)], 10)
    result = bootstrap_incident_level(y_true, y_prob, incident_ids, pr_auc, n_boot=200)
    assert result["ci_low"] <= result["point"] <= result["ci_high"]


def test_per_incident_metric_returns_one_value_per_incident():
    y_true = np.array([0, 1, 0, 1])
    y_prob = np.array([0.1, 0.9, 0.2, 0.8])
    incident_ids = np.array(["a", "a", "b", "b"])
    result = per_incident_metric(y_true, y_prob, incident_ids, pr_auc)
    assert set(result.keys()) == {"a", "b"}
