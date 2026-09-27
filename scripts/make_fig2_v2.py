"""Ve lai Fig. 2 (v2) sau phan hoi: case cu (deltaprime vs benign_control 1
action) lech do dai qua lon (23 vs 1), co nguy co vo tinh minh hoa dung
"shortcut do dai" ma du an da sua (Giai doan B, tieu chi fan_out band-
matched). Doi sang deltaprime_arbitrum_2024__hn051 (15 action, DA co trong
metadata/hard_negative_registry.csv, band-matched, cung dung Across Protocol
SpokePool tren Arbitrum) - 23 vs 15, gan nhau hon nhieu.

Xuat 2 ban:
  - fig2_simplified_for_slide.png: don gian hoa manh cho nguoi xem khong
    chuyen - nhan hanh dong bang tieng Viet thuong + icon hinh dang don
    gian (khong con nhan dang S->A (USDC)), KHONG co chu giai dia chi, KHONG
    co so lieu thong ke motif tren hinh. Positive dai 23 action (>15) nen
    chi ve dai dien ~11 action dau + hop "...con N hanh dong khac".
  - fig2_technical_full.png: giu day du chi tiet ky thuat (nhan dia chi rut
    gon + ma chu cai, chu giai, so lieu motif) - dung cho phu luc/paper, tuy
    nhien DUNG CUNG case moi (23 vs 15) de nhat quan, khong giu lai case cu
    bi lech do dai.

Chi tiet ky thuat day du (dia chi day du, bang motif toan bo 2 trajectory,
ly do chon case) duoc ghi rieng trong results/figures/fig2_technical_appendix.md
- KHONG hien thi tren hinh dung cho slide.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
FIG_DIR = REPO_ROOT / "results" / "figures"
SCRATCH_HN051 = Path(
    "C:/Users/GAMING/AppData/Local/Temp/claude/d--DAI-HOC-cagi-ed/"
    "13088f9a-2212-448d-89ca-1bc07963c50b/scratchpad/deltaprime_hn051_events.json"
)

POS_ID = "deltaprime_arbitrum_2024"
NEG_ID = "deltaprime_arbitrum_2024__hn051"

SPLIT_SRCS = {
    "0x56e7f67211683857ee31a1220827cac5cdaa634c",  # seed positive (5 outgoing)
    "0x0000000000000000000000000000000000000000",  # relay hub 1 (11 outgoing)
    "0xea3123e9d9911199a6711321d1277285e6d4f3ec",  # relay hub 2 (6 outgoing)
    "0xd45bda83d11fda3eda0107ce9aa8856b753fc44e",  # seed hard-negative (15 outgoing, lap lai 1 canh)
}
MERGE_DSTS = {
    "0xc3f3a07ae7d2a125ef81a5950c4d0dd54c740251",
    "0xea3123e9d9911199a6711321d1277285e6d4f3ec",
    "0x6c411ad3e74de3e7bd422b94a27770f5b86c623b",
    "0xe35e9842fceaca96570b734083f4a58e8f7c5f2a",  # bridge contract, nhan 15 lan tu hard-negative
}

NODE_LABELS = {
    "0x56e7f67211683857ee31a1220827cac5cdaa634c": ("S", "seed / ví tấn công"),
    "0xc3f3a07ae7d2a125ef81a5950c4d0dd54c740251": ("A", "hop trung gian 1"),
    "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": ("B", "WETH contract (Arbitrum)"),
    "0x0000000000000000000000000000000000000000": ("Z", "relay hub 1 (native ETH wrap/unwrap)"),
    "0xea3123e9d9911199a6711321d1277285e6d4f3ec": ("H", "relay hub 2"),
    "0x6c411ad3e74de3e7bd422b94a27770f5b86c623b": ("F", "điểm gom cuối cùng"),
    "0xe35e9842fceaca96570b734083f4a58e8f7c5f2a": ("BR", "Across Protocol SpokePool (bridge thật)"),
    "0xd45bda83d11fda3eda0107ce9aa8856b753fc44e": ("S2", "ví khác (hard-negative, không liên quan S)"),
}

EVENT_VN = {
    "transfer": "Chuyển tiền",
    "swap": "Đổi token",
    "bridge_deposit": "Qua cầu nối",
}
EVENT_COLOR = {
    "transfer": "#4C72B0",
    "swap": "#DD8452",
    "bridge_deposit": "#C0392B",
}
EVENT_MARKER = {
    "transfer": "o",
    "swap": "D",
    "bridge_deposit": "*",
}


def short(addr: str) -> str:
    return addr[:8] + "..."


def node_label(addr: str) -> str:
    return NODE_LABELS.get(addr, (short(addr), addr))[0]


def is_motif_action(ev) -> bool:
    return ev["src"] in SPLIT_SRCS or ev["dst"] in MERGE_DSTS


def load_events(path_or_id) -> list:
    if isinstance(path_or_id, Path):
        events = json.loads(path_or_id.read_text(encoding="utf-8"))
    else:
        events = json.loads((PROCESSED_DIR / f"{path_or_id}_events.json").read_text(encoding="utf-8"))
    return sorted(events, key=lambda a: a["timestamp"])


def cluster_by_exact_timestamp(events):
    clusters = []
    for ev in events:
        if clusters and clusters[-1][0] == ev["timestamp"]:
            clusters[-1][1].append(ev)
        else:
            clusters.append((ev["timestamp"], [ev]))
    return clusters


def motif_spans(clusters):
    """Tra ve list (i_start, i_end) cac doan cluster LIEN TIEP co it nhat 1
    action thoa is_motif_action - dung chung cho ca 2 ban ve."""
    flags = [any(is_motif_action(ev) for ev in evs) for _, evs in clusters]
    spans = []
    i = 0
    while i < len(flags):
        if flags[i]:
            j = i
            while j < len(flags) and flags[j]:
                j += 1
            spans.append((i, j - 1))
            i = j
        else:
            i += 1
    return spans


# ---------------------------------------------------------------------------
# BAN DON GIAN (slide) - khong ma dia chi, khong so lieu thong ke, ngon ngu
# thuong, toi da 3 mau (khong tinh nen vang nhat cua motif)
# ---------------------------------------------------------------------------
POS_SHOW_CLUSTERS = 8  # ~11/23 action dau, du de thay ca 4 loai hanh dong


def draw_simplified(pos_events, neg_events, out_path: Path):
    pos_clusters = cluster_by_exact_timestamp(pos_events)
    neg_clusters = cluster_by_exact_timestamp(neg_events)

    pos_shown = pos_clusters[:POS_SHOW_CLUSTERS]
    pos_hidden_n = sum(len(evs) for _, evs in pos_clusters[POS_SHOW_CLUSTERS:])
    pos_shown_n = sum(len(evs) for _, evs in pos_shown)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12.5, 6.4), height_ratios=[1, 1])

    X_STEP = 1.7

    def draw_row(ax, clusters, t0, truncate_note=None, show_motif_bg=True,
                 uniform_label=None):
        xs = [i * X_STEP for i in range(len(clusters))]
        if show_motif_bg:
            spans = motif_spans(clusters)
            for i0, i1 in spans:
                ax.axvspan(xs[i0] - X_STEP * 0.42, xs[i1] + X_STEP * 0.42,
                           color="#FDF3D0", zorder=0, lw=0)

        ax.plot([xs[0], xs[-1]] if len(xs) > 1 else [xs[0], xs[0]], [0, 0],
                color="#C7C7C7", lw=2, zorder=1, solid_capstyle="round")

        for x, (ts, evs) in zip(xs, clusters):
            dt_h = (pd.Timestamp(ts) - t0).total_seconds() / 3600.0
            n = len(evs)
            et = evs[0]["event_type"]
            for k, ev in enumerate(evs):
                yy = (k - (n - 1) / 2.0) * 0.10
                ax.scatter([x], [yy], marker=EVENT_MARKER[ev["event_type"]],
                           s=340 if ev["event_type"] == "bridge_deposit" else 220,
                           color=EVENT_COLOR[ev["event_type"]], edgecolor="white",
                           linewidth=1.2, zorder=3)
            ax.annotate(f"+{dt_h:.1f}h", (x, 0.32), ha="center", va="bottom",
                        fontsize=10, color="#333333")
            if uniform_label is None:
                label = EVENT_VN[et] + (f" ×{n}" if n > 1 else "")
                ax.annotate(label, (x, -0.32), ha="center", va="top",
                            fontsize=10.5, color="#222222", fontweight="medium")

        if uniform_label is not None:
            ax.annotate(uniform_label, (sum(xs) / len(xs), -0.32), ha="center", va="top",
                        fontsize=11.5, color="#222222", fontweight="medium")

        if truncate_note:
            x_note = xs[-1] + X_STEP
            ax.annotate(truncate_note, (x_note, 0), ha="left", va="center",
                        fontsize=10.5, color="#555555", style="italic",
                        bbox=dict(boxstyle="round,pad=0.5", fc="#F4F4F4", ec="#BBBBBB", lw=1))
            return x_note + X_STEP * 2.3
        return xs[-1]

    t0_pos = pd.Timestamp(pos_shown[0][0])
    end_x1 = draw_row(ax1, pos_shown, t0_pos,
                       truncate_note=f"... còn {pos_hidden_n} hành động khác\n(xem phụ lục kỹ thuật)")
    ax1.set_xlim(-1.6, end_x1 + 0.6)
    ax1.set_ylim(-0.6, 0.6)
    ax1.axis("off")
    ax1.set_title(f"1) Positive — {pos_shown_n}/{len(pos_events)} hành động đầu tiên được hiển thị",
                  loc="left", fontsize=12.5, color="#8B0000", fontweight="bold")

    t0_neg = pd.Timestamp(neg_clusters[0][0])
    # Hard-negative: toan bo la 1 canh lap lai (khong phai mau phan tan/gom
    # tien that) - KHONG to nen vang, chi ghi 1 nhan chung 1 lan thay vi lap
    # lai 15 lan (tranh chong chu, van giu dung ban chat: khong co da dang
    # hanh vi nhu positive)
    end_x2 = draw_row(ax2, neg_clusters, t0_neg, show_motif_bg=False,
                       uniform_label=f"Qua cầu nối — lặp lại {len(neg_clusters)} lần, không hành vi nào khác")
    ax2.set_xlim(-1.6, max(end_x1, end_x2) + 0.6)
    ax2.set_ylim(-0.6, 0.6)
    ax2.axis("off")
    ax2.set_title(f"2) Hard-negative — toàn bộ {len(neg_events)} hành động",
                  loc="left", fontsize=12.5, color="#1B4F72", fontweight="bold")

    legend_elems = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=EVENT_COLOR["transfer"],
               markersize=13, label="Chuyển tiền"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=EVENT_COLOR["swap"],
               markersize=12, label="Đổi token"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor=EVENT_COLOR["bridge_deposit"],
               markersize=18, label="Qua cầu nối"),
        mpatches.Patch(facecolor="#FDF3D0", label="Có phân tán/gom tiền qua nhiều ví"),
    ]
    fig.legend(handles=legend_elems, loc="lower center", ncol=4, fontsize=11,
               frameon=False, bbox_to_anchor=(0.5, -0.02))

    fig.suptitle(
        "So sánh 1 vụ tấn công thật với 1 ví bình thường có hoạt động tương tự\n"
        "(cùng số hành động ở mức tương đương — không phải cứ dài là đáng ngờ)",
        fontsize=14.5, fontweight="bold", y=1.06
    )

    fig.text(0.5, -0.14,
              "Thời gian ghi là thời gian tương đối kể từ hành động đầu tiên của mỗi ví. "
              "Vùng nền vàng nhạt = đoạn có mẫu \"tiền tách ra rồi gom lại qua nhiều ví trung gian\" "
              "— chi tiết kỹ thuật đầy đủ xem results/figures/fig2_technical_appendix.md.",
              ha="center", fontsize=9.5, color="#555555")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Da luu: {out_path}")


# ---------------------------------------------------------------------------
# BAN KY THUAT (paper/phu luc) - day du nhan dia chi, chu giai, so lieu motif
# ---------------------------------------------------------------------------
ROW_HALF_HEIGHT = 0.42
X_STEP_TECH = 1.55


def draw_technical_row(ax, y, events, label, color_label, y_axis_lim):
    clusters = cluster_by_exact_timestamp(events)
    t0 = pd.Timestamp(clusters[0][0])
    xs = [i * X_STEP_TECH for i in range(len(clusters))]
    seen_signatures = {}

    motif_flags = [any(is_motif_action(ev) for ev in evs) for _, evs in clusters]
    ax.plot([xs[0], xs[-1]] if len(xs) > 1 else [xs[0], xs[0]], [y, y],
            color="#BBBBBB", lw=1.5, zorder=1, solid_capstyle="round")

    ylo, yhi = y_axis_lim
    span = yhi - ylo
    frac_lo = (y - ROW_HALF_HEIGHT - ylo) / span
    frac_hi = (y + ROW_HALF_HEIGHT - ylo) / span
    i = 0
    while i < len(xs):
        if motif_flags[i]:
            j = i
            while j < len(xs) and motif_flags[j]:
                j += 1
            ax.axvspan(xs[i] - X_STEP_TECH * 0.4, xs[j - 1] + X_STEP_TECH * 0.4,
                       ymin=frac_lo, ymax=frac_hi, color="#F9E79F", alpha=0.6, zorder=0, lw=0)
            i = j
        else:
            i += 1

    for x, (ts, evs) in zip(xs, clusters):
        dt_h = (pd.Timestamp(ts) - t0).total_seconds() / 3600.0
        n = len(evs)
        for k, ev in enumerate(evs):
            yy = y + (k - (n - 1) / 2.0) * 0.14
            highlighted = is_motif_action(ev)
            ax.scatter([x], [yy], marker=EVENT_MARKER[ev["event_type"]],
                       s=190 if ev["event_type"] == "bridge_deposit" else 100,
                       color=EVENT_COLOR[ev["event_type"]],
                       edgecolor="#0B0B0B" if highlighted else "white",
                       linewidth=1.6 if highlighted else 0.6,
                       zorder=4 if ev["event_type"] == "bridge_deposit" else 3)

        sign = 1 if y > 0 else -1
        ax.annotate(f"+{dt_h:.2f}h", (x, y + sign * 0.30), ha="center",
                    va="bottom" if sign > 0 else "top",
                    fontsize=7.5, color="#222222")

        seen_pairs = sorted({f"{node_label(ev['src'])}→{node_label(ev['dst'])} ({ev['token']})" for ev in evs})
        signature = tuple(seen_pairs)
        cnt_txt = f" x{n}" if n > 1 else ""
        if signature in seen_signatures:
            addr_txt = "(lặp lại)"
        else:
            seen_signatures[signature] = x
            addr_txt = "\n".join(seen_pairs)
        ax.annotate(addr_txt + cnt_txt, (x, y - sign * 0.30), ha="center",
                    va="top" if sign > 0 else "bottom",
                    fontsize=6.8, color="#444444", linespacing=1.4,
                    style="italic" if signature in seen_signatures and seen_signatures[signature] != x else "normal")

    ax.text(-1.3, y, label, ha="right", va="center", fontsize=10.5, fontweight="bold", color=color_label)
    return xs[-1] if xs else 0


def draw_technical(pos_events, neg_events, out_path: Path):
    fig = plt.figure(figsize=(13.5, 7.4))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.1, 1.75], hspace=0.28)
    ax = fig.add_subplot(gs[0])
    ax_leg = fig.add_subplot(gs[1])
    ax_leg.axis("off")

    y_axis_lim = (-2.6, 2.6)
    max_x_pos = draw_technical_row(ax, y=1.45, events=pos_events,
                                    label=f"POSITIVE\n{POS_ID}\n(n={len(pos_events)} action)",
                                    color_label="#8B0000", y_axis_lim=y_axis_lim)
    max_x_neg = draw_technical_row(ax, y=-1.45, events=neg_events,
                                    label=f"HARD-NEGATIVE (mined)\n{NEG_ID}\n(n={len(neg_events)} action)",
                                    color_label="#1B4F72", y_axis_lim=y_axis_lim)

    max_x = max(max_x_pos, max_x_neg, 1)
    ax.set_xlim(-5.4, max_x + 1.6)
    ax.set_ylim(*y_axis_lim)
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        "Fig. 2 (technical) — So sánh trajectory positive vs hard-negative band-matched "
        "(chain: Arbitrum, chain_id=42161, cả hai)\n"
        "Nền vàng = vùng khớp định nghĩa motif_split/motif_merge "
        "(_motif_features(), dựa trên fan-out/fan-in ≥2 cạnh toàn cục)",
        fontsize=10.5, loc="left", pad=10,
    )

    legend_elems = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=EVENT_COLOR["transfer"],
               markersize=9, label="transfer"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=EVENT_COLOR["swap"],
               markersize=8, label="swap"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor=EVENT_COLOR["bridge_deposit"],
               markersize=13, label="bridge_deposit"),
        mpatches.Patch(facecolor="#F9E79F", alpha=0.55, label="motif split/merge region"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
               markeredgecolor="black", markeredgewidth=1.3, markersize=9,
               label="action là 1 cạnh của motif (viền đen)"),
    ]
    ax_leg.set_xlim(0, 1)
    ax_leg.set_ylim(0, 1)
    ax_leg.legend(handles=legend_elems, loc="upper center", bbox_to_anchor=(0.5, 1.06),
                  ncol=5, fontsize=8.3, frameon=False)

    node_legend_lines = [f"{lbl} = {short(addr)} ({role})" for addr, (lbl, role) in NODE_LABELS.items()]
    ax_leg.text(0.0, 0.72, "Chú giải nhãn địa chỉ (địa chỉ đầy đủ bị rút gọn còn "
                           "6 ký tự đầu, xem metadata/incident_registry.csv):",
                ha="left", va="top", fontsize=8, color="#222222", fontweight="bold")
    ax_leg.text(0.0, 0.58, "\n".join(node_legend_lines[:4]), ha="left", va="top",
                fontsize=7.6, color="#444444", linespacing=1.7)
    ax_leg.text(0.5, 0.58, "\n".join(node_legend_lines[4:]), ha="left", va="top",
                fontsize=7.6, color="#444444", linespacing=1.7)

    ax_leg.text(0.5, 0.14,
                "Ghi chú: case hard-negative đã đổi từ deltaprime_benign_control_2024 (1 action) sang\n"
                "deltaprime_arbitrum_2024__hn051 (15 action, band-matched) để tránh lệch độ dài quá lớn\n"
                "(23 vs 1) — xem results/figures/fig2_technical_appendix.md để biết đầy đủ lý do & số liệu.",
                ha="center", va="top", fontsize=7.6, color="#444444")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Da luu: {out_path}")


def write_appendix(pos_events, neg_events, out_path: Path):
    df = pd.read_parquet(PROCESSED_DIR / "features_v2.parquet")
    motif_cols = [c for c in df.columns if c.startswith("motif_")]
    pos_motif = df[(df["source_id"] == POS_ID) & (df["prefix_label"] == "ratio_100")][motif_cols].iloc[0]
    neg_motif = df[(df["source_id"] == NEG_ID) & (df["prefix_label"] == "ratio_100")][motif_cols].iloc[0]

    lines = []
    lines.append("# Fig. 2 — Phụ lục kỹ thuật đầy đủ\n")
    lines.append(
        "Tài liệu này chứa toàn bộ chi tiết kỹ thuật đã lược bỏ khỏi "
        "`fig2_simplified_for_slide.png` (nhãn địa chỉ, số liệu motif, danh sách "
        "action đầy đủ) để bản dùng cho slide không quá tải thông tin. Bản "
        "`fig2_technical_full.png` giữ lại các chi tiết này trực tiếp trên hình; "
        "tài liệu này bổ sung phần không thể hiện hết trên hình (bảng action đầy đủ).\n"
    )

    lines.append("## Lý do chọn case\n")
    lines.append(
        f"- **Positive**: `{POS_ID}` — {len(pos_events)} action (không đổi so với "
        "bản vẽ đầu tiên).\n"
        f"- **Hard-negative**: đổi từ `deltaprime_benign_control_2024` (1 action, "
        f"control gốc theo incident) sang `{NEG_ID}` ({len(neg_events)} action, "
        "**hard-negative đã MINE**, có trong `metadata/hard_negative_registry.csv`, "
        "cùng tiêu chí band-matched của Giai đoạn B).\n"
        "- Lý do đổi: cặp gốc lệch độ dài quá lớn (23 vs 1 action) — có rủi ro vô "
        "tình minh họa đúng \"shortcut về độ dài\" mà dự án đã chứng minh và loại bỏ "
        "(tiêu chí fan_out band-matched, xem `results/reports/fanout_band_v3_mining_v1.md`). "
        f"`{NEG_ID}` (15 action) gần hơn nhiều so với 23 của positive.\n"
    )

    lines.append("## Chú giải nhãn địa chỉ (áp dụng cho cả 2 trajectory)\n\n")
    lines.append("| Mã | Địa chỉ đầy đủ | Vai trò |\n|---|---|---|\n")
    for addr, (lbl, role) in NODE_LABELS.items():
        lines.append(f"| {lbl} | `{addr}` | {role} |\n")

    lines.append("\n## Số liệu motif (features_v2.parquet, prefix_label=ratio_100)\n\n")
    lines.append("| Motif feature | Positive (23 action) | Hard-negative hn051 (15 action) |\n|---|---|---|\n")
    for c in motif_cols:
        lines.append(f"| {c} | {pos_motif[c]:.1f} | {neg_motif[c]:.1f} |\n")
    lines.append(
        "\n**Lưu ý quan trọng**: `motif_split=1.0, motif_merge=1.0` của hard-negative "
        "là trường hợp **thoái hóa** (degenerate) — 1 địa chỉ lặp lại đúng 1 cạnh "
        "(seed → cùng 1 contract cầu nối) 15 lần, kỹ thuật thỏa mãn ngưỡng \"≥2 cạnh\" "
        "của định nghĩa `_motif_features()` nhưng KHÔNG phải mẫu \"phân tán qua nhiều "
        "ví trung gian\" thật như ở positive (nơi motif_split/merge=3.0 phản ánh 3 địa "
        "chỉ KHÁC NHAU mỗi địa chỉ có ≥2 cạnh, tạo thành chuỗi layering nhiều tầng thật "
        "sự). Đây là lý do bản `fig2_simplified_for_slide.png` KHÔNG tô nền vàng cho "
        "hàng hard-negative — tránh gây hiểu lầm rằng nó cũng có \"mẫu đáng ngờ\" như "
        "positive.\n"
    )

    for name, events in [("Positive — " + POS_ID, pos_events), ("Hard-negative — " + NEG_ID, neg_events)]:
        lines.append(f"\n## Toàn bộ {len(events)} action — {name}\n\n")
        lines.append("| # | Thời gian (UTC) | +Xh | Loại | Src | Dst | Token |\n|---|---|---|---|---|---|---|\n")
        t0 = pd.Timestamp(events[0]["timestamp"])
        for i, ev in enumerate(events, start=1):
            dt_h = (pd.Timestamp(ev["timestamp"]) - t0).total_seconds() / 3600.0
            lines.append(
                f"| {i} | {ev['timestamp']} | +{dt_h:.2f}h | {ev['event_type']} | "
                f"{node_label(ev['src'])} (`{short(ev['src'])}`) | "
                f"{node_label(ev['dst'])} (`{short(ev['dst'])}`) | {ev['token']} |\n"
            )

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"Da luu: {out_path}")


def main():
    pos_events = load_events(POS_ID)
    neg_events = load_events(SCRATCH_HN051)
    print(f"positive n={len(pos_events)}  hard-negative(hn051) n={len(neg_events)}")

    draw_simplified(pos_events, neg_events, FIG_DIR / "fig2_simplified_for_slide.png")
    draw_technical(pos_events, neg_events, FIG_DIR / "fig2_technical_full.png")
    write_appendix(pos_events, neg_events, FIG_DIR / "fig2_technical_appendix.md")


if __name__ == "__main__":
    main()
