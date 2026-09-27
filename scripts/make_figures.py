"""Ve toan bo hinh thuc nghiem cua paper tu results/tables/ + data/processed/exp/.

Moi panel la 1 file PDF vector rieng, dat ten figNx.pdf (vd fig3a.pdf,
fig3b.pdf) trong paper/figures/, de ghep trong LaTeX bang subcaption.
Figure 1 (kien truc) ve tay bang draw.io, khong sinh o day.

    python scripts/make_figures.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TAB = REPO_ROOT / "results" / "tables"
EXP = REPO_ROOT / "data" / "processed" / "exp"
OUT = REPO_ROOT / "paper" / "figures"

# Mau co dinh theo THUC THE (khong theo thu hang) — palette da validate
# (dataviz reference, light mode). Nhan dang khong chi bang mau: kem marker
# + linestyle + nhan truc tiep.
C = {"M1": "#2a78d6", "B3p": "#eb6834", "B3": "#1baf7a", "B1": "#eda100", "B2": "#e87ba4", "B0": "#8c8b87"}
NEG = "#8c8b87"
INK = "#0b0b0b"
INK2 = "#52514e"
LABEL = {"M1": "M1 (typed+motif, XGB)", "B3p": "B3$'$ (flat, XGB)", "B3": "B3 (flat, RF)",
         "B1": "B1 (rules)", "B2": "B2 (bag-of-actions)", "B0": "B0 (prevalence)"}
MARK = {"M1": "o", "B3p": "s", "B3": "^", "B1": "D", "B2": "v", "B0": "x"}
LS = {"M1": "-", "B3p": "--", "B3": "-.", "B1": ":", "B2": ":", "B0": ":"}

W1 = 3.3   # 1 panel trong 1 hang 2 panel (inch)
H1 = 2.35

plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 6.5, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.5,
    "lines.linewidth": 1.5, "lines.markersize": 4, "legend.frameon": False, "pdf.fonttype": 42,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=200)
    plt.close(fig)
    print("  ->", name)


def load(name):
    with open(EXP / f"{name}.pkl", "rb") as f:
        return pickle.load(f)


def csv(name):
    return pd.read_csv(TAB / name)


# ----------------------------------------------------------------------
# Fig 2 — dataset
# ----------------------------------------------------------------------
def fig2():
    trajs = load("trajectories")
    pos = np.array([len(t["trajectory"]) for t in trajs if t["label"] == 1])
    neg = np.array([len(t["trajectory"]) for t in trajs if t["label"] == 0])
    fig, ax = plt.subplots(figsize=(W1, H1))
    for arr, col, lab, ls in ((pos, C["M1"], f"incident ($n$={len(pos)})", "-"),
                              (neg, NEG, f"hard negative ($n$={len(neg)})", "--")):
        x = np.sort(arr)
        ax.step(x, np.arange(1, len(x) + 1) / len(x), where="post", color=col, ls=ls, label=lab)
    ax.set_xscale("log")
    ax.set_xlabel("trajectory length $n$ (actions, log scale)")
    ax.set_ylabel("cumulative fraction")
    ax.legend(loc="lower right")
    save(fig, "fig2a")

    types = ["transfer", "swap", "bridge_deposit", "bridge_withdraw", "split", "merge",
             "lending_deposit", "mixer_or_exit"]
    short = ["transfer", "swap", "bridge dep.", "bridge wdr.", "split", "merge", "lending", "mixer/exit"]
    comp = {}
    for lab, name in ((1, "incident"), (0, "negative")):
        cnt = pd.Series([a.event_type for t in trajs if t["label"] == lab for a in t["trajectory"].actions]).value_counts()
        tot = cnt.sum()
        # ty le trung binh theo trajectory (tranh 1 incident dai ap dao)
        per = []
        for t in trajs:
            if t["label"] != lab or not len(t["trajectory"]):
                continue
            c = pd.Series([a.event_type for a in t["trajectory"].actions]).value_counts(normalize=True)
            per.append([c.get(k, 0.0) for k in types])
        comp[name] = np.mean(per, axis=0)
    fig, ax = plt.subplots(figsize=(W1, H1))
    y = np.arange(len(types))
    ax.barh(y - 0.2, comp["incident"], height=0.38, color=C["M1"], label="incident")
    ax.barh(y + 0.2, comp["negative"], height=0.38, color=NEG, label="hard negative", hatch="////", edgecolor="white", linewidth=0)
    ax.set_yticks(y, short)
    ax.invert_yaxis()
    ax.set_xscale("symlog", linthresh=0.01)
    ax.set_xlabel("mean share of actions per trajectory")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    save(fig, "fig2b")


# ----------------------------------------------------------------------
# Fig 3 — RQ1
# ----------------------------------------------------------------------
def fig3():
    oof = pd.read_csv(REPO_ROOT / "data" / "processed" / "oof_predictions_v3.csv")
    main = csv("rq1_main.csv").set_index("model")
    fig, ax = plt.subplots(figsize=(W1, H1))
    for m in ("M1", "B3p", "B3", "B1", "B2"):
        p, r, _ = precision_recall_curve(oof.label, oof[f"oof_{m}"])
        ax.step(r, p, where="post", color=C[m], ls=LS[m],
                label=f"{LABEL[m]}  {main.loc[m, 'pooled_pr_auc']:.3f}")
    ax.axhline(oof.label.mean(), color=NEG, lw=0.8, ls=":")
    ax.text(0.99, oof.label.mean() + 0.015, f"prevalence {oof.label.mean():.3f}", ha="right", va="bottom", color=INK2, fontsize=6.5)
    ax.set_xlabel("recall")
    ax.set_ylabel("precision")
    ax.set_ylim(0, 1.02)
    ax.legend(loc="upper right", title="pooled PR-AUC", title_fontsize=6.5)
    save(fig, "fig3a")

    per = csv("rq1_per_incident.csv")
    fig, ax = plt.subplots(figsize=(W1, H1))
    per = per.sort_values("M1")
    y = np.arange(len(per))
    for i, (a, b) in enumerate(zip(per["B3p"], per["M1"])):
        ax.plot([a, b], [i, i], color="#c3c2b7", lw=1, zorder=1)
    ax.scatter(per["B3p"], y, marker=MARK["B3p"], color=C["B3p"], s=16, label=LABEL["B3p"], zorder=2)
    ax.scatter(per["M1"], y, marker=MARK["M1"], color=C["M1"], s=16, label=LABEL["M1"], zorder=3)
    ax.set_yticks(y, [s.replace("_", " ") for s in per["incident_id"]], fontsize=5.5)
    ax.set_xlabel("per-incident PR-AUC (held-out fold)")
    ax.set_xlim(-0.02, 1.02)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=6)
    save(fig, "fig3b")

    rep = main.loc[[f"rep:{k}" for k in ("Flat", "Flat+Types", "Flat+Motifs", "Flat+Types+Motifs")]]
    fig, ax = plt.subplots(figsize=(W1, H1))
    x = np.arange(len(rep))
    err = np.vstack([rep.pooled_pr_auc - rep.ci_low, rep.ci_high - rep.pooled_pr_auc])
    cols = [C["B3p"], "#9aa9bf", "#9aa9bf", C["M1"]]
    ax.bar(x, rep.pooled_pr_auc, width=0.55, color=cols)
    ax.errorbar(x, rep.pooled_pr_auc, yerr=err, fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2)
    for xi, v in zip(x, rep.pooled_pr_auc):
        ax.text(xi, 0.02, f"{v:.3f}", ha="center", va="bottom", color="white", fontsize=6.5, fontweight="bold")
    ax.set_xticks(x, ["flat", "flat+types", "flat+motifs", "flat+types\n+motifs (M1)"])
    ax.set_ylabel("pooled PR-AUC (95% CI)")
    ax.set_ylim(0, 1)
    ax.grid(axis="x", visible=False)
    save(fig, "fig3c")


# ----------------------------------------------------------------------
# Fig 4 — RQ2 early detection
# ----------------------------------------------------------------------
def fig4():
    cp = csv("rq2_checkpoints.csv")
    rel = cp[cp.checkpoint.str.startswith("ratio")].copy()
    rel["x"] = rel.checkpoint.str.replace("ratio_", "").astype(int)
    fig, ax = plt.subplots(figsize=(W1, H1))
    for m in ("M1", "B3p"):
        ax.fill_between(rel.x, rel[f"{m}_ci_low"], rel[f"{m}_ci_high"], color=C[m], alpha=0.12, lw=0)
        ax.plot(rel.x, rel[f"{m}_pr_auc"], color=C[m], ls=LS[m], marker=MARK[m], label=LABEL[m])
    ax.plot(rel.x, rel.pos_rate, color=NEG, ls=":", lw=1, label="prevalence")
    ax.set_xticks(rel.x, [f"{v}%" for v in rel.x])
    ax.set_xlabel("observed fraction of trajectory (retrospective)")
    ax.set_ylabel("PR-AUC (95% CI)")
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right")
    save(fig, "fig4a")

    hz = csv("rq2_time_horizons.csv")
    fig, ax = plt.subplots(figsize=(W1, H1))
    x = np.arange(len(hz))
    for m in ("M1", "B3p"):
        ax.fill_between(x, hz[f"{m}_ci_low"], hz[f"{m}_ci_high"], color=C[m], alpha=0.12, lw=0)
        ax.plot(x, hz[f"{m}_pr_auc"], color=C[m], ls=LS[m], marker=MARK[m], label=LABEL[m])
    ax.plot(x, hz.pos_rate, color=NEG, ls=":", lw=1, label="prevalence")
    lab = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "1h", 180: "3h", 720: "12h", 1440: "24h"}
    ax.set_xticks(x, [lab.get(v, str(v)) for v in hz.horizon_min])
    ax.set_xlabel("time since first outgoing action (online)")
    ax.set_ylabel("PR-AUC (95% CI)")
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right")
    save(fig, "fig4b")

    online = load("online_scores")
    grid = np.linspace(0, 1, 21)
    fig, ax = plt.subplots(figsize=(W1, H1))
    for lab_, col, ls, name in ((1, C["M1"], "-", "incident"), (0, NEG, "--", "hard negative")):
        mat = []
        for o in online:
            if o["label"] != lab_ or o["n"] < 4:
                continue
            frac = o["ks"] / o["n"]
            mat.append(np.interp(grid, frac, o["cal"], left=o["cal"][0]))
        mat = np.array(mat)
        q1, med, q3 = np.percentile(mat, [25, 50, 75], axis=0)
        ax.fill_between(grid * 100, q1, q3, color=col, alpha=0.15, lw=0)
        ax.plot(grid * 100, med, color=col, ls=ls, label=f"{name} median, IQR ($n$={len(mat)})")
    ax.set_xlabel("prefix position $k/n$ (%)")
    ax.set_ylabel("calibrated score $\\hat p_k$")
    ax.set_ylim(0, 1.02)
    ax.legend(loc="center right")
    save(fig, "fig4c")


# ----------------------------------------------------------------------
# Fig 5 — alerting, lead time, case study
# ----------------------------------------------------------------------
def fig5():
    al = csv("rq2_alerting.csv").sort_values("theta")
    fig, ax = plt.subplots(figsize=(W1, H1))
    ax.plot(al.false_alert_rate * 100, al.detected_before / al.n_endpoint * 100, color=C["M1"], marker="o", ms=3,
            label="alert before endpoint")
    ax.plot(al.false_alert_rate * 100, al.pos_alerted_any / al.n_pos * 100, color=C["M1"], ls="--", marker="s", ms=3,
            label="alert at any time")
    for th in (0.3, 0.5, 0.7, 0.9):
        r = al[np.isclose(al.theta, th)]
        if len(r):
            ax.annotate(f"$\\theta$={th}", (r.false_alert_rate.iloc[0] * 100, r.detected_before.iloc[0] / r.n_endpoint.iloc[0] * 100),
                        textcoords="offset points", xytext=(4, -9), fontsize=6, color=INK2)
    ax.set_xlabel("false-alert rate on hard negatives (% trajectories)")
    ax.set_ylabel("incidents alerted (%)")
    ax.set_ylim(0, 102)
    ax.legend(loc="lower right")
    save(fig, "fig5a")

    per = csv("rq2_alerting_per_incident.csv")
    per = per[np.isclose(per.theta, 0.5)].copy().sort_values("lead_sec")
    fig, ax = plt.subplots(figsize=(W1, H1))
    y = np.arange(len(per))
    lead_min = per.lead_sec / 60
    colors = [C["M1"] if b else C["B3p"] for b in per.before_endpoint]
    ax.axvline(0, color=INK2, lw=0.8)
    ax.scatter(np.sign(lead_min) * np.log10(1 + np.abs(lead_min)), y, c=colors, s=18, zorder=3)
    for yi, (lm, ls_) in enumerate(zip(lead_min, per.lead_steps)):
        ax.text(np.sign(lm) * np.log10(1 + abs(lm)) + (0.08 if lm >= 0 else -0.08), yi,
                f"{lm:+.0f} min, {ls_:+d} steps", va="center", ha="left" if lm >= 0 else "right", fontsize=5.5, color=INK2)
    ax.set_yticks(y, [s.replace("_", " ") for s in per.incident], fontsize=5.5)
    ticks = [-1000, -100, -10, 0, 10, 100, 1000]
    ax.set_xticks([np.sign(t) * np.log10(1 + abs(t)) for t in ticks], [str(t) for t in ticks])
    ax.set_xlim(-4.2, 4.2)
    ax.set_xlabel("lead time $t_e - t_a$ at $\\theta$=0.5 (minutes, symlog)")
    ax.grid(axis="y", visible=False)
    ax.text(0.98, 0.02, "left of 0: late", transform=ax.transAxes, ha="right", fontsize=6, color=INK2)
    save(fig, "fig5b")

    # case study: incident co lead time duong lon nhat trong so incident co >=20 action
    online = {o["source_id"]: o for o in load("online_scores")}
    cs = csv("case_study_shap.csv")
    inc = pick_case_incident()
    o = online[inc]
    fig, ax = plt.subplots(figsize=(W1, H1))
    t0 = o["ts"][0]
    tt = (o["ts"][o["ks"] - 1] - t0) / 60
    ax.step(tt, o["cal"], where="post", color=C["M1"], label="M1 calibrated $\\hat p_k$")
    ax.step(tt, o["raw_b3p"], where="post", color=C["B3p"], ls="--", lw=1, label="B3$'$ raw score")
    ax.axhline(0.5, color=INK2, lw=0.7, ls=":")
    e = o["endpoint_idx"]
    if e:
        te = (o["ts"][e - 1] - t0) / 60
        ax.axvline(te, color="#e34948", lw=1, ls="-.")
        ax.text(te, 1.03, " endpoint $t_e$", color="#e34948", fontsize=6, va="bottom")
    hit = np.where(o["cal"] >= 0.5)[0]
    if len(hit):
        ta = tt[hit[0]]
        ax.axvline(ta, color=INK2, lw=0.8, ls="--")
        ax.text(ta, 1.03, "first alert $t_a$ ", color=INK2, fontsize=6, va="bottom", ha="right")
    ax.set_xscale("symlog", linthresh=1)
    ax.set_xlabel(f"minutes since first action ({inc.replace('_', ' ')})")
    ax.set_ylabel("score")
    ax.set_ylim(0, 1.1)
    ax.legend(loc="lower right")
    save(fig, "fig5c")


def pick_case_incident():
    per = csv("rq2_alerting_per_incident.csv")
    per = per[np.isclose(per.theta, 0.5) & per.before_endpoint]
    inc = csv("incident_table.csv").set_index("incident_id")
    per = per[per.incident.map(inc.n_actions) >= 20]
    if "chibi_finance_2023" in set(per.incident):
        return "chibi_finance_2023"
    return per.sort_values("lead_sec", ascending=False).incident.iloc[0]


# ----------------------------------------------------------------------
# Fig 6 — ablation, calibration, stress
# ----------------------------------------------------------------------
def fig6():
    pr = csv("rq1_paired.csv")
    rows = [("abl:no_temporal", "M1", "$-$ temporal"), ("abl:no_motif", "M1", "$-$ motifs"),
            ("abl:no_typed_action", "M1", "$-$ typed actions"), ("abl:no_bridge_context", "M1", "$-$ bridge context"),
            ("nested_select", "M1", "nested selection"),
            ("M1", "B3p", "M1 $-$ B3$'$"), ("M1", "B3", "M1 $-$ B3")]
    fig, ax = plt.subplots(figsize=(W1, H1))
    for i, (a, b, lab) in enumerate(rows):
        r = pr[(pr.a == a) & (pr.b == b)].iloc[0]
        col = C["M1"] if i >= 5 else INK2
        ax.plot([r.ci_low, r.ci_high], [i, i], color=col, lw=1.2)
        ax.scatter([r.point], [i], color=col, s=16, zorder=3)
        ax.text(0.99, i, f"{r.point:+.3f}  $p$={r.p_value:.2f}", transform=ax.get_yaxis_transform(), ha="right",
                va="center", fontsize=5.8, color=INK2)
    ax.axvline(0, color=INK2, lw=0.7)
    ax.set_yticks(range(len(rows)), [r[2] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel("$\\Delta$ pooled PR-AUC vs. reference (95% bootstrap CI)")
    ax.grid(axis="y", visible=False)
    save(fig, "fig6a")

    rel = csv("calibration_reliability.csv")
    cal = csv("calibration.csv").set_index("method")
    fig, ax = plt.subplots(figsize=(W1, H1))
    ax.plot([0, 1], [0, 1], color="#c3c2b7", lw=0.8)
    sty = {"raw": (NEG, "--", "x"), "isotonic": (C["B3"], "-.", "^"), "platt": (C["M1"], "-", "o")}
    for mth, (col, ls, mk) in sty.items():
        r = rel[rel.method == mth]
        ax.plot(r.mean_pred, r.frac_pos, color=col, ls=ls, marker=mk,
                label=f"{mth}: ECE {cal.loc[mth, 'ece']:.3f}, Brier {cal.loc[mth, 'brier']:.3f}")
    ax.set_xlabel("mean predicted probability (10 bins)")
    ax.set_ylabel("observed positive fraction")
    ax.legend(loc="upper left")
    save(fig, "fig6b")

    st = csv("stress_mimicry.csv")
    fig, ax = plt.subplots(figsize=(W1, H1))
    ax.plot(st.j, st.detect_rate_0_5 * 100, color=C["M1"], marker="o", label="incidents alerted ($\\theta$=0.5)")
    ax.plot(st.j, st.mean_score_25 * 100, color=C["M1"], ls="--", marker="s", label="mean $\\hat p$ at 25% (×100)")
    ax.set_xticks(st.j)
    ax.set_xlabel("benign decoy transfers inserted after each action ($j$)")
    ax.set_ylabel("%")
    ax.set_ylim(0, 102)
    ax.legend(loc="lower left")
    save(fig, "fig6c")


# ----------------------------------------------------------------------
# Fig 7 — explanation + cost
# ----------------------------------------------------------------------
def fig7():
    imp = csv("shap_global.csv").head(12).iloc[::-1]
    gcol = {"flat": C["B3p"], "typed_action": C["M1"], "motif": C["B3"]}
    fig, ax = plt.subplots(figsize=(W1, H1 + 0.3))
    ax.barh(range(len(imp)), imp.mean_abs_shap, color=[gcol.get(g, NEG) for g in imp.group], height=0.6)
    ax.set_yticks(range(len(imp)), [f.replace("_", " ") for f in imp.feature], fontsize=6)
    ax.set_xlabel("mean |SHAP| (log-odds)")
    ax.grid(axis="y", visible=False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=v, label=k.replace("_", " ")) for k, v in gcol.items()], loc="lower right")
    save(fig, "fig7a")

    rt = csv("runtime.csv")
    fig, ax = plt.subplots(figsize=(W1, H1))
    ax.plot(rt.n_events, rt.median_ms, color=C["M1"], marker="o", label="median")
    ax.plot(rt.n_events, rt.p95_ms, color=C["M1"], ls="--", marker="s", lw=1, label="95th percentile")
    ax.set_xscale("log")
    ax.set_xlabel("prefix length $k$ (actions, log scale)")
    ax.set_ylabel("feature extraction + scoring (ms)")
    ax.legend(loc="upper left")
    save(fig, "fig7b")


def main():
    for f in (fig2, fig3, fig4, fig5, fig6, fig7):
        print(f.__name__)
        f()


if __name__ == "__main__":
    main()
