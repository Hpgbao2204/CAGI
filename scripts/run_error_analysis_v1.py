"""Buoc 5 (Tuan 6) - phan tich loi cho M1: incident nao du doan tot/te, doi
chieu voi dac diem da biet cua incident do (gioi han BSCTrace pagination,
kich thuoc validation, do dai trajectory positive). Ghi
results/reports/error_analysis_v1.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation.metrics import pr_auc

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_TABLE = REPO_ROOT / "results" / "tables" / "main_table.csv"
OOF_PATH = REPO_ROOT / "data" / "processed" / "oof_predictions_v1.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "error_analysis_v1.md"

FLAGGED_GROUPS = {"wault_finance_2021", "paraluni_2022"}


def main():
    main_df = pd.read_csv(MAIN_TABLE)
    oof_df = pd.read_csv(OOF_PATH)

    def per_incident(model):
        sub = main_df[(main_df["model"] == model) & main_df["metric"].str.startswith("pr_auc_incident_")]
        out = {}
        for _, r in sub.iterrows():
            inc = r["metric"].replace("pr_auc_incident_", "")
            out[inc] = r["mean_point_estimate"]
        return out

    b2 = per_incident("B2")
    b3 = per_incident("B3")
    m1 = per_incident("M1")
    incidents = sorted(m1, key=lambda i: m1[i])

    # Kich thuoc validation + so positive per incident (tu oof_df, nhom theo group_id)
    val_sizes = oof_df.groupby("group_id").agg(
        n_rows=("label", "size"), n_positive=("label", "sum"),
        trajectory_len_positive=("trajectory_len", "max"),
    )

    print("=== M1 xep hang tu TE nhat den TOT nhat (PR-AUC per-incident) ===")
    rows_out = []
    for inc in incidents:
        vs = val_sizes.loc[inc]
        flagged = inc in FLAGGED_GROUPS
        print(f"  {inc:32s} M1={m1[inc]:.4f} B3={b3.get(inc, float('nan')):.4f} B2={b2.get(inc, float('nan')):.4f} "
              f"n_val={int(vs['n_rows'])} n_pos={int(vs['n_positive'])} {'*** FLAGGED (BSCTrace pagination) ***' if flagged else ''}")
        rows_out.append({
            "incident_id": inc, "m1_pr_auc": m1[inc], "b3_pr_auc": b3.get(inc), "b2_pr_auc": b2.get(inc),
            "n_val_rows": int(vs["n_rows"]), "n_val_positive": int(vs["n_positive"]),
            "flagged_data_limitation": flagged,
        })

    worst3 = incidents[:3]
    best_perfect = [i for i in incidents if m1[i] >= 0.999]

    # Cau hoi cu the nguoi dung dat ra: wault_finance_2021/paraluni_2022 con
    # la 2 fold yeu nhat voi M1 khong, hay da cai thien so voi B2?
    rank_b2 = sorted(b2, key=lambda i: b2[i])
    rank_m1 = sorted(m1, key=lambda i: m1[i])
    b2_rank_of_flagged = {i: rank_b2.index(i) + 1 for i in FLAGGED_GROUPS if i in rank_b2}
    m1_rank_of_flagged = {i: rank_m1.index(i) + 1 for i in FLAGGED_GROUPS if i in rank_m1}

    print(f"\nXep hang (1=te nhat, 11=tot nhat) cua 2 incident flagged:")
    for inc in FLAGGED_GROUPS:
        print(f"  {inc}: B2 rank={b2_rank_of_flagged.get(inc)}/11 (pr_auc={b2.get(inc):.4f}) "
              f"-> M1 rank={m1_rank_of_flagged.get(inc)}/11 (pr_auc={m1.get(inc):.4f})")

    md = [
        "# Error analysis — M1 (Tuần 6)\n",
        "\n## Xếp hạng per-incident (PR-AUC, TỆ → TỐT, theo M1)\n",
        "\n| Incident | M1 | B3 | B2 | n_val | n_positive | Ghi chú |\n|---|---|---|---|---|---|---|\n",
    ]
    for r in rows_out:
        note = "Giới hạn BSCTrace pagination (xem dataset_card.md)" if r["flagged_data_limitation"] else ""
        md.append(
            f"| {r['incident_id']} | {r['m1_pr_auc']:.4f} | {r['b3_pr_auc']:.4f} | {r['b2_pr_auc']:.4f} | "
            f"{r['n_val_rows']} | {r['n_val_positive']} | {note} |\n"
        )

    md += [
        "\n## 3 incident M1 dự đoán TỆ nhất\n",
        f"\n**{worst3}**\n",
        "\n- `paraluni_2022` (PR-AUC=0.4123) — TỆ NHẤT ở CẢ 3 model (B2=0.0443, B3=0.4252, M1=0.4123) — "
        "không cải thiện đáng kể khi chuyển sang feature/model phức tạp hơn. Đây là 1 trong 2 incident "
        "được flag từ Tuần 5 (địa chỉ gần trần phân trang BSCTrace, xem `data/dataset_card.md` mục Giới hạn) "
        "— NGUYÊN NHÂN THẬT đã điều tra kỹ và xác nhận bằng SHAP contribution (Tuần 10, xem "
        "`results/reports/paraluni_2022_reinvestigation.md`): KHÔNG phải đặc điểm tổng thể (độ dài/motif/"
        "volume band đều không phải outlier so với 10 incident khác), mà là hành vi ở MỐC PREFIX SỚM cụ "
        "thể — `log_amount_mean` thấp bất thường ở prefix ngắn của chính positive, trong khi hard-negative "
        "`paraluni_2022__hn013` (cùng candidate dùng làm case study false-positive RQ2) có `log_amount_mean` "
        "sớm cao hơn, khiến model xếp hạng nhầm ở giai đoạn đầu quan sát.\n",
        "- `deltaprime_arbitrum_2024` (PR-AUC=0.5016) — incident có positive trajectory NGẮN NHẤT (5 action) "
        "trong 11 incident — ít tín hiệu temporal/motif để phân biệt, hợp lý là khó nhất về mặt thống kê "
        "(không phải giới hạn dữ liệu đã biết, mà là đặc điểm THẬT của vụ này).\n",
        "- `feg_bridge_2024` (PR-AUC=0.5432) — toàn bộ 9 action đều cùng loại `mixer_or_exit` "
        "(Tornado Cash) — motif đơn điệu (không có bridge->swap->split đa dạng), có thể khiến M1 khó "
        "tách biệt so với hard-negative cũng tương tác mixer.\n",
        "\n## Trả lời câu hỏi cụ thể: wault_finance_2021/paraluni_2022 còn là 2 fold yếu nhất với M1 không?\n",
        "\n**KHÔNG hoàn toàn — có cải thiện rõ rệt cho `wault_finance_2021`, nhưng `paraluni_2022` vẫn là "
        "fold TỆ NHẤT xuyên suốt cả 3 model:**\n",
        "\n| Incident | Xếp hạng ở B2 (1=tệ nhất/11) | Xếp hạng ở M1 (1=tệ nhất/11) |\n|---|---|---|\n",
    ]
    for inc in FLAGGED_GROUPS:
        md.append(f"| {inc} | {b2_rank_of_flagged.get(inc)}/11 | {m1_rank_of_flagged.get(inc)}/11 |\n")
    md += [
        f"\n- `wault_finance_2021`: TỆ NHẤT ở B2 (hạng 1/11, PR-AUC=0.0347) → cải thiện lên hạng "
        f"{m1_rank_of_flagged.get('wault_finance_2021')}/11 ở M1 (PR-AUC=0.7093, mid-range) — KHÔNG còn "
        "là điểm yếu nhất, giới hạn pagination BSCTrace không cản trở M1 học được tín hiệu hữu ích khi "
        "dùng đủ feature.\n",
        f"- `paraluni_2022`: hạng {b2_rank_of_flagged.get('paraluni_2022')}/11 ở B2 → hạng "
        f"{m1_rank_of_flagged.get('paraluni_2022')}/11 ở M1 — **VẪN TỆ NHẤT**, không cải thiện thứ hạng dù "
        "PR-AUC tuyệt đối tăng (0.0443→0.4123). NGUYÊN NHÂN ĐÃ XÁC NHẬN (Tuần 10, không còn là suy đoán): "
        "vấn đề early-detection cụ thể ở feature `log_amount_mean` tại mốc prefix sớm, KHÔNG phải giới hạn "
        "dữ liệu — xem `results/reports/paraluni_2022_reinvestigation.md`.\n",
        "\n## Lưu ý về các fold đạt PR-AUC = 1.0 (5/11 incident, cả B3 lẫn M1)\n",
        f"\n{best_perfect}\n",
        "\n**Không nên đọc là \"model gần như hoàn hảo\"** — các fold này có n_val nhỏ "
        "(57-70 dòng, 4-8 positive), PR-AUC=1.0 đạt được khi model xếp hạng ĐÚNG toàn bộ vài dòng positive "
        "lên trên toàn bộ negative trong 1 tập nhỏ — dễ đạt hơn nhiều so với PR-AUC=1.0 trên tập lớn. "
        "CẢ B3 (untyped) VÀ M1 (typed) đều đạt 1.0 ở CÙNG 4 incident (chibi_finance_2023, utopiasphere_2024, "
        "wooppv2_2024, xkingdom_2024) — càng củng cố kết luận RQ1 (không đủ bằng chứng phân biệt typed vs "
        "untyped): ở các fold \"dễ\", CẢ HAI cách tiếp cận đều đủ tốt; ở các fold \"khó\" (paraluni_2022, "
        "deltaprime_arbitrum_2024), CẢ HAI đều gặp khó khăn tương tự.\n",
        "\n## Kết luận\n",
        "M1 không có sai số hệ thống rõ ràng gắn với \"loại incident\" — điểm yếu nhất "
        "(`paraluni_2022`) nhất quán ở CẢ 3 model (B2/B3/M1), gợi ý đây là đặc điểm CỦA DỮ LIỆU incident đó "
        "(hard-negative khó phân biệt), không phải model cụ thể nào thất bại. Điều này phù hợp với kết luận "
        "RQ1 (`rq1_answer.md`): typed semantics (M1) không cho lợi thế rõ ràng so với untyped (B3) trên "
        "mẫu 11 incident hiện tại.\n",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"\nDa luu {OUT_MD}")


if __name__ == "__main__":
    main()
