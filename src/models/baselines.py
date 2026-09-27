"""
Baseline & primary models — xem configs/model.yaml.

Mọi model implement chung interface:
    fit(X_train, y_train, groups_train) -> self
    predict_proba(X) -> np.ndarray shape (n_samples,)  # P(label=1)

`groups_train` (incident_id) được truyền vào để các model tương lai có thể
dùng (vd calibration theo nhóm); các baseline hiện tại không cần nhưng vẫn
nhận tham số để giữ interface đồng nhất, phục vụ GroupKFold trong
src/evaluation/.

- B0: majority/prevalence baseline (không học từ feature)
- B1: rule-based typology score (bridge -> swap -> split/mixer trong cửa sổ
  thời gian, không học máy — chỉ cộng điểm theo motif/semantic feature)
- B2: bag-of-actions (action_count_*) + Logistic Regression
- B3: flat-graph handcrafted features (toàn bộ feature vector) + RandomForest
- M1: typed temporal + motif features + XGBoost (fallback RandomForest nếu
  xgboost không khả dụng trong môi trường chạy)
"""
from __future__ import annotations

from typing import Dict, List, Optional, Protocol, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

try:
    from xgboost import XGBClassifier

    _HAS_XGBOOST = True
except ImportError:  # pragma: no cover - fallback path exercised only without xgboost installed
    _HAS_XGBOOST = False


class BaselineModel(Protocol):
    def fit(self, X_train: pd.DataFrame, y_train: Sequence[int], groups_train: Sequence) -> "BaselineModel": ...

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray: ...


class B0MajorityBaseline:
    """Sanity-check tối thiểu: luôn trả về prevalence (tỉ lệ lớp dương) của train."""

    name = "B0_majority_prevalence"

    def __init__(self) -> None:
        self.prevalence_: float = 0.0

    def fit(self, X_train: pd.DataFrame, y_train: Sequence[int], groups_train: Sequence = None) -> "B0MajorityBaseline":
        y = np.asarray(y_train)
        self.prevalence_ = float(y.mean()) if len(y) else 0.0
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(shape=(len(X),), fill_value=self.prevalence_, dtype=float)


class B1RuleBasedTypologyScore:
    """Rule-based, không học: cộng điểm theo motif/semantic-action đã quan sát.

    Điểm dựa trên các feature do src/features/extractor.py sinh ra:
    motif_bridge_then_swap, motif_swap_then_split, motif_split,
    swap_after_bridge, num_bridge_families — đúng typology "bridge -> swap ->
    split/mixer" trong cửa sổ thời gian đã mô tả trong configs/model.yaml.
    Không có bước "fit" theo nghĩa học tham số; `fit` chỉ để tương thích
    interface và ước lượng ngưỡng chuẩn hóa điểm (min-max trên train).
    """

    name = "B1_rule_based_typology_score"

    RULE_FEATURES: Dict[str, float] = {
        "motif_bridge_then_swap": 2.0,
        "motif_swap_then_split": 2.0,
        "motif_split": 1.0,
        "swap_after_bridge": 1.0,
        "num_bridge_families": 0.5,
        "motif_nested_bridge": 1.0,
        "motif_peel_like_chain": 1.0,
        "motif_rapid_token_pivot": 0.25,
    }

    def __init__(self) -> None:
        self.max_score_: float = 1.0

    def _raw_score(self, X: pd.DataFrame) -> np.ndarray:
        score = np.zeros(len(X), dtype=float)
        for feat, weight in self.RULE_FEATURES.items():
            if feat in X.columns:
                score += weight * X[feat].to_numpy(dtype=float)
        return score

    def fit(self, X_train: pd.DataFrame, y_train: Sequence[int], groups_train: Sequence = None) -> "B1RuleBasedTypologyScore":
        raw = self._raw_score(X_train)
        self.max_score_ = float(raw.max()) if len(raw) and raw.max() > 0 else 1.0
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raw = self._raw_score(X)
        return np.clip(raw / self.max_score_, 0.0, 1.0)


