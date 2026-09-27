"""Buoc 4 (Tuan 6) - train M1 CUOI CUNG tren TOAN BO 11 incident (khong
phai 1 fold rieng le), luu model + feature list + moi truong + commit hash
vao results/reports/model_card_m1.md, luu model that (joblib) de tai tao
lai duoc, khong chi chay 1 lan roi mat.

Chay lai script nay BAT KY LUC NAO se cho ra CUNG 1 model (random_state=42
co dinh, hyperparameter co dinh, du lieu doc tu features_v2.parquet da
freeze) - dam bao tai tao duoc.
"""
from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost

from src.evaluation.nested_eval import dedupe_pooled_prefixes
from src.models.baselines import M1TypedTemporalMotifModel

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
MODEL_OUT = REPO_ROOT / "results" / "models" / "m1_final.joblib"
CARD_OUT = REPO_ROOT / "results" / "reports" / "model_card_m1.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]


def _git_commit_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).decode().strip()
    except Exception:
        return "UNKNOWN (khong doc duoc git rev-parse)"


def main():
    df_raw = pd.read_parquet(FEATURES_PATH)
    # Model nay train tren TOAN BO 8 prefix bucket POOL chung (giong RQ1,
    # khac RQ2 - danh gia tung bucket rieng) - phai dedupe (trajectory_id,
    # prefix_len) TRUOC KHI pool, cung ly do voi RQ1 (xem
    # results/reports/rq1_v2_prefixfix.md): sau khi sua bug generate_prefixes
    # (Tuan 7), 1 length co the mang nhieu nhan, giu nguyen se dem lap 1
    # diem quan sat that nhieu lan mot cach gia tao.
    df = dedupe_pooled_prefixes(df_raw)
    print(f"Dedupe pooled prefixes: {len(df_raw)} -> {len(df)} dong", flush=True)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    X = df[feature_cols]
    y = df["label"]
    groups = df["group_id"]

    model = M1TypedTemporalMotifModel()
    model.fit(X, y, groups)

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_OUT)
    print(f"Da luu model: {MODEL_OUT}")

    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    commit_hash = _git_commit_hash()
    now = datetime.now(timezone.utc).isoformat()

    importances = None
    if hasattr(model.model, "feature_importances_"):
        importances = pd.Series(model.model.feature_importances_, index=model.feature_cols_).sort_values(ascending=False)

    card_lines = [
        "# Model Card — M1 (typed temporal + motif + XGBoost/RF)\n",
        f"\n**Ngày train:** {now}\n",
        f"**Commit hash (lúc train):** `{commit_hash}`\n",
        f"**File model:** `{MODEL_OUT.relative_to(REPO_ROOT)}` (joblib, tái tạo qua `python scripts/train_and_save_m1_final.py`)\n",
        "\n## Dữ liệu train\n",
        f"- Nguồn: `{FEATURES_PATH.relative_to(REPO_ROOT)}` (freeze v0.9 + mining bổ sung độ phức tạp, Tuần 5 đợt 2)\n",
        f"- Tổng {len(df)} prefix row, {groups.nunique()} incident/group (leave-one-incident-out — "
        f"model NÀY train trên TOÀN BỘ, không phải 1 fold riêng).\n",
        f"- Positive: {n_pos} dòng, Negative: {n_neg} dòng (tỉ lệ ~1:{n_neg/n_pos:.1f}).\n",
        "\n## Feature\n",
        f"- Tổng {len(model.feature_cols_)}/{len(feature_cols)} cột dùng (đã loại "
        f"{len(model.excluded_raw_action_count_)} cột action_count thô + "
        f"{len(model.excluded_low_coverage_)} cột coverage thấp <2 incident positive).\n",
        f"- Cột action_count thô bị loại: {model.excluded_raw_action_count_}\n",
        f"- Cột coverage thấp bị loại (tính trên TOÀN BỘ dataset — model cuối cùng, "
        f"không phải per-fold): {model.excluded_low_coverage_}\n",
        f"- Danh sách đầy đủ feature cột dùng:\n```\n{model.feature_cols_}\n```\n",
    ]
    if importances is not None:
        card_lines += [
            "\n## Feature importance (top 15, từ model cuối cùng — chỉ mang tính minh họa, "
            "KHÔNG dùng để suy diễn causal)\n",
            "\n```\n" + importances.head(15).to_string() + "\n```\n",
        ]

    card_lines += [
        "\n## Hyperparameter (cố định trước, không tuning rộng — configs/model.yaml)\n",
        f"- Loại model: {'XGBoost' if hasattr(model.model, 'get_booster') else 'RandomForest (fallback, xgboost không khả dụng)'}\n",
        "- n_estimators=200, max_depth=4, learning_rate=0.1, random_state=42\n",
        f"- scale_pos_weight={n_neg/n_pos:.4f} (bù mất cân bằng lớp, tính từ n_neg/n_pos của toàn bộ train)\n",
        "- min_positive_incident_coverage=2 (loại feature coverage thấp)\n",
        "\n## Môi trường (để tái tạo)\n",
        f"- Python: {platform.python_version()} ({platform.system()} {platform.release()})\n",
        f"- scikit-learn: {sklearn.__version__}\n",
        f"- xgboost: {xgboost.__version__}\n",
        f"- pandas: {pd.__version__}\n",
        f"- numpy: {np.__version__}\n",
        f"- scipy: {scipy.__version__}\n",
        "\n## Đánh giá (KHÔNG phải model này — xem kết quả cross-validation trung thực)\n",
        "Model trong file này train trên TOÀN BỘ 11 incident, dùng để lưu/deploy/diễn giải "
        "feature importance — KHÔNG dùng để báo cáo hiệu năng (sẽ overfit/lạc quan giả vì "
        "không có held-out data). Hiệu năng THẬT (leave-one-incident-out, threshold chọn "
        "đúng cách) xem `results/tables/main_table.csv` và `results/reports/rq1_answer.md`.\n",
        "\n## Cách tái tạo\n",
        "```bash\npython scripts/build_features_v2.py   # dung features_v2.parquet (neu chua co)\n"
        "python scripts/train_and_save_m1_final.py\n```\n",
        "Với CÙNG commit + CÙNG features_v2.parquet, kết quả (hệ số/importance) phải GIỐNG HỆT "
        "(random_state cố định trong toàn bộ pipeline).\n",
    ]
    CARD_OUT.parent.mkdir(parents=True, exist_ok=True)
    CARD_OUT.write_text("".join(card_lines), encoding="utf-8")
    print(f"Da luu model card: {CARD_OUT}")


if __name__ == "__main__":
    main()
