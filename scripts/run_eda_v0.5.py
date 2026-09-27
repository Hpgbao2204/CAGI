"""Buoc 1 (Tuan 5) - EDA tren du lieu THAT (khong synthetic) cho tap RQ1
chinh (11 positive incident + 408 hard-negative da xac nhan >=1 prefix
row). Xuat results/reports/eda_v0.5.html.

KHONG dung ground truth AMLGuard - moi thong ke tinh truc tiep tu
trajectory da build qua expand_and_build_trajectory (do_collect=False,
dung cache that da co).
"""
from __future__ import annotations

import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from src.features.extractor import generate_prefixes
from src.pipeline.dataset_builder import load_rq1_trajectories

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "results" / "reports" / "eda_v0.5.html"

OPTIONAL_FIELDS = ["protocol", "token", "counterparty_type", "source_confidence"]


def _iqr(values):
    if not values:
        return (float("nan"), float("nan"), float("nan"))
    s = sorted(values)
    n = len(s)
    median = statistics.median(s)
    q1 = s[max(0, n // 4)]
    q3 = s[min(n - 1, (3 * n) // 4)]
    return (q1, median, q3)


def bar(pct: float, color: str = "#4c78a8") -> str:
    pct = max(0.0, min(100.0, pct))
    return (
        f'<div style="background:#e8e8e8;border-radius:3px;overflow:hidden;height:14px;width:200px;display:inline-block;vertical-align:middle;">'
        f'<div style="background:{color};height:100%;width:{pct:.1f}%;"></div></div>'
    )


def main():
    print("Dang build trajectory that (co the mat vai chuc giay)...", flush=True)
    items = load_rq1_trajectories(verbose=False)
    n_pos = sum(1 for i in items if i.label == 1)
    n_neg = sum(1 for i in items if i.label == 0)
    print(f"Tong item: {len(items)} (positive={n_pos}, negative={n_neg})", flush=True)

    # ---- 1. Trajectory length distribution ----
    pos_lens = [len(i.trajectory) for i in items if i.label == 1]
    neg_lens = [len(i.trajectory) for i in items if i.label == 0]

    by_group_lens = defaultdict(lambda: {"pos": [], "neg": []})
    for i in items:
        key = "pos" if i.label == 1 else "neg"
        by_group_lens[i.group_id][key].append(len(i.trajectory))

    # ---- 2. Chain / protocol distribution ----
    chain_ctr_by_label = {0: Counter(), 1: Counter()}
    protocol_ctr_by_label = {0: Counter(), 1: Counter()}
    event_type_ctr_by_label = {0: Counter(), 1: Counter()}
    for i in items:
        chain_ctr_by_label[i.label][i.chain] += 1
        for a in i.trajectory.actions:
            if a.protocol:
                protocol_ctr_by_label[i.label][a.protocol] += 1
            event_type_ctr_by_label[i.label][a.event_type] += 1

    # ---- 3. Class balance (trajectory-level vs prefix-row-level) ----
    total_prefix_rows = 0
    pos_prefix_rows = 0
    neg_prefix_rows = 0
    prefix_len_records = []  # (label, group_id, prefix_len, trajectory_len)
    for i in items:
        specs = generate_prefixes(i.trajectory)
        total_prefix_rows += len(specs)
        if i.label == 1:
            pos_prefix_rows += len(specs)
        else:
            neg_prefix_rows += len(specs)
        for spec in specs:
            prefix_len_records.append((i.label, i.group_id, spec.length, len(i.trajectory)))

    # ---- 4. Missingness theo field (tren TOAN BO action, khong phai prefix) ----
    n_total_actions = 0
    missing_ctr = Counter()
    for i in items:
        for a in i.trajectory.actions:
            n_total_actions += 1
            for f in OPTIONAL_FIELDS:
                if getattr(a, f) is None:
                    missing_ctr[f] += 1

    # ---- 5. Shortcut check: median/IQR do dai theo lop ----
    q1_p, med_p, q3_p = _iqr(pos_lens)
    q1_n, med_n, q3_n = _iqr(neg_lens)

    # ================= RENDER HTML =================
    def esc(s):
        return html.escape(str(s))

    rows_group = []
    for gid in sorted(by_group_lens):
        d = by_group_lens[gid]
        p_txt = ", ".join(str(x) for x in sorted(d["pos"])) or "-"
        n_vals = sorted(d["neg"])
        n_summary = f"n={len(n_vals)}, median={statistics.median(n_vals):.0f}, min={min(n_vals)}, max={max(n_vals)}" if n_vals else "-"
        rows_group.append(
            f"<tr><td>{esc(gid)}</td><td>{esc(p_txt)}</td><td>{esc(n_summary)}</td></tr>"
        )

    def dist_table(ctr_by_label, title):
        keys = sorted(set(ctr_by_label[0]) | set(ctr_by_label[1]))
        rows = []
        for k in keys:
            c0, c1 = ctr_by_label[0][k], ctr_by_label[1][k]
            rows.append(f"<tr><td>{esc(k)}</td><td>{c1}</td><td>{c0}</td></tr>")
        return f"""
        <table>
          <caption>{title}</caption>
          <tr><th>Giá trị</th><th>Positive (n={n_pos})</th><th>Negative (n={n_neg})</th></tr>
          {''.join(rows)}
        </table>"""

    missing_rows = "".join(
        f"<tr><td>{esc(f)}</td><td>{missing_ctr[f]}</td><td>{n_total_actions}</td>"
        f"<td>{100*missing_ctr[f]/n_total_actions:.1f}%</td><td>{bar(100*missing_ctr[f]/n_total_actions, '#e45756')}</td></tr>"
        for f in OPTIONAL_FIELDS
    )

    shortcut_html = f"""
    <table>
      <tr><th>Lớp</th><th>n trajectory</th><th>Q1</th><th>Median</th><th>Q3</th><th>Min</th><th>Max</th></tr>
      <tr><td>Positive (label=1)</td><td>{len(pos_lens)}</td><td>{q1_p}</td><td>{med_p}</td><td>{q3_p}</td><td>{min(pos_lens)}</td><td>{max(pos_lens)}</td></tr>
      <tr><td>Negative (label=0)</td><td>{len(neg_lens)}</td><td>{q1_n}</td><td>{med_n}</td><td>{q3_n}</td><td>{min(neg_lens)}</td><td>{max(neg_lens)}</td></tr>
    </table>
    """

    overlap_lo = max(q1_p, q1_n)
    overlap_hi = min(q3_p, q3_n)
    if overlap_lo <= overlap_hi:
        overlap_note = (
            f"<p><strong>Nhận xét:</strong> khoảng IQR của 2 lớp CÓ chồng lấn "
            f"(vùng chung [{overlap_lo:.0f}, {overlap_hi:.0f}]) &rarr; độ dài trajectory một mình "
            f"không tách lớp hoàn toàn.</p>"
        )
    else:
        overlap_note = (
            f"<p style='color:#b91c1c'><strong>CẢNH BÁO SHORTCUT:</strong> khoảng IQR của 2 lớp "
            f"<em>KHÔNG chồng lấn</em> — positive [{q1_p:.0f}, {q3_p:.0f}] (median {med_p:.0f}) "
            f"hoàn toàn nằm trên negative [{q1_n:.0f}, {q3_n:.0f}] (median {med_n:.0f}). "
            f"Đây là dấu hiệu rõ ràng model CÓ THỂ đạt điểm cao chỉ bằng cách học "
            f"\"trajectory dài &rarr; positive\" thay vì tín hiệu semantic/motif thật — "
            f"PHẢI đối chiếu với feature importance của B2 ở Bước 5 để xác nhận model "
            f"không chỉ dựa vào cardinality/length-correlated feature (vd fan_out, "
            f"action_count_* cộng dồn theo độ dài) mà bỏ qua ngữ nghĩa loại hành động.</p>"
        )

    html_doc = f"""<title>EDA v0.5 — CAGI-ED RQ1 dataset thật</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 980px; margin: 40px auto; padding: 0 16px; color:#1a1a1a; background:#fff; line-height:1.55; }}
  h1 {{ font-size: 1.6rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2.2rem; border-bottom: 2px solid #eee; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0 20px; font-size: 0.92rem; }}
  caption {{ text-align:left; font-weight:600; margin-bottom:6px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
  th {{ background: #f5f5f5; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .meta {{ color: #666; font-size: 0.9rem; }}
  code {{ background:#f3f3f3; padding:1px 5px; border-radius:3px; }}
</style>

<h1>EDA v0.5 — CAGI-ED dataset RQ1 (11 incident positive, dữ liệu thật)</h1>
<p class="meta">Nguồn: freeze v0.9 (<code>experiments/registry.csv</code>). Không dùng ground truth AMLGuard —
mọi số liệu tính trực tiếp từ trajectory build qua <code>expand_and_build_trajectory</code>
(cache thật, <code>do_collect=False</code>).</p>

<h2>1. Class balance</h2>
<table>
  <tr><th>Mức</th><th>Positive</th><th>Negative</th><th>Tỷ lệ (neg:pos)</th></tr>
  <tr><td><strong>Trajectory-level</strong></td><td>{n_pos}</td><td>{n_neg}</td><td>1:{n_neg/n_pos:.1f}</td></tr>
  <tr><td><strong>Prefix-row-level</strong></td><td>{pos_prefix_rows}</td><td>{neg_prefix_rows}</td><td>1:{neg_prefix_rows/pos_prefix_rows:.1f}</td></tr>
</table>
<p>Tổng prefix row = <strong>{total_prefix_rows}</strong> (freeze v0.9 ghi nhận 1002 —
{"KHỚP" if total_prefix_rows == 1002 else f"LỆCH ({total_prefix_rows} != 1002), cần điều tra"}).</p>
<p>Mất cân bằng ở mức trajectory (~1:{n_neg/n_pos:.0f}) lớn hơn nhiều so với mức prefix row
(~1:{neg_prefix_rows/pos_prefix_rows:.0f}) — vì mỗi positive trajectory (thường dài hơn) sinh
nhiều prefix row hơn 1 hard-negative trajectory ngắn (nhiều hard-negative chỉ có 1 action &rarr; 1 prefix row).</p>

<h2>2. Trajectory length distribution</h2>
{shortcut_html}
{overlap_note}

<h3>2b. Theo từng group (11 group, group_id từ split_manifest.json)</h3>
<table>
  <tr><th>group_id</th><th>Positive — độ dài</th><th>Hard-negative (control + mined) — tóm tắt</th></tr>
  {''.join(rows_group)}
</table>

<h2>3. Chain distribution</h2>
{dist_table(chain_ctr_by_label, "Số trajectory theo chain")}

<h2>4. Protocol distribution (đếm theo ACTION, không phải trajectory)</h2>
{dist_table(protocol_ctr_by_label, "Số action theo protocol đã gắn nhãn")}

<h2>5. Event type distribution (đếm theo ACTION)</h2>
{dist_table(event_type_ctr_by_label, "Số action theo event_type")}

<h2>6. Missingness theo field (optional fields, đếm theo ACTION)</h2>
<table>
  <tr><th>Field</th><th>Missing</th><th>Tổng action</th><th>% Missing</th><th></th></tr>
  {missing_rows}
</table>
<p class="meta">required_fields (chain_id, block_number, timestamp, tx_hash, log_index, src, dst,
event_type, amount_norm) không bao giờ null — Pydantic <code>CanonicalEvent</code> validator
chặn ngay khi decode, không cần thống kê.</p>

<h2>7. Shortcut check chi tiết</h2>
<p>Xem mục 2 — bảng median/IQR độ dài theo lớp ở trên. IQR 2 lớp <strong>KHÔNG chồng
lấn</strong> (cảnh báo shortcut thật) — đã đối chiếu tiếp ở Bước 4 (baseline B0/B1/B2,
<code>results/tables/baseline_results_v1.csv</code>) và Bước 5 (leakage audit trên hệ số
B2, <code>results/reports/leakage_audit_v1_findings.md</code>). Kết quả Bước 5 xác nhận lo
ngại này CÓ CƠ SỞ THẬT: tổng <code>action_count_*</code> (dùng bởi B2) tương quan tuyệt đối
(pearson r=1.000) với <code>prefix_len</code> — về mặt toán học đây là hệ quả trực tiếp của
cách định nghĩa prefix (không phải phát hiện bất ngờ), nhưng nghĩa là B2 CÓ đường tiếp cận
tới tín hiệu độ dài thô qua tổng bag-of-actions. Đồng thời phát hiện thêm 1 shortcut RÕ RÀNG
hơn: feature có hệ số cao nhất của B2 (<code>action_count_lending_deposit</code>) chỉ xuất
hiện ở <strong>1/11</strong> group positive (<code>bsc_token_hub_2022</code> — Venus Protocol)
— mô hình đang gán trọng số lớn cho 1 đặc điểm riêng của 1 incident, không phải tín hiệu
typology chung. Xem chi tiết đầy đủ trong file leakage audit.</p>
"""

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html_doc, encoding="utf-8")
    print(f"\nDa ghi {OUT_PATH}")
    print(f"Tong prefix row = {total_prefix_rows} (ky vong ~1002)")
    print(f"positive median/IQR len = {med_p} [{q1_p}, {q3_p}]")
    print(f"negative median/IQR len = {med_n} [{q1_n}, {q3_n}]")


if __name__ == "__main__":
    main()