class B2BagOfActionsLogisticRegression:
    """Bag-of-actions (action_count_*) + Logistic Regression.

    Sửa Tuần 5 (leakage audit — xem results/reports/leakage_audit_v1_findings.md
    và leakage_audit_v2_comparison.md): 2 thay đổi để giảm shortcut phát hiện
    ở B2 v1:
    1. Ưu tiên cột `_ratio` (action_count_X / prefix_len) thay vì cột thô —
       cột thô tương quan TUYỆT ĐỐI (r=1.000) với prefix_len vì tổng của
       chúng CHÍNH LÀ prefix_len, cho model đường tắt học độ dài thay vì
       thành phần hành động.
    2. `min_positive_incident_coverage` (mặc định=2): loại cột chỉ có giá
       trị >0 ở <2 group_id khác nhau trong số các dòng positive CỦA TRAIN
       FOLD — tránh model gán trọng số lớn cho đặc điểm riêng của 1 incident
       (bug thật phát hiện ở B2 v1: action_count_lending_deposit hệ số cao
       nhất, coef=1.635, nhưng chỉ xuất hiện ở bsc_token_hub_2022). Tính
       TRÊN TRAIN FOLD (không phải toàn bộ dataset) để không rò rỉ thống kê
       từ fold validation vào bước chọn feature.
    """

    name = "B2_bag_of_actions_logreg"

    def __init__(self, min_positive_incident_coverage: int = 2, **lr_kwargs) -> None:
        self.model = LogisticRegression(max_iter=1000, **lr_kwargs)
        self.feature_cols_: List[str] = []
        self.min_positive_incident_coverage = min_positive_incident_coverage
        self.excluded_low_coverage_: List[str] = []

    def _candidate_columns(self, X: pd.DataFrame) -> List[str]:
        # Ưu tiên cột "_ratio" nếu có (feature v2 trở đi); fallback về cột
        # thô cho tương thích ngược với parquet cũ (feature v1) chưa có cột
        # "_ratio" — không phải lựa chọn chủ động, chỉ để không crash.
        ratio_cols = [c for c in X.columns if c.startswith("action_count_") and c.endswith("_ratio")]
        if ratio_cols:
            return ratio_cols
        return [c for c in X.columns if c.startswith("action_count_")]

    def fit(self, X_train: pd.DataFrame, y_train: Sequence[int], groups_train: Sequence = None) -> "B2BagOfActionsLogisticRegression":
        candidate_cols = self._candidate_columns(X_train)
        kept, excluded = _filter_low_coverage_columns(
            X_train, y_train, groups_train, candidate_cols, self.min_positive_incident_coverage,
        )
        self.excluded_low_coverage_ = excluded
        self.feature_cols_ = kept
        self.model.fit(X_train[kept], y_train)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Xb = X[self.feature_cols_]
        return self.model.predict_proba(Xb)[:, 1]


class B3FlatGraphRandomForest:
    """Flat-graph handcrafted features + RandomForest — đối chứng "KHÔNG
    typed semantics" cho RQ1 (so sánh với M1 "typed").

    Sửa Tuần 6 (theo yêu cầu người dùng): bản trước dùng TOÀN BỘ feature
    vector (kể cả action_count_*/motif_* — cùng bộ với M1!), khiến B3
    KHÔNG thực sự là baseline "flat/untyped" — không phải phép so sánh hợp
    lệ cho RQ1 (typed vs untyped). Sửa: B3 CHỈ dùng feature coi trajectory
    như đồ thị dòng tiền ẩn danh (ai gửi bao nhiêu cho ai, lúc nào) —
    KHÔNG biết cạnh nào là bridge/swap/mixer/lending (nhóm semantic_action,
    motif) hay đặc thù bridge (time_to_first_bridge):
    - structural (nhóm gốc, đã bản chất "flat": đếm cạnh/node, không phân
      biệt loại): fan_out, fan_in, unique_counterparties, local_ego_density,
      path_depth, branch_count.
    - economic KHÔNG phân loại hành động: log_amount_mean,
      outgoing_incoming_ratio, value_retention, token_category_diversity.
    - temporal TỔNG QUÁT (không tham chiếu bridge): active_duration_sec,
      burstiness, inter_action_gap_mean/std.
    - prefix_ratio: kích thước tương đối của prefix (không phải thông tin loại).
    """

    name = "B3_flat_graph_rf"

    FLAT_UNTYPED_FEATURES = (
        # structural
        "fan_out", "fan_in", "unique_counterparties", "local_ego_density", "path_depth", "branch_count",
        # economic (không phân biệt loại hành động)
        "log_amount_mean", "outgoing_incoming_ratio", "value_retention", "token_category_diversity",
        # temporal tổng quát (KHÔNG gồm time_to_first_bridge — đặc thù bridge)
        "active_duration_sec", "burstiness", "inter_action_gap_mean", "inter_action_gap_std",
        "prefix_ratio",
    )

    def __init__(self, **rf_kwargs) -> None:
        params = dict(n_estimators=200, max_depth=8, random_state=42, class_weight="balanced")
        params.update(rf_kwargs)
        self.model = RandomForestClassifier(**params)
        self.feature_cols_: List[str] = []

    def _select_columns(self, X: pd.DataFrame) -> List[str]:
        return [c for c in self.FLAT_UNTYPED_FEATURES if c in X.columns]

    def fit(self, X_train: pd.DataFrame, y_train: Sequence[int], groups_train: Sequence = None) -> "B3FlatGraphRandomForest":
        cols = self._select_columns(X_train)
        self.feature_cols_ = cols
        self.model.fit(X_train[cols], y_train)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Xb = X[self.feature_cols_]
        return self.model.predict_proba(Xb)[:, 1]


