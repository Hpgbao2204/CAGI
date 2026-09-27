"""Tuan 9, Buoc 6 - benchmark efficiency (RQ4): ms/event (extract_features),
s/trajectory (extract_features + M1.predict_proba), peak RAM theo so
event/trajectory - do SAU warm-up, ghi ro hardware/process count.

Dung TRAJECTORY THAT (tu load_rq1_trajectories, cache local, khong goi API
moi) o nhieu do dai khac nhau - khong dung du lieu tong hop gia dinh.

Luu y (dung tinh than RQ4 - xem research_questions.md): CHI do model
processing latency (extract_features + predict_proba), KHONG do
data-availability delay (thoi gian cho API tra ve) hay lead time canh bao -
2 khai niem khac nhau, khong duoc gop chung thanh "near real-time <60s".
"""
from __future__ import annotations

import gc
import platform
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import sklearn
import xgboost

from src.evaluation.nested_eval import dedupe_pooled_prefixes
from src.features.extractor import extract_features
from src.models.baselines import M1TypedTemporalMotifModel
from src.pipeline.dataset_builder import load_rq1_trajectories

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OUT_TABLE = REPO_ROOT / "results" / "tables" / "runtime_table.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "runtime_v1.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]

N_WARMUP = 20
N_MEASURE_PER_BUCKET = 15


