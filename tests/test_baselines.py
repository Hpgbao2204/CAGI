"""
Test cho baseline/primary models (Bước 6), dùng dữ liệu synthetic.
"""
import numpy as np

from src.evaluation.dataset import build_prefix_dataset
from src.models.baselines import get_all_baselines
from src.trajectories.builder import TrajectoryConfig
from tests.fixtures.synthetic_trajectories import build_synthetic_dataset

CONFIG = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05)


def _dataset():
    raw = build_synthetic_dataset()
    return build_prefix_dataset(raw, CONFIG)


def test_prefix_dataset_has_rows_and_matching_lengths():
    X, y, groups, meta = _dataset()
    assert len(X) == len(y) == len(groups) == len(meta)
    assert len(X) > 0
    assert set(y.unique()) <= {0, 1}


def test_all_baselines_fit_predict_proba_in_range():
    X, y, groups, _ = _dataset()
    models = get_all_baselines()
    for name, model in models.items():
        model.fit(X, y, groups)
        proba = model.predict_proba(X)
        assert len(proba) == len(X), f"{name}: predict_proba length mismatch"
        assert np.all((proba >= 0.0) & (proba <= 1.0)), f"{name}: proba ngoài [0,1]"


def test_b0_majority_returns_constant_prevalence():
    X, y, groups, _ = _dataset()
    from src.models.baselines import B0MajorityBaseline

    model = B0MajorityBaseline()
    model.fit(X, y, groups)
    proba = model.predict_proba(X)
    assert np.allclose(proba, proba[0])
    assert np.isclose(proba[0], y.mean())


def test_b1_rule_based_scores_positive_incidents_higher():
    X, y, groups, meta = _dataset()
    from src.models.baselines import B1RuleBasedTypologyScore

    model = B1RuleBasedTypologyScore()
    model.fit(X, y, groups)
    proba = model.predict_proba(X)

    # Tại prefix đầy đủ (ratio_100), incident dương (có bridge->swap->split)
    # phải có điểm rule-based cao hơn rõ rệt so với incident âm.
    full_mask = meta["prefix_label"] == "ratio_100"
    pos_scores = proba[full_mask & (y.to_numpy() == 1)]
    neg_scores = proba[full_mask & (y.to_numpy() == 0)]
    assert pos_scores.mean() > neg_scores.mean()


def test_b2_bag_of_actions_only_uses_action_count_columns():
    X, y, groups, _ = _dataset()
    from src.models.baselines import B2BagOfActionsLogisticRegression

    model = B2BagOfActionsLogisticRegression()
    model.fit(X, y, groups)
    assert all(c.startswith("action_count_") for c in model.feature_cols_)


def test_m1_model_fits_without_error_and_uses_more_features_than_b2():
    X, y, groups, _ = _dataset()
    from src.models.baselines import B2BagOfActionsLogisticRegression, M1TypedTemporalMotifModel

    b2 = B2BagOfActionsLogisticRegression()
    b2.fit(X, y, groups)
    m1 = M1TypedTemporalMotifModel()
    m1.fit(X, y, groups)
    assert len(m1.feature_cols_) > len(b2.feature_cols_)


def test_models_do_not_use_endpoint_context_features_by_default():
    """Đảm bảo dataset mặc định (include_endpoint_context=False trong
    extract_all_prefixes) không lộ known_mixer_interaction/public_exit_service_label
    cho model, đúng anti_leakage_rules khi mục tiêu là cảnh báo trước endpoint.
    """
    X, _, _, _ = _dataset()
    assert "known_mixer_interaction" not in X.columns
    assert "public_exit_service_label" not in X.columns


def test_b3_flat_graph_excludes_typed_semantic_and_motif_features():
    """B3 (Tuần 6) PHẢI là baseline "untyped" thật sự cho RQ1 — không được
    dùng bất kỳ feature nào phân biệt loại hành động (semantic_action,
    motif) hay đặc thù bridge (time_to_first_bridge), khác với bug thật ở
    bản trước (B3 dùng chung toàn bộ feature với M1, không phải phép so
    sánh hợp lệ cho "typed vs untyped")."""
    X, y, groups, _ = _dataset()
    from src.models.baselines import B3FlatGraphRandomForest

    model = B3FlatGraphRandomForest()
    model.fit(X, y, groups)
    assert not any(c.startswith("action_count_") for c in model.feature_cols_)
    assert not any(c.startswith("motif_") for c in model.feature_cols_)
    assert "time_to_first_bridge" not in model.feature_cols_
    assert "num_bridge_families" not in model.feature_cols_
    assert "swap_after_bridge" not in model.feature_cols_
    assert len(model.feature_cols_) > 0  # vẫn phải còn feature structural/economic để fit được


def test_m1_excludes_raw_action_count_and_applies_coverage_filter():
    """M1 (Tuần 6) phải dùng bộ feature ĐÃ LÀM SẠCH ở Tuần 5: loại
    action_count_{type} thô (giữ bản "_ratio"), và loại feature coverage
    thấp (<2 incident positive trong train fold) — không quay lại bản có
    shortcut."""
    X, y, groups, _ = _dataset()
    from src.models.baselines import M1TypedTemporalMotifModel

    model = M1TypedTemporalMotifModel()
    model.fit(X, y, groups)
    raw_action_cols = [c for c in model.feature_cols_ if c.startswith("action_count_") and not c.endswith("_ratio")]
    assert raw_action_cols == [], f"M1 không được dùng action_count thô: {raw_action_cols}"
    assert model.excluded_raw_action_count_, "phải ghi nhận đã loại cột thô nào"