def _filter_low_coverage_columns(
    X_train: pd.DataFrame, y_train: Sequence[int], groups_train: Optional[Sequence], candidate_cols: List[str],
    min_positive_incident_coverage: int,
) -> tuple:
    """Dùng chung cho B2/M1: loại cột chỉ có giá trị >0 ở <min_positive_
    incident_coverage group_id khác nhau TRONG SỐ DÒNG POSITIVE của TRAIN
    FOLD — tránh model gán trọng số lớn cho đặc điểm riêng của 1 incident
    (xem B2BagOfActionsLogisticRegression docstring, bug thật Tuần 5).
    Tính trên TRAIN FOLD (không phải toàn bộ dataset) để không rò rỉ thống
    kê từ fold validation vào bước chọn feature. Trả về (kept, excluded).
    """
    if groups_train is None or not candidate_cols:
        return candidate_cols, []
    y_arr = pd.Series(y_train).reset_index(drop=True)
    g_arr = pd.Series(groups_train).reset_index(drop=True)
    Xc = X_train[candidate_cols].reset_index(drop=True)
    pos_mask = (y_arr == 1)
    kept, excluded = [], []
    for col in candidate_cols:
        nonzero_groups = g_arr[pos_mask & (Xc[col] > 0)].nunique()
        (kept if nonzero_groups >= min_positive_incident_coverage else excluded).append(col)
    if not kept:  # an toàn: dataset quá nhỏ, giữ nguyên toàn bộ thay vì crash
        return candidate_cols, []
    return kept, excluded


# Loại bỏ khỏi M1 chính thức (2026-08-28, xem
# results/reports/bridge_context_ablation_investigation.md) — nhóm
# "bridge_context" (không phải nhóm "context" đã loại theo anti_leakage_rules
# từ trước, đây là tên khác, dễ nhầm): điều tra ablation trên 15 incident
# xác nhận nhóm này gây HẠI có ý nghĩa thống kê (paired diff +0.0638, 95% CI
# [+0.0101,+0.1501] không chứa 0), do overfitting theo protocol cụ thể —
# time_to_first_bridge chỉ học đúng hướng cho 5/15 incident có bridge thật
# (LI.FI/Stargate/Across), sai hướng cho 9/15 incident còn lại (BSC/mixer).
# Hiệu ứng gần như không tồn tại ở N=11-12 (CI luôn chứa 0) — chỉ lộ rõ khi
# N=15 với protocol đa dạng hơn. Loại TOÀN BỘ 9 cột (không giữ một phần):
# chỉ 2/9 cột thực sự được dùng để split (theo SHAP), và CẢ HAI đều có hại.
BRIDGE_CONTEXT_COLS_EXCLUDED = [
    "time_to_first_bridge", "action_count_bridge_deposit", "action_count_bridge_deposit_ratio",
    "action_count_bridge_withdraw", "action_count_bridge_withdraw_ratio",
    "num_bridge_families", "swap_after_bridge", "motif_bridge_then_swap", "motif_nested_bridge",
]