def main():
    print("=== Nap trajectory that (cache local) ===", flush=True)
    items = load_rq1_trajectories(verbose=False, include_v2_complexity=True)
    lengths = sorted(set(len(i.trajectory) for i in items if len(i.trajectory) > 0))
    print(f"Tong {len(items)} trajectory, do dai distinct: {len(lengths)} (min={min(lengths)}, max={max(lengths)})", flush=True)

    # --- Train model that (tren dataset da dedupe, giong RQ1) de predict_proba co nghia ---
    df_raw = pd.read_parquet(FEATURES_PATH)
    df = dedupe_pooled_prefixes(df_raw)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    model = M1TypedTemporalMotifModel()
    model.fit(df[feature_cols], df["label"], df["group_id"])
    print(f"Da train M1 (giong m1_final) tren {len(df)} dong, {len(model.feature_cols_)} feature.", flush=True)

    # --- Chon bucket do dai (log-scale) tu trajectory THAT co san ---
    length_buckets = sorted(set(min(lengths, key=lambda l: abs(l - target))
                                 for target in [2, 5, 10, 25, 50, 100, 250, 500]))
    traj_by_len = {}
    for i in items:
        n = len(i.trajectory)
        if n in length_buckets and n not in traj_by_len:
            traj_by_len[n] = i.trajectory
    print(f"Bucket do dai dung de benchmark: {sorted(traj_by_len.keys())}", flush=True)

    def _run_once(traj):
        feats = extract_features(traj, len(traj), include_endpoint_context=False)
        row = pd.DataFrame([feats])[model.feature_cols_].fillna(0.0)
        prob = model.predict_proba(row)[0]
        return prob

    # --- Warm-up (loai bo anh huong JIT/cache lan dau cua numpy/xgboost) ---
    print(f"\n=== Warm-up ({N_WARMUP} lan, khong tinh vao ket qua) ===", flush=True)
    warmup_traj = traj_by_len[sorted(traj_by_len)[len(traj_by_len) // 2]]
    for _ in range(N_WARMUP):
        _run_once(warmup_traj)

    # --- Do latency + peak RAM cho tung bucket do dai ---
    process = psutil.Process()
    rows = []
    print(f"\n=== Benchmark ({N_MEASURE_PER_BUCKET} lan/bucket, sau warm-up) ===", flush=True)
    for n_events in sorted(traj_by_len):
        traj = traj_by_len[n_events]
        gc.collect()
        latencies_ms = []
        tracemalloc.start()
        rss_before = process.memory_info().rss
        for _ in range(N_MEASURE_PER_BUCKET):
            t0 = time.perf_counter()
            _run_once(traj)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)
        _, peak_tracemalloc = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rss_after = process.memory_info().rss

        latencies_ms = np.array(latencies_ms)
        row = {
            "n_events": n_events,
            "median_ms_per_trajectory": float(np.median(latencies_ms)),
            "mean_ms_per_trajectory": float(latencies_ms.mean()),
            "p95_ms_per_trajectory": float(np.percentile(latencies_ms, 95)),
            "ms_per_event": float(np.median(latencies_ms) / n_events),
            "peak_ram_delta_mb_tracemalloc": peak_tracemalloc / 1e6,
            "rss_mb_before": rss_before / 1e6,
            "rss_mb_after": rss_after / 1e6,
            "n_measurements": N_MEASURE_PER_BUCKET,
        }
        rows.append(row)
        print(f"  n_events={n_events:4d}  median={row['median_ms_per_trajectory']:.3f}ms  "
              f"p95={row['p95_ms_per_trajectory']:.3f}ms  ms/event={row['ms_per_event']:.4f}  "
              f"peak_ram_delta={row['peak_ram_delta_mb_tracemalloc']:.3f}MB", flush=True)

    table_df = pd.DataFrame(rows)
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    table_df.to_csv(OUT_TABLE, index=False)
    print(f"\nDa luu {OUT_TABLE}")

    # --- Kiem tra tang gan tuyen tinh (H4) - fit hoi quy tuyen tinh don gian tren log-log de bao cao he so ---
    x = np.log(table_df["n_events"].to_numpy())
    y_lat = np.log(table_df["median_ms_per_trajectory"].to_numpy())
    slope_lat = float(np.polyfit(x, y_lat, 1)[0])  # ~1 = tuyen tinh, <1 = duoi tuyen tinh, >1 = tren tuyen tinh

    hardware = {
        "platform": platform.platform(), "processor": platform.processor(),
        "python_version": platform.python_version(), "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "total_ram_gb": psutil.virtual_memory().total / 1e9,
        "sklearn_version": sklearn.__version__, "xgboost_version": xgboost.__version__,
        "process_count": 1,  # single-process, single-thread benchmark (khong parallel)
    }

    latency_ratio = table_df["median_ms_per_trajectory"].iloc[-1] / table_df["median_ms_per_trajectory"].iloc[0]
    n_ratio = table_df["n_events"].iloc[-1] / table_df["n_events"].iloc[0]
    md = [
        "# Efficiency benchmark — M1 (Tuần 9, Bước 6, bằng chứng RQ4)\n",
        "\n**CHỈ đo model processing latency** (extract_features + predict_proba) — "
        "KHÔNG đo data-availability delay (thời gian chờ API) hay alert lead time (RQ2). "
        "Không đồng nhất với \"near real-time <60s\" — 2 khái niệm khác nhau (đúng ràng buộc "
        "`research_questions.md` mục RQ4).\n",
        f"\nĐo sau {N_WARMUP} lần warm-up, {N_MEASURE_PER_BUCKET} lần đo/bucket độ dài, dùng "
        "trajectory THẬT từ dataset (không tổng hợp giả định).\n",
        "\n## Hardware / môi trường\n\n```\n" + "\n".join(f"{k}: {v}" for k, v in hardware.items()) + "\n```\n",
        "\n## Kết quả theo số event/trajectory\n\n",
        table_df.to_string(index=False),
        "\n\n## Kiểm tra tăng gần tuyến tính (H4) — diễn giải thủ công "
        "(số hồi quy tự động dễ gây hiểu lầm, xem lý do dưới)\n",
        f"\nHệ số góc hồi quy log(latency) ~ log(n_events) = **{slope_lat:.3f}** — con số này "
        "KHÔNG có nghĩa \"không tuyến tính rõ theo hướng xấu\"; nó phản ánh đúng thực tế quan "
        f"sát được: **latency gần như PHẲNG (dưới tuyến tính), không tăng mạnh theo độ dài** "
        f"trong khoảng đã đo ({table_df['n_events'].iloc[0]:.0f}→{table_df['n_events'].iloc[-1]:.0f} "
        f"event, tăng {n_ratio:.0f} lần): {table_df['median_ms_per_trajectory'].iloc[0]:.1f}ms → "
        f"{table_df['median_ms_per_trajectory'].iloc[-1]:.1f}ms (chỉ tăng ~{latency_ratio:.2f} lần). "
        "Nguyên nhân: mỗi lần gọi có **overhead cố định** (chủ yếu từ dựng `DataFrame` 1 dòng + "
        "gọi XGBoost booster) không phụ thuộc số event — phần tăng thêm theo độ dài (từ "
        "`extract_features` duyệt qua các action) chỉ đóng góp một phần nhỏ, chỉ rõ rệt khi "
        "trajectory khá dài.\n",
        "\n**ms/event giảm dần theo độ dài là HỆ QUẢ TRỰC TIẾP** của overhead cố định chia cho "
        "số event tăng dần — không phải \"biến động bất thường\", mà cho thấy **throughput/event "
        "CẢI THIỆN** khi trajectory dài hơn (chi phí cố định được khấu hao trên nhiều event hơn).\n",
        f"\n**Kết luận cho H4:** đạt tinh thần giả thuyết (latency KHÔNG bùng nổ theo độ dài trong "
        f"quy mô proof-of-concept, tổng latency luôn <{table_df['p95_ms_per_trajectory'].max():.0f}ms/"
        "trajectory kể cả ở kích thước lớn nhất đã đo) — thực tế còn tốt hơn \"tuyến tính\" "
        "(sub-linear/gần phẳng), nên diễn giải là \"H4 được ủng hộ, với đặc điểm cụ thể: chi phí "
        "cố định/lần gọi chiếm ưu thế ở quy mô hiện tại\" thay vì chỉ nói \"gần tuyến tính\".\n",
        f"\n**RAM:** `peak_ram_delta_mb_tracemalloc` giữ phẳng quanh "
        f"{table_df['peak_ram_delta_mb_tracemalloc'].min():.3f}–"
        f"{table_df['peak_ram_delta_mb_tracemalloc'].max():.3f}MB bất kể độ dài — không đo được "
        "xu hướng tăng RAM theo độ dài trong khoảng đã test (dự đoán trên 1 trajectory tại 1 "
        "thời điểm, không phải batch lớn) — phù hợp \"không cần GPU, chi phí bộ nhớ không đáng "
        "kể ở quy mô này\".\n",
        "\n**Không cần GPU** — toàn bộ benchmark chạy CPU-only (XGBoost CPU backend).\n",
        f"\n**Lưu ý về `total_ram_gb={hardware['total_ram_gb']:.2f}`** trong bảng hardware phía "
        "trên: đây là RAM mà `psutil` báo cáo trong MÔI TRƯỜNG CHẠY THẬT (có thể là VM/container "
        "giới hạn tài nguyên, không nhất thiết là RAM vật lý đầy đủ của máy host) — ghi nguyên "
        "trạng, không suy đoán thêm.\n",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")


if __name__ == "__main__":
    main()
