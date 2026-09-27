"""Tuan 7 (RQ2) - chan doan cau hoi cua nguoi dung: vi sao mean PR-AUC giam
0.955 (ratio_75) -> 0.852 (ratio_100), va so nay co khop voi PR-AUC M1 da
bao cao o RQ1/Tuan 6 hay khong.

Ket luan (xem results/reports/rq2_ratio100_diagnostic.md sau khi chay):
(a) Tap 11 held_out_group giong het nhau o ca 2 bucket (khong co incident
    nao "moi" xuat hien rieng o ratio_100).
(b) Nguyen nhan giam la do CO CHE DEDUP THEO DO DAI trong generate_prefixes()
    (specs.setdefault, uu tien nhan ratio nho hon khi trung do dai): 1
    trajectory can do dai >= 4 moi co the co ca 4 nhan ratio_25/50/75/100
    PHAN BIET NHAU; trajectory ngan hon se KHONG BAO GIO nhan nhan
    "ratio_100" (bi "nuot" vao ratio_25/50/75). Vi phan lon hard-negative
    rat ngan (median 1-2 action), bucket ratio_100 mat gan het hard-negative
    "de" va chi con lai (i) khong con hard-negative nao (xkingdom_2024,
    feg_bridge_2024 -> PR-AUC undefined/NaN, bi loai khoi mean) hoac (ii)
    chi con lai nhung hard-negative DAI NHAT/KHO NHAT (deltaprime_arbitrum_2024,
    wooppv2_2024 -> PR-AUC roi tu 1.0 xuong 0.333).
(c) 0.852 (ratio_100, trung binh 9/11 fold hop le) KHONG khop voi con so M1
    da bao cao o RQ1 (0.7190, bootstrap point estimate tren OOF gop tat ca
    8 bucket) - va KHONG NEN khop, vi day la 2 thuc nghiem khac nhau: RQ1
    train 1 model/fold tren TOAN BO 1304 dong (8 bucket gop chung), con
    ratio_100 o day train 1 model/fold RIENG chi tren cac dong ratio_100.
    Cach chon threshold (nested, target_fpr=0.01) la GIONG HET NHAU o ca 2
    tuan - khong phai nguon khac biet. Cach tinh mean CUNG khac nhau (bootstrap
    pooled-then-scored vs trung binh per-fold don gian) va TU NO da tao ra 2
    con so khac nhau (0.7190 vs 0.7892) ngay trong cung 1 tuan.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
FOLD_PATH = REPO_ROOT / "results" / "tables" / "rq2_prefix_evaluation_folds.csv"
MAIN_TABLE_PATH = REPO_ROOT / "results" / "tables" / "main_table.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "rq2_ratio100_diagnostic.md"


def main():
    df = pd.read_parquet(FEATURES_PATH)
    fold_df = pd.read_csv(FOLD_PATH)
    main_df = pd.read_csv(MAIN_TABLE_PATH)

    r75 = fold_df[fold_df["prefix_bucket"] == "ratio_75"].set_index("held_out_group")
    r100 = fold_df[fold_df["prefix_bucket"] == "ratio_100"].set_index("held_out_group")

    # (a) tap incident co giong nhau khong
    set_75, set_100 = set(r75.index), set(r100.index)
    same_set = set_75 == set_100

    # (b) ghep bang so sanh + n_val + pr_auc 2 bucket
    cmp = pd.DataFrame({
        "n_val_75": r75["n_val_rows"], "pr_auc_75": r75["pr_auc"],
        "n_val_100": r100["n_val_rows"], "pr_auc_100": r100["pr_auc"],
    })
    cmp["delta_pr_auc"] = cmp["pr_auc_100"] - cmp["pr_auc_75"]

    # kiem chung nguyen nhan: do dai hard-negative cua tung group, so dong
    # dat toi han length>=4 (dieu kien can de co nhan rieng ratio_100)
    len_report = []
    for grp in sorted(set_75):
        neg = df[(df["group_id"] == grp) & (df["label"] == 0)]
        by_traj = neg.groupby("source_id")["trajectory_len"].first()
        n_ge4 = int((by_traj >= 4).sum())
        len_report.append({
            "group": grp, "n_hard_neg_traj": len(by_traj),
            "median_len": by_traj.median() if len(by_traj) else float("nan"),
            "n_traj_len_ge_4": n_ge4,
            "pct_survive_to_ratio100": (n_ge4 / len(by_traj) * 100) if len(by_traj) else float("nan"),
            "n_rows_ratio100_actual": int((neg["prefix_label"] == "ratio_100").sum()),
        })
    len_df = pd.DataFrame(len_report).set_index("group")

    # (c) so sanh voi RQ1/Tuan 6
    m1_overall = main_df[(main_df["model"] == "M1") & (main_df["metric"] == "pr_auc")].iloc[0]
    m1_per_inc = main_df[(main_df["model"] == "M1") & main_df["metric"].str.startswith("pr_auc_incident_")].copy()
    m1_per_inc_mean = m1_per_inc["mean_point_estimate"].mean()
    r100_mean_valid = r100["pr_auc"].mean()
    n_valid_100 = r100["pr_auc"].notna().sum()

    lines = [
        "# Chẩn đoán: PR-AUC giảm ratio_75 (0.955) → ratio_100 (0.852)\n",
        "\n(Tuần 7, chẩn đoán bổ sung theo yêu cầu — không phải bug, có nguyên nhân cấu trúc "
        "đã xác nhận qua code + dữ liệu thật, xem `scripts/diagnose_ratio100_drop_v1.py`.)\n",
        "\n## (a) Tập incident/fold có giống nhau giữa 2 bucket không?\n",
        f"\n**CÓ, giống hệt nhau** — cả `ratio_75` và `ratio_100` đều có đúng 11 `held_out_group` "
        f"(same_set = {same_set}). Không có incident nào chỉ xuất hiện riêng ở bucket 100%.\n",
        "\n## (b) Vì tập incident giống nhau, điểm số giảm đến từ đâu?\n",
        "\n### Nguyên nhân gốc (đã xác nhận trong code `src/features/extractor.py:32-54`)\n",
        "\n`generate_prefixes()` duyệt `ratios=(0.25, 0.5, 0.75, 1.0)` theo đúng thứ tự này, dùng "
        "`specs.setdefault(length, label)` — nếu 2 mốc ratio khác nhau tính ra **cùng 1 độ dài "
        "nguyên** (hay xảy ra với trajectory ngắn), chỉ nhãn ratio **được xử lý TRƯỚC** (nhỏ hơn) "
        "được giữ. Hệ quả: một trajectory cần độ dài ≥ 4 hành động mới có thể có đủ 4 nhãn "
        "ratio_25/50/75/100 **phân biệt nhau**; trajectory ngắn hơn (1–3 hành động) **KHÔNG BAO "
        "GIỜ có dòng nhãn `ratio_100`** — dòng full-length của nó bị 'nuốt' vào ratio_75/50/25.\n",
        "\n### Xác nhận bằng dữ liệu thật (số hard-negative theo group)\n\n",
        len_df.to_string(), "\n",
        "\n`xkingdom_2024` và `feg_bridge_2024`: **100% hard-negative của chính 2 group này ngắn "
        "hơn 4 hành động** → 0 dòng `ratio_100` cho cả 2 → khi 2 group này là held-out fold ở "
        "bucket `ratio_100`, tập validation chỉ còn đúng 1 dòng (positive), **0 negative** → "
        "PR-AUC không xác định (NaN), bị loại khỏi mean (đúng, không nên gán 0 hay 1 giả).\n",
        "\n`deltaprime_arbitrum_2024` (9/75 = 12%) và `wooppv2_2024` (3/35 = 8.6%): chỉ một phần "
        "rất nhỏ hard-negative đủ dài để sống sót tới `ratio_100`. Đây là **hiệu ứng chọn lọc**: "
        "số ít sống sót lại chính là các hard-negative **DÀI/PHỨC TẠP NHẤT** (deltaprime có "
        "hard-negative dài tới 224 hành động trong khi chính positive chỉ dài 5 hành động) — khó "
        "phân biệt hơn hẳn so với các hard-negative ngắn 'dễ' đã bị hút hết vào `ratio_25/50/75`. "
        "PR-AUC của 2 fold này vì vậy rơi từ 1.0 (ratio_75, có cả negative dễ) xuống 0.333 "
        "(ratio_100, chỉ còn negative khó).\n",
        "\n### Bảng so sánh trực tiếp 2 bucket theo từng fold\n\n",
        cmp.to_string(), "\n",
        f"\nMean ratio_75 (11/11 fold hợp lệ) = **{r75['pr_auc'].mean():.4f}**. "
        f"Mean ratio_100 ({n_valid_100}/11 fold hợp lệ, loại 2 fold NaN) = **{r100_mean_valid:.4f}**.\n",
        "\n**Kết luận (b):** không phải một incident 'mới' kéo điểm xuống — mà (i) 2/11 fold trở "
        "thành *không xác định* và bị loại khỏi mẫu số (giảm cỡ mẫu), và (ii) 2/11 fold khác bị "
        "đánh giá trên một tập negative đã bị lọc thiên lệch về phía khó hơn, do đúng cơ chế dedup "
        "theo độ dài của `generate_prefixes()` — đây là hạn chế cấu trúc cần ghi chú rõ trong báo "
        "cáo RQ2 (bucket `ratio_100` không đại diện đầy đủ cho toàn bộ negative population, thiên "
        "lệch loại bỏ các hard-negative ngắn).\n",
        "\n## (c) 0.852 (ratio_100) có khớp với PR-AUC M1 đã báo cáo ở RQ1/Tuần 6 không?\n",
        f"\n**KHÔNG khớp — và điều đó là đúng như kỳ vọng, không phải sai số cần sửa:**\n",
        f"\n| Nguồn | Giá trị | Cách tính |\n|---|---|---|\n",
        f"| RQ1/Tuần 6 (`rq1_answer.md`, headline) | **{m1_overall['mean_point_estimate']:.4f}** "
        f"[{m1_overall['ci_low_95']:.4f}, {m1_overall['ci_high_95']:.4f}] | Bootstrap incident-level "
        f"point estimate — 1 model/fold train+eval trên TOÀN BỘ 1304 dòng (gộp cả 8 bucket "
        f"ratio_25/50/75/100 + k_2/3/5/7), OOF pooled rồi mới bootstrap-resample 11 incident |\n",
        f"| RQ1/Tuần 6 (trung bình đơn giản 11 per-incident PR-AUC, cùng model/predictions) | "
        f"**{m1_per_inc_mean:.4f}** | Trung bình cộng 11 giá trị PR-AUC/incident (KHÔNG bootstrap "
        f"pooled) — cùng dữ liệu, khác cách gộp |\n",
        f"| RQ2/Tuần 7 (`ratio_100` bucket) | **{r100_mean_valid:.4f}** ({n_valid_100}/11 fold) | "
        f"1 model/fold RIÊNG chỉ train+eval trên 105 dòng nhãn `ratio_100` — model, tập train, tập "
        f"eval ĐỀU khác RQ1 |\n",
        "\n**Nguồn khác biệt, xác nhận từng phần:**\n",
        "\n1. **Phạm vi model/dữ liệu (nguyên nhân chính):** RQ1 đánh giá M1 như 1 model/fold học "
        "từ TẤT CẢ độ dài prefix trộn chung (train set 10 incident × 8 bucket); RQ2 `ratio_100` "
        "train một model/fold RIÊNG BIỆT, nhỏ hơn nhiều, chỉ thấy dữ liệu ở đúng 1 mốc độ dài. "
        "Đây là 2 thí nghiệm khác nhau, không phải cùng 1 con số báo cáo 2 lần.\n",
        "\n2. **Cách chọn threshold: GIỐNG HỆT NHAU**, không phải nguồn khác biệt — cả 2 tuần đều "
        "dùng `evaluate_model_nested(..., target_fpr=0.01)` với inner Leave-One-Group-Out y hệt.\n",
        "\n3. **Cách tính mean: có khác biệt, và tự nó cũng gây chênh lệch** — ngay trong Tuần 6, "
        f"bootstrap pooled-then-scored ({m1_overall['mean_point_estimate']:.4f}) và trung bình "
        f"per-incident đơn giản ({m1_per_inc_mean:.4f}) đã lệch nhau ~0.07 trên CÙNG 1 tập dự đoán, "
        "vì pooling thay đổi trọng số theo số dòng/incident. Số 0.852 của Tuần 7 dùng cách tính "
        "thứ 3 (trung bình per-fold PR-AUC, loại các fold NaN) trên tập dữ liệu nhỏ hơn hẳn (105 "
        "dòng thay vì 1304).\n",
        "\n**Khuyến nghị cho báo cáo RQ2:** không nên so trực tiếp '0.852 (ratio_100)' với "
        f"'{m1_overall['mean_point_estimate']:.4f} (RQ1 headline)' như cùng 1 đại lượng — nên ghi rõ "
        "đây là PR-AUC của model chuyên biệt-theo-mốc-prefix, đánh giá trên tập validation nhỏ và "
        "bị lệch thành phần negative (thiếu hard-negative ngắn) ở mốc 100%, đồng thời loại 2/11 "
        "fold (xkingdom_2024, feg_bridge_2024) do không có negative nào để đánh giá ở mốc này.\n",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"Da luu {OUT_MD}")
    print(f"\nsame_set(a) = {same_set}")
    print(f"\nRQ1 headline (bootstrap pooled) = {m1_overall['mean_point_estimate']:.4f}")
    print(f"RQ1 per-incident-mean (simple)  = {m1_per_inc_mean:.4f}")
    print(f"RQ2 ratio_100 mean ({n_valid_100}/11 fold hop le) = {r100_mean_valid:.4f}")


if __name__ == "__main__":
    main()