class M1TypedTemporalMotifModel:
    """Model chính (RQ1): dùng "làm sạch" ở Tuần 5 (temporal/structural/
    economic/semantic_action/motif — nhóm "context" loại theo
    anti_leakage_rules) + XGBoost, TRỪ nhóm con `bridge_context`
    (xem `BRIDGE_CONTEXT_COLS_EXCLUDED` ở trên — loại 2026-08-28 sau khi
    xác nhận gây hại qua ablation 15-incident).

    Fallback sang RandomForest nếu xgboost không import được trong môi
    trường chạy (vd sandbox không có wheel phù hợp) — vẫn giữ nguyên
    interface fit/predict_proba để không phá vỡ evaluation pipeline.

    Sửa Tuần 6 (áp dụng ĐÚNG bộ feature đã làm sạch ở Tuần 5, không quay
    lại bản có shortcut — theo yêu cầu người dùng):
    1. Loại cột action_count_{type} THÔ (giữ bản "_ratio") — bản thô tương
       quan TUYỆT ĐỐI (r=1.000) với prefix_len (xem leakage_audit_v1_findings.md).
    2. Áp dụng CÙNG coverage filter với B2 (min_positive_incident_coverage=2,
       tính trên train fold) cho TOÀN BỘ feature còn lại — không chỉ
       action_count_*, vì motif_* cũng có thể chỉ xuất hiện ở 1 incident.
    3. `scale_pos_weight` bù mất cân bằng lớp nặng (~1:37 ở mức trajectory).

    Sửa 2026-08-28: loại `BRIDGE_CONTEXT_COLS_EXCLUDED` (xem module-level
    constant) — xem `results/reports/bridge_context_ablation_investigation.md`.

    Hyperparameter CỐ ĐỊNH TRƯỚC (không tuning rộng — đúng configs/model.yaml
    hyperparameter_search.no_wide_tuning=true): n_estimators=200, max_depth=4,
    learning_rate=0.1 — chọn dựa trên kinh nghiệm chung cho dataset nhỏ
    (tránh overfit với cây sâu/nhiều estimator), KHÔNG search trên dữ liệu.
    """

    name = "M1_typed_temporal_motif_xgboost"

    def __init__(
        self, min_positive_incident_coverage: int = 2, include_bridge_context: bool = False, **model_kwargs
    ) -> None:
        self.min_positive_incident_coverage = min_positive_incident_coverage
        # include_bridge_context: CHI dung cho ablation/investigation (vd
        # "M1_with_bridge_context" trong scripts/run_ablation_e4_e5.py) - de
        # tai tao lai hanh vi CU (truoc 2026-08-28) khi can doi chieu. KHONG
        # dat True cho M1 chinh thuc dung trong RQ1/RQ2.
        self.include_bridge_context = include_bridge_context
        self._model_kwargs = model_kwargs
        self.feature_cols_: List[str] = []
        self.excluded_low_coverage_: List[str] = []
        self.excluded_raw_action_count_: List[str] = []
        self.excluded_bridge_context_: List[str] = []

    def _candidate_columns(self, X: pd.DataFrame) -> List[str]:
        cols = []
        for c in X.columns:
            if c in ("prefix_len", "prefix_ratio_meta"):
                continue
            if c.startswith("action_count_") and not c.endswith("_ratio"):
                continue  # loại bản thô, giữ bản "_ratio"
            if not self.include_bridge_context and c in BRIDGE_CONTEXT_COLS_EXCLUDED:
                continue  # loại 2026-08-28 - xac nhan gay hai qua ablation 15-incident
            cols.append(c)
        return cols

    def fit(self, X_train: pd.DataFrame, y_train: Sequence[int], groups_train: Sequence = None) -> "M1TypedTemporalMotifModel":
        raw_action_cols = [c for c in X_train.columns if c.startswith("action_count_") and not c.endswith("_ratio")]
        self.excluded_raw_action_count_ = raw_action_cols
        self.excluded_bridge_context_ = (
            [] if self.include_bridge_context else [c for c in X_train.columns if c in BRIDGE_CONTEXT_COLS_EXCLUDED]
        )
        candidate_cols = self._candidate_columns(X_train)
        kept, excluded = _filter_low_coverage_columns(
            X_train, y_train, groups_train, candidate_cols, self.min_positive_incident_coverage,
        )
        self.excluded_low_coverage_ = excluded
        self.feature_cols_ = kept

        y_arr = np.asarray(y_train)
        n_pos = int((y_arr == 1).sum())
        n_neg = int((y_arr == 0).sum())
        scale_pos_weight = (n_neg / n_pos) if n_pos > 0 else 1.0

        if _HAS_XGBOOST:
            params = dict(
                n_estimators=200, max_depth=4, learning_rate=0.1, random_state=42,
                eval_metric="logloss", scale_pos_weight=scale_pos_weight,
            )
            params.update(self._model_kwargs)
            self.model = XGBClassifier(**params)
        else:  # pragma: no cover
            params = dict(n_estimators=200, max_depth=6, random_state=42, class_weight="balanced")
            params.update(self._model_kwargs)
            self.model = RandomForestClassifier(**params)

        self.model.fit(X_train[kept], y_train)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Xb = X[self.feature_cols_]
        return self.model.predict_proba(Xb)[:, 1]


def get_all_baselines() -> Dict[str, BaselineModel]:
    """Registry tiện dùng trong evaluation — khớp configs/model.yaml."""
    return {
        "B0": B0MajorityBaseline(),
        "B1": B1RuleBasedTypologyScore(),
        "B2": B2BagOfActionsLogisticRegression(),
        "B3": B3FlatGraphRandomForest(),
        "M1": M1TypedTemporalMotifModel(),
    }
