"""Ve Fig. 4 cho paper: duong cong risk probability theo % quan sat (prefix
ratio) cho 1 case study, danh dau First alert + Endpoint (ground truth) +
lead time that. Toan bo so lieu doc THAT tu:
  - data/processed/rq2_oof_predictions.csv (oof_prob, oof_threshold tung
    prefix bucket - LUU Y: threshold KHAC NHAU theo tung bucket, khong phai
    1 nguong global - ban "technical" ve ca 2 duong de trung thuc)
  - results/tables/lead_time_results.csv (alert_prefix_len/bucket, te,
    lead_time_sec, lead_steps)
  - metadata/incident_registry.csv (endpoint_confirmed, endpoint_type)
  - data/processed/{incident_id}_events.json (vi tri that cua action te
    trong trajectory, de dinh vi moc Endpoint tren truc % quan sat)

Lich su chon case (xem hoi thoai): qbridge_qubit_2022 (case Tuan 7) khong co
endpoint_confirmed=True nen bi loai. radiant_capital_arbitrum_2024 co du
dieu kien nhung endpoint qua som (2.8% trajectory) - kho minh hoa truc giac
"phat hien som truoc khi ket thuc". Sau khi liet ke toan bo 10 incident du
dieu kien va ap 3 tieu chi (endpoint cang tre cang tot / uu tien phat hien
som thanh cong / <50 action), chon chibi_finance_2023 - incident DUY NHAT
thoa ca 3 tieu chi dong thoi (endpoint o 47.5% trajectory - cao nhat trong
tat ca, alert thanh cong truoc endpoint +449s, chi 40 action). Da bao cao
va duoc nguoi dung xac nhan qua AskUserQuestion truoc khi ve.

Xuat 2 ban:
  - fig4_simplified_for_slide.png : bo duong nguong (dao dong manh, kho giai
    thich nhanh tren slide), chi giu risk curve + First alert + Endpoint.
  - fig4_technical_full.png : day du ca duong nguong rieng tung moc prefix,
    dung cho paper/phu luc.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
FIG_DIR = REPO_ROOT / "results" / "figures"

INCIDENT_ID = "chibi_finance_2023"


def load_case_data(incident_id: str):
    oof = pd.read_csv(PROCESSED_DIR / "rq2_oof_predictions.csv")
    q = oof[(oof["source_id"] == incident_id) & (oof["label"] == 1)].copy()
    q = q.sort_values("prefix_len").reset_index(drop=True)

    lt = pd.read_csv(REPO_ROOT / "results" / "tables" / "lead_time_results.csv")
    lt_row = lt[lt["incident_id"] == incident_id].iloc[0]

    reg = pd.read_csv(REPO_ROOT / "metadata" / "incident_registry.csv")
    reg_row = reg[reg["incident_id"] == incident_id].iloc[0]

    events = json.loads((PROCESSED_DIR / f"{incident_id}_events.json").read_text(encoding="utf-8"))
    events_sorted = sorted(events, key=lambda a: a["timestamp"])
    n_total = len(events_sorted)

    te = pd.Timestamp(lt_row["te"])
    te_action_type = lt_row["te_action_type"]
    te_idx = None
    for i, ev in enumerate(events_sorted, start=1):
        if pd.Timestamp(ev["timestamp"]) == te and ev["event_type"] == te_action_type:
            te_idx = i
            break
    assert te_idx is not None, "khong tim thay action te trong trajectory - kiem tra lai du lieu"

    q["pct_observed"] = q["prefix_len"] / n_total * 100.0
    span_h = (pd.Timestamp(events_sorted[-1]["timestamp"]) - pd.Timestamp(events_sorted[0]["timestamp"])).total_seconds() / 3600.0

    return {
        "q": q, "lt_row": lt_row, "reg_row": reg_row, "n_total": n_total,
        "te": te, "te_action_type": te_action_type, "te_idx": te_idx,
        "te_pct": te_idx / n_total * 100.0, "span_h": span_h,
    }


def compute_label_offsets(q: pd.DataFrame, te_pct: float, alert_pct: float):
    """Dat nhan phia TREN diem cuc dai cuc bo, phia DUOI diem cuc tieu cuc
    bo (tranh de nhan de len duong noi 2 canh doc len/xuong quanh diem do);
    day nhan ra xa neu qua gan moc Endpoint hoac First alert (tranh chong
    chu voi 2 duong doc)."""
    probs = q["oof_prob"].tolist()
    offsets = {}
    for i, (_, r) in enumerate(q.iterrows()):
        left = probs[i - 1] if i > 0 else probs[i]
        right = probs[i + 1] if i < len(probs) - 1 else probs[i]
        is_local_min = probs[i] < left and probs[i] < right
        dy = -22 if is_local_min else 12
        dx = 0
        x = r["pct_observed"]
        if abs(x - te_pct) < max(te_pct, 1.0) * 0.08:
            dx = 16
        elif abs(x - alert_pct) < max(alert_pct, 1.0) * 0.15:
            dx = -14
        offsets[r["prefix_label"]] = (dx, dy)
    return offsets


def draw_figure(data: dict, incident_id: str, out_path: Path, simplified: bool):
    q = data["q"]
    lt_row = data["lt_row"]
    reg_row = data["reg_row"]
    n_total = data["n_total"]
    te = data["te"]
    te_action_type = data["te_action_type"]
    te_idx = data["te_idx"]
    te_pct = data["te_pct"]
    span_h = data["span_h"]

    alert_prefix_len = int(lt_row["alert_prefix_len"])
    alert_bucket = lt_row["alert_prefix_bucket"]
    lead_time_min = lt_row["lead_time_sec"] / 60.0
    lead_steps = int(lt_row["lead_steps"])
    alert_pct = alert_prefix_len / n_total * 100.0

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.set_xscale("log")

    ax.plot(q["pct_observed"], q["oof_prob"], marker="o", color="#1B4F72",
            lw=2.2, markersize=7, label="Risk probability (OOF) — thực đo", zorder=3)
    if not simplified:
        ax.plot(q["pct_observed"], q["oof_threshold"], marker="s", color="#B7950B",
                lw=1.4, markersize=5, linestyle="--",
                label="Ngưỡng quyết định (riêng từng mốc prefix)", zorder=2)

    label_offsets = compute_label_offsets(q, te_pct, alert_pct)
    for _, r in q.iterrows():
        dx, dy = label_offsets[r["prefix_label"]]
        ax.annotate(r["prefix_label"], (r["pct_observed"], r["oof_prob"]),
                    textcoords="offset points", xytext=(dx, dy), ha="center",
                    va="bottom" if dy > 0 else "top",
                    fontsize=8, color="#1B4F72")

    # First alert
    ax.axvline(alert_pct, color="#C0392B", linestyle=":", lw=1.5, zorder=1)
    ax.scatter([alert_pct], [q.loc[q["prefix_label"] == alert_bucket, "oof_prob"].iloc[0]],
               marker="*", s=280, color="#C0392B", edgecolor="black", linewidth=0.8, zorder=5,
               label=f"First alert ({alert_bucket})")

    # Endpoint (ground truth)
    ax.axvline(te_pct, color="#117A65", linestyle="-.", lw=1.7, zorder=1)
    ax.text(te_pct, 1.10, "Endpoint\n(ground truth)", ha="center", va="bottom",
            fontsize=8.5, color="#117A65", fontweight="bold")

    ax.text(alert_pct, -0.11, f"First alert\n+{alert_pct:.1f}%", ha="center", va="top",
            fontsize=8.5, color="#C0392B", fontweight="bold", transform=ax.get_xaxis_transform())

    ax.set_ylim(-0.02, 1.30)
    ax.set_xlim(q["pct_observed"].min() * 0.7, 115)
    ax.set_xlabel("% trajectory đã quan sát (prefix ratio, thang log)", fontsize=10.5)
    ax.set_ylabel("Risk probability (OOF)", fontsize=10.5)

    title = (
        f"Risk probability theo prefix — {incident_id}\n"
        f"Alert tại {alert_bucket} ({alert_pct:.1f}% trajectory) — "
        f"sớm hơn {lead_time_min:.2f} phút so với endpoint ({te_pct:.1f}% trajectory)"
    )
    ax.set_title(title, fontsize=10.5, loc="left")
    ax.grid(True, which="both", axis="x", alpha=0.25)
    ax.grid(True, which="major", axis="y", alpha=0.25)
    ax.legend(loc="lower left", fontsize=8.5, frameon=True)

    footnote = (
        f"Endpoint that: {te_action_type} lúc {te:%Y-%m-%d %H:%M} UTC "
        f"(action {te_idx}/{n_total} = {te_pct:.1f}% trajectory, "
        f"endpoint_type={reg_row['endpoint_type']}). "
        f"First alert: {alert_bucket} ({alert_prefix_len}/{n_total} action) → "
        f"lead time = {lt_row['lead_time_sec']:.0f}s ({lead_time_min:.2f} phút), "
        f"{lead_steps} action còn lại sau alert. "
        f"Nguồn: data/processed/rq2_oof_predictions.csv (OOF, mô hình M1), "
        f"results/tables/lead_time_results.csv, metadata/incident_registry.csv. "
        f"Toàn bộ trajectory dài {n_total} action / {span_h:.1f}h."
    )
    fig.text(0.5, -0.08, footnote, ha="center", fontsize=7.5, color="#444444", wrap=True)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Da luu: {out_path}")


def main():
    data = load_case_data(INCIDENT_ID)
    draw_figure(data, INCIDENT_ID, FIG_DIR / "fig4_technical_full.png", simplified=False)
    draw_figure(data, INCIDENT_ID, FIG_DIR / "fig4_simplified_for_slide.png", simplified=True)


if __name__ == "__main__":
    main()
