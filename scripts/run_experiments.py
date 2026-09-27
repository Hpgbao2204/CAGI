"""Run every experiment of the paper from one command and one commit.

    python scripts/run_experiments.py                  # all stages
    python scripts/run_experiments.py --stage rq1 rq2  # selected stages

Stages: dataset (build trajectories + prefix features), rq1 (detectors,
representation study, ablations, nested selection, seeds), spearman, seq
(GRU baseline), rq2 (checkpoints, online replay, lead time, false alerts),
rq2paired (paired tests per checkpoint/horizon), calib, explain (TreeSHAP),
stress (mimicry, per bridge family), builder (depth/share sensitivity), synth
(CAGI-Synth, synthetic only), gate (RQ3 data gate), runtime (RQ4).
Outputs go to results/tables/; intermediates to data/processed/exp/.
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import platform
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.evaluation.loio import (  # noqa: E402
    ap, bootstrap_metric, brier, dedupe_pooled_prefixes, ece, paired_bootstrap, per_incident, run_loio,
)
from src.features.extractor import extract_all_prefixes, extract_features  # noqa: E402
from src.models.baselines import (  # noqa: E402
    FLAT_FEATURES, MOTIF_FEATURES, TEMPORAL_FEATURES, TYPED_ACTION_FEATURES,
    B0MajorityBaseline, B1RuleBasedTypologyScore, B2BagOfActionsLogisticRegression,
    B3FlatGraphRandomForest, BRIDGE_CONTEXT_COLS_EXCLUDED, XGBFeatureSubsetModel,
)
from src.pipeline.dataset_builder import load_rq1_trajectories  # noqa: E402
from src.trajectories.builder import load_trajectory_config  # noqa: E402

PROC = REPO_ROOT / "data" / "processed"
EXP = PROC / "exp"
TAB = REPO_ROOT / "results" / "tables"
META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]
FULL_FEATURES = tuple(dict.fromkeys(FLAT_FEATURES + TYPED_ACTION_FEATURES + MOTIF_FEATURES))
TERMINAL_TYPES = {"bridge_deposit", "mixer_or_exit", "lending_deposit"}
THETAS = (0.3, 0.5, 0.7, 0.9)
HORIZONS_MIN = (1, 5, 15, 30, 60, 180, 720, 1440)
SEEDS = (0, 1, 2, 3, 4)


def log(*a):
    print(*a, flush=True)


def save(obj, name):
    EXP.mkdir(parents=True, exist_ok=True)
    with open(EXP / f"{name}.pkl", "wb") as f:
        pickle.dump(obj, f)


def load(name):
    with open(EXP / f"{name}.pkl", "rb") as f:
        return pickle.load(f)


def write_csv(df: pd.DataFrame, name: str):
    TAB.mkdir(parents=True, exist_ok=True)
    df.to_csv(TAB / name, index=False)
    log(f"  -> results/tables/{name} ({len(df)} dong)")


# ----------------------------------------------------------------------
# Model registry
# ----------------------------------------------------------------------
def m1(seed=42):
    return lambda: XGBFeatureSubsetModel(FULL_FEATURES, random_state=seed)


def subset(cols, seed=42):
    return lambda: XGBFeatureSubsetModel(tuple(cols), random_state=seed)


MAIN_MODELS = {
    "B0": B0MajorityBaseline,
    "B1": B1RuleBasedTypologyScore,
    "B2": B2BagOfActionsLogisticRegression,
    "B3": B3FlatGraphRandomForest,
    "B3p": subset(FLAT_FEATURES),
    "M1": m1(),
}
REPRESENTATIONS = {
    "Flat": FLAT_FEATURES,
    "Flat+Types": FLAT_FEATURES + TYPED_ACTION_FEATURES,
    "Flat+Motifs": FLAT_FEATURES + MOTIF_FEATURES,
    "Flat+Types+Motifs": FULL_FEATURES,
}
ABLATIONS = {
    "no_temporal": [c for c in FULL_FEATURES if c not in TEMPORAL_FEATURES],
    "no_motif": [c for c in FULL_FEATURES if c not in MOTIF_FEATURES],
    "no_typed_action": [c for c in FULL_FEATURES if c not in TYPED_ACTION_FEATURES],
    "no_bridge_context": [c for c in FULL_FEATURES if c not in BRIDGE_CONTEXT_COLS_EXCLUDED],
}


# ----------------------------------------------------------------------
# Stage: dataset
# ----------------------------------------------------------------------
TRAJ_EXPORT = PROC / "trajectories_v3.jsonl.gz"


def _export_trajectories(items):
    """Xuat trajectory da decode (dang gon) — cho phep tai lap moi thuc
    nghiem ma KHONG can data/raw (xem README)."""
    import gzip
    with gzip.open(TRAJ_EXPORT, "wt", encoding="utf-8") as f:
        for it in items:
            t = it.trajectory
            f.write(json.dumps({
                "source_id": it.source_id, "group_id": it.group_id, "label": it.label, "kind": it.kind,
                "chain": it.chain, "trajectory_id": t.trajectory_id, "seed_address": t.seed_address,
                "actions": [a.model_dump(mode="json") for a in t.actions],
            }) + "\n")


def _import_trajectories():
    import gzip
    from src.normalize.schema import CanonicalEvent
    from src.pipeline.dataset_builder import DatasetItem
    from src.trajectories.builder import Trajectory
    items = []
    with gzip.open(TRAJ_EXPORT, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            t = Trajectory(trajectory_id=d["trajectory_id"], seed_address=d["seed_address"],
                           actions=[CanonicalEvent(**a) for a in d["actions"]], label=d["label"])
            items.append(DatasetItem(trajectory=t, group_id=d["group_id"], label=d["label"], chain=d["chain"],
                                     kind=d["kind"], source_id=d["source_id"]))
    return items


def stage_dataset(from_export: bool = False):
    if from_export:
        log(f"=== dataset: doc trajectory tu {TRAJ_EXPORT.name} (khong can data/raw) ===")
        items = _import_trajectories()
    else:
        log("=== dataset: build trajectory tu data/raw (offline) ===")
        prov = {}
        items = load_rq1_trajectories(include_v2_complexity=True, verbose=False, require_complete_cache=True,
                                      provenance=prov)
        _export_trajectories(items)
        TAB.mkdir(parents=True, exist_ok=True)
        (TAB / "dataset_provenance.json").write_text(json.dumps(prov, indent=1, sort_keys=True))
    reg = pd.read_csv(REPO_ROOT / "metadata" / "incident_registry.csv").set_index("incident_id")
    trajs = []
    rows = []
    for it in items:
        t = it.trajectory
        e_idx = None
        if it.label == 1 and bool(reg.loc[it.source_id, "endpoint_confirmed"]):
            for i, a in enumerate(t.actions):
                if a.event_type in TERMINAL_TYPES:
                    e_idx = i + 1  # 1-indexed: prefix do dai e_idx CHUA endpoint
                    break
        trajs.append(dict(source_id=it.source_id, group_id=it.group_id, label=it.label, kind=it.kind,
                          chain=it.chain, trajectory=t, endpoint_idx=e_idx))
        for spec, feats in extract_all_prefixes(t, include_endpoint_context=False):
            feats = dict(feats)
            feats.pop("prefix_len", None)
            rows.append({"trajectory_id": t.trajectory_id, "source_id": it.source_id, "group_id": it.group_id,
                         "kind": it.kind, "chain": it.chain, "label": it.label, "prefix_label": spec.label,
                         "prefix_len": spec.length, "trajectory_len": len(t), **feats})
    df = pd.DataFrame(rows).fillna(0.0)
    df.to_parquet(PROC / "features_v3.parquet", index=False)
    save(trajs, "trajectories")
    pos = [t for t in trajs if t["label"] == 1]
    neg = [t for t in trajs if t["label"] == 0]
    stats = {
        "n_positive_trajectories": len(pos), "n_negative_trajectories": len(neg),
        "negatives_by_kind": pd.Series([t["kind"] for t in neg]).value_counts().to_dict(),
        "n_groups": int(df["group_id"].nunique()), "n_prefix_rows": len(df),
        "n_positive_rows": int(df["label"].sum()), "positive_rate_rows": float(df["label"].mean()),
        "n_pooled_rows_dedup": len(dedupe_pooled_prefixes(df)),
        "n_endpoint_confirmed": sum(1 for t in pos if t["endpoint_idx"] is not None),
        "chains": pd.Series([t["chain"] for t in trajs]).value_counts().to_dict(),
        "total_actions": int(sum(len(t["trajectory"]) for t in trajs)),
    }
    log(json.dumps(stats, indent=1))
    (TAB / "dataset_stats.json").write_text(json.dumps(stats, indent=1))

    # bang per-incident (Appendix + T17)
    inc_rows = []
    for g in sorted({t["group_id"] for t in trajs}):
        p = [t for t in pos if t["group_id"] == g][0]
        ng = [t for t in neg if t["group_id"] == g]
        acts = p["trajectory"].actions
        inc_rows.append({
            "incident_id": g, "chain": p["chain"], "n_actions": len(acts),
            "duration_h": (acts[-1].timestamp - acts[0].timestamp).total_seconds() / 3600 if acts else 0,
            "n_bridge_deposit": sum(a.event_type == "bridge_deposit" for a in acts),
            "n_swap": sum(a.event_type == "swap" for a in acts),
            "n_mixer_or_exit": sum(a.event_type == "mixer_or_exit" for a in acts),
            "endpoint_idx": p["endpoint_idx"],
            "endpoint_type": acts[p["endpoint_idx"] - 1].event_type if p["endpoint_idx"] else "",
            "n_negatives": len(ng),
            "n_neg_mined": sum(t["kind"] == "hard_negative_mined" for t in ng),
            "n_neg_complex": sum(t["kind"] == "hard_negative_mined_v2_complexity" for t in ng),
            "n_neg_control": sum(t["kind"] == "hard_negative_control" for t in ng),
            "neg_len_median": float(np.median([len(t["trajectory"]) for t in ng])) if ng else 0,
        })
    write_csv(pd.DataFrame(inc_rows), "incident_table.csv")


def load_pool():
    df = pd.read_parquet(PROC / "features_v3.parquet")
    pool = dedupe_pooled_prefixes(df)
    feat_cols = [c for c in pool.columns if c not in META_COLS]
    return df, pool, feat_cols


# ----------------------------------------------------------------------
# Stage: rq1
# ----------------------------------------------------------------------
def _eval_model(name, factory, X, y, g, calibrate=False):
    t = time.time()
    res = run_loio(factory, X, y, g, calibrate=calibrate)
    log(f"  {name:22s} pooled PR-AUC={ap(y, res.oof_raw):.4f}  ({time.time() - t:.0f}s)")
    return res


def stage_rq1():
    log("=== rq1 ===")
    df, pool, feat_cols = load_pool()
    X, y, g = pool[feat_cols], pool["label"], pool["group_id"]
    log(f"pooled rows={len(pool)} pos={int(y.sum())} ({y.mean():.4f}) groups={g.nunique()}")

    oof = {}
    results = {}
    for name, fac in MAIN_MODELS.items():
        res = _eval_model(name, fac, X, y, g, calibrate=(name == "M1"))
        results[name] = res
        oof[name] = res.oof_raw
    save(results["M1"], "loio_M1")
    for name, cols in REPRESENTATIONS.items():
        oof[f"rep:{name}"] = _eval_model(f"rep:{name}", subset(cols), X, y, g).oof_raw
    for name, cols in ABLATIONS.items():
        oof[f"abl:{name}"] = _eval_model(f"abl:{name}", subset(cols), X, y, g).oof_raw

    # T14: nested LOIO chon co/khong bridge-context TRONG moi fold train
    nested = pd.Series(np.nan, index=X.index)
    choices = {}
    cand = {"with_bridge": FULL_FEATURES, "no_bridge": tuple(ABLATIONS["no_bridge_context"])}
    for h in pd.unique(g):
        te = g == h
        tr = ~te
        inner_scores = {}
        for cname, cols in cand.items():
            r = run_loio(subset(cols), X[tr], y[tr], g[tr])
            inner_scores[cname] = ap(y[tr], r.oof_raw)
        best = max(inner_scores, key=inner_scores.get)
        choices[str(h)] = {"choice": best, **{f"inner_{k}": v for k, v in inner_scores.items()}}
        nested[te] = subset(cand[best])().fit(X[tr], y[tr], g[tr]).predict_proba(X[te])
    oof["nested_select"] = nested
    log(f"  nested_select          pooled PR-AUC={ap(y, nested):.4f}  choices="
        f"{pd.Series([c['choice'] for c in choices.values()]).value_counts().to_dict()}")

    # T13: seed
    seed_rows = []
    for s in SEEDS:
        for name, fac in {"M1": m1(s), "B3p": subset(FLAT_FEATURES, s),
                          "B3": lambda s=s: B3FlatGraphRandomForest(random_state=s)}.items():
            r = run_loio(fac, X, y, g)
            seed_rows.append({"seed": s, "model": name, "pooled_pr_auc": ap(y, r.oof_raw),
                              "mean_incident_pr_auc": float(np.nanmean(list(per_incident(y, r.oof_raw, g).values())))})
    seed_df = pd.DataFrame(seed_rows)
    write_csv(seed_df, "seed_robustness.csv")
    log(seed_df.groupby("model")["pooled_pr_auc"].agg(["mean", "std"]).to_string())

    # --- bang chinh ---
    main_rows = []
    for name, p in oof.items():
        ci = bootstrap_metric(y, p, g)
        pi = per_incident(y, p, g)
        main_rows.append({"model": name, "pooled_pr_auc": ci["point"], "ci_low": ci["ci_low"], "ci_high": ci["ci_high"],
                          "mean_incident_pr_auc": float(np.nanmean(list(pi.values())))})
    main = pd.DataFrame(main_rows)
    write_csv(main, "rq1_main.csv")
    log(main.to_string())

    pairs = [("M1", "B3"), ("M1", "B3p"), ("M1", "B1"), ("M1", "B2"),
             ("rep:Flat+Types", "rep:Flat"), ("rep:Flat+Motifs", "rep:Flat"),
             ("rep:Flat+Types+Motifs", "rep:Flat"), ("nested_select", "M1")]
    pairs += [(f"abl:{a}", "M1") for a in ABLATIONS]
    pr = []
    for a, b in pairs:
        r = paired_bootstrap(y, oof[a], oof[b], g)
        pr.append({"a": a, "b": b, **r})
    pr = pd.DataFrame(pr)
    write_csv(pr, "rq1_paired.csv")
    log(pr.to_string())

    # per-incident
    per = pd.DataFrame({name: per_incident(y, p, g) for name, p in oof.items()})
    per.index.name = "incident_id"
    per = per.reset_index()
    tl = pool[pool.label == 1].groupby("group_id")["trajectory_len"].first()
    per["trajectory_len"] = per["incident_id"].map(tl)
    write_csv(per, "rq1_per_incident.csv")

    stage_spearman()

    nested_df = pd.DataFrame(choices).T.reset_index().rename(columns={"index": "held_out"})
    write_csv(nested_df, "nested_selection_choices.csv")

    oof_df = pool[META_COLS].copy()
    for name, p in oof.items():
        oof_df[f"oof_{name}"] = p.to_numpy()
    for mth, s in results["M1"].oof_cal.items():
        oof_df[f"oof_M1_{mth}"] = s.to_numpy()
    oof_df.to_csv(PROC / "oof_predictions_v3.csv", index=False)


def stage_seq():
    """S1: GRU tren token hanh dong co kieu (Todo T19), cung LOIO voi M1."""
    log("=== seq (GRU) ===")
    from src.models.sequence import GRUSequenceModel, tokenize_prefix
    df, pool, feat_cols = load_pool()
    trajs = {t["source_id"]: t["trajectory"] for t in load("trajectories")}
    lookup = {i: tokenize_prefix(trajs[sid].actions[:k])
              for i, sid, k in zip(pool.index, pool.source_id, pool.prefix_len)}
    X, y, g = pool[feat_cols], pool["label"], pool["group_id"]
    t = time.time()
    res = run_loio(lambda: GRUSequenceModel(lookup), X, y, g)
    log(f"  S1 GRU pooled PR-AUC={ap(y, res.oof_raw):.4f} ({time.time() - t:.0f}s)")
    oof = pd.read_csv(PROC / "oof_predictions_v3.csv")
    oof["oof_S1"] = res.oof_raw.to_numpy()
    oof.to_csv(PROC / "oof_predictions_v3.csv", index=False)
    ci = bootstrap_metric(y, res.oof_raw, g)
    rows = [{"model": "S1", "pooled_pr_auc": ci["point"], "ci_low": ci["ci_low"], "ci_high": ci["ci_high"],
             "mean_incident_pr_auc": float(np.nanmean(list(per_incident(y, res.oof_raw, g).values())))}]
    write_csv(pd.DataFrame(rows), "rq1_sequence.csv")
    pr = paired_bootstrap(y, oof["oof_M1"], res.oof_raw, g)
    write_csv(pd.DataFrame([{"a": "M1", "b": "S1", **pr}]), "rq1_sequence_paired.csv")
    log(pr)


def stage_spearman():
    """T7: Spearman giua do dai trajectory va chenh lech per-incident PR-AUC.
    Incident khong co negative (PR-AUC khong xac dinh) bi bo qua."""
    from scipy.stats import spearmanr
    per = pd.read_csv(TAB / "rq1_per_incident.csv")
    sp = []
    for base in ("B3", "B3p"):
        d = per[["trajectory_len", "M1", base]].dropna()
        rho, pv = spearmanr(d["trajectory_len"], d["M1"] - d[base])
        sp.append({"gap": f"M1-{base}", "n": len(d), "rho": rho, "p": pv,
                   "excluded_no_negatives": ";".join(per.loc[per[base].isna() | per["M1"].isna(), "incident_id"])})
    sp = pd.DataFrame(sp)
    write_csv(sp, "rq1_spearman.csv")
    log(sp.to_string())


# ----------------------------------------------------------------------
# Stage: rq2
# ----------------------------------------------------------------------
def _features_for_prefixes(traj, ks, feat_cols):
    rows = [extract_features(traj, k, include_endpoint_context=False) for k in ks]
    return pd.DataFrame(rows).reindex(columns=feat_cols, fill_value=0.0).fillna(0.0)


def _k_at_horizon(traj, minutes):
    t0 = traj.actions[0].timestamp
    lim = t0 + timedelta(minutes=minutes)
    return sum(1 for a in traj.actions if a.timestamp <= lim)


def _horizon_tables(online):
    """Moc thoi gian online (T15): prefix k(t1+h). So M1 va B3' tren diem RAW
    (cung learner, chi khac bieu dien) + paired bootstrap tung moc."""
    rows, pair = [], []
    for h in HORIZONS_MIN:
        y, g, pm, pb, ks, kn = [], [], [], [], [], []
        for o in online:
            k = int(np.clip(np.sum(o["ts"] <= o["ts"][0] + 60 * h), 2, o["n"]))
            y.append(o["label"]); g.append(o["group_id"])
            pm.append(o["raw"][k - 2]); pb.append(o["raw_b3p"][k - 2])
            (ks if o["label"] == 1 else kn).append(k)
        y, g, pm, pb = map(np.asarray, (y, g, pm, pb))
        bm, bb = bootstrap_metric(y, pm, g), bootstrap_metric(y, pb, g)
        rows.append({"horizon_min": h, "n": len(y), "pos_rate": y.mean(), "median_k_pos": float(np.median(ks)),
                     "median_k_neg": float(np.median(kn)), "M1_pr_auc": bm["point"], "M1_ci_low": bm["ci_low"],
                     "M1_ci_high": bm["ci_high"], "B3p_pr_auc": bb["point"], "B3p_ci_low": bb["ci_low"],
                     "B3p_ci_high": bb["ci_high"]})
        pair.append({"horizon_min": h, **paired_bootstrap(y, pm, pb, g)})
    out = pd.DataFrame(rows)
    write_csv(out, "rq2_time_horizons.csv")
    write_csv(pd.DataFrame(pair), "rq2_time_horizons_paired.csv")
    log(out[["horizon_min", "median_k_pos", "M1_pr_auc", "B3p_pr_auc"]].to_string())
    log(pd.DataFrame(pair)[["horizon_min", "point", "ci_low", "ci_high", "p_value"]].to_string())


def stage_rq2paired():
    """Paired bootstrap M1 vs B3' theo tung checkpoint + tung moc thoi gian."""
    log("=== rq2paired ===")
    df, pool, feat_cols = load_pool()
    oof = pd.read_csv(PROC / "oof_predictions_v3.csv").set_index(["source_id", "prefix_len"])
    ck = df[META_COLS].copy()
    for col in ("oof_M1", "oof_B3p"):
        ck[col] = oof.loc[list(zip(ck.source_id, ck.prefix_len)), col].to_numpy()
    pr = []
    for lab in ["k_2", "k_3", "k_5", "k_7", "ratio_25", "ratio_50", "ratio_75", "ratio_100"]:
        s_ = ck[ck.prefix_label == lab]
        pr.append({"checkpoint": lab, **paired_bootstrap(s_.label, s_.oof_M1, s_.oof_B3p, s_.group_id)})
    pr = pd.DataFrame(pr)
    write_csv(pr, "rq2_checkpoints_paired.csv")
    log(pr[["checkpoint", "point", "ci_low", "ci_high", "p_value"]].to_string())
    _horizon_tables(load("online_scores"))


def stage_rq2():
    log("=== rq2 ===")
    df, pool, feat_cols = load_pool()
    res = load("loio_M1")
    trajs = load("trajectories")
    oof = pd.read_csv(PROC / "oof_predictions_v3.csv")

    # (a) moc checkpoint: dong goc (chua dedupe) lay diem OOF theo (source_id, prefix_len)
    key = oof.set_index(["source_id", "prefix_len"])
    ck = df[META_COLS].copy()
    for col in ("oof_M1", "oof_B3p", "oof_B3", "oof_B1", "oof_M1_platt"):
        ck[col] = key.loc[list(zip(ck.source_id, ck.prefix_len)), col].to_numpy()
    rows = []
    for lab in ["k_2", "k_3", "k_5", "k_7", "ratio_25", "ratio_50", "ratio_75", "ratio_100"]:
        s = ck[ck.prefix_label == lab]
        r = {"checkpoint": lab, "n_rows": len(s), "n_pos": int(s.label.sum()), "pos_rate": s.label.mean()}
        for m in ("M1", "B3p", "B3", "B1"):
            b = bootstrap_metric(s.label, s[f"oof_{m}"], s.group_id)
            r[f"{m}_pr_auc"], r[f"{m}_ci_low"], r[f"{m}_ci_high"] = b["point"], b["ci_low"], b["ci_high"]
            r[f"{m}_mean_incident"] = float(np.nanmean(list(per_incident(s.label, s[f"oof_{m}"], s.group_id).values())))
        rows.append(r)
    cp = pd.DataFrame(rows)
    write_csv(cp, "rq2_checkpoints.csv")
    log(cp[["checkpoint", "n_rows", "pos_rate", "M1_pr_auc", "M1_ci_low", "M1_ci_high", "B3p_pr_auc", "M1_mean_incident"]].to_string())

    # (b) moc thoi gian (T15) + (c) online moi prefix -> first alert
    b3p = run_loio(subset(FLAT_FEATURES), pool[feat_cols], pool["label"], pool["group_id"])
    online = []
    t_start = time.time()
    for t in trajs:
        fold = res.folds[t["group_id"]]
        tr = t["trajectory"]
        n = len(tr)
        if n < 2:
            continue
        ks = list(range(2, n + 1))
        Xk = _features_for_prefixes(tr, ks, feat_cols)
        raw = fold.model.predict_proba(Xk)
        cal = fold.calibrators["platt"](raw)
        rawb = b3p.folds[t["group_id"]].model.predict_proba(Xk)
        online.append({"source_id": t["source_id"], "group_id": t["group_id"], "label": t["label"],
                       "kind": t["kind"], "chain": t["chain"], "n": n, "endpoint_idx": t["endpoint_idx"],
                       "ks": np.array(ks), "raw": raw, "cal": cal, "raw_b3p": rawb,
                       "ts": np.array([a.timestamp.timestamp() for a in tr.actions])})
    log(f"  online scoring {len(online)} trajectory trong {time.time() - t_start:.0f}s")
    save(online, "online_scores")

    _horizon_tables(online)

    # (d) first alert, lead time, false alert (T2) — tren diem Platt, MOI prefix k>=2
    pos = [o for o in online if o["label"] == 1]
    neg = [o for o in online if o["label"] == 0]
    lt_rows, per_inc = [], []
    grid = np.round(np.arange(0.05, 1.0, 0.05), 2)
    for th in sorted(set(THETAS) | set(grid)):
        n_fa = sum(bool((o["cal"] >= th).any()) for o in neg)
        leads, late, never, before = [], 0, 0, 0
        n_alerted_any = 0
        for o in pos:
            hit = np.where(o["cal"] >= th)[0]
            if len(hit):
                n_alerted_any += 1
            if o["endpoint_idx"] is None:
                continue
            if not len(hit):
                never += 1
                continue
            ka = int(o["ks"][hit[0]])
            e = o["endpoint_idx"]
            if ka < e:
                before += 1
                leads.append(o["ts"][e - 1] - o["ts"][ka - 1])
            else:
                late += 1
            if th in THETAS:
                per_inc.append({"theta": th, "incident": o["source_id"], "k_alert": ka, "endpoint_idx": e,
                                "lead_steps": e - ka, "lead_sec": o["ts"][e - 1] - o["ts"][ka - 1],
                                "before_endpoint": ka < e})
        n_e = sum(1 for o in pos if o["endpoint_idx"] is not None)
        lt_rows.append({"theta": th, "n_endpoint": n_e, "detected_before": before, "late": late, "never": never,
                        "median_lead_sec": float(np.median(leads)) if leads else np.nan,
                        "q1_lead_sec": float(np.percentile(leads, 25)) if leads else np.nan,
                        "q3_lead_sec": float(np.percentile(leads, 75)) if leads else np.nan,
                        "pos_alerted_any": n_alerted_any, "n_pos": len(pos),
                        "false_alert_traj": n_fa, "n_neg": len(neg), "false_alert_rate": n_fa / len(neg)})
    lt = pd.DataFrame(lt_rows)
    write_csv(lt, "rq2_alerting.csv")
    log(lt[lt.theta.isin(THETAS)].to_string())
    write_csv(pd.DataFrame(per_inc), "rq2_alerting_per_incident.csv")


# ----------------------------------------------------------------------
# Stage: calib
# ----------------------------------------------------------------------
def stage_calib():
    log("=== calib ===")
    oof = pd.read_csv(PROC / "oof_predictions_v3.csv")
    y, g = oof.label.to_numpy(), oof.group_id.to_numpy()
    rows, rel = [], []
    for name, col in (("raw", "oof_M1"), ("isotonic", "oof_M1_isotonic"), ("platt", "oof_M1_platt")):
        p = oof[col].to_numpy()
        bb = bootstrap_metric(y, p, g, metric=brier)
        be = bootstrap_metric(y, p, g, metric=ece)
        rows.append({"method": name, "n": len(p), "brier": bb["point"], "brier_ci_low": bb["ci_low"],
                     "brier_ci_high": bb["ci_high"], "ece": be["point"], "ece_ci_low": be["ci_low"],
                     "ece_ci_high": be["ci_high"], "pr_auc": ap(y, p)})
        bins = np.linspace(0, 1, 11)
        idx = np.clip(np.digitize(p, bins[1:-1]), 0, 9)
        for b in range(10):
            m = idx == b
            if m.any():
                rel.append({"method": name, "bin": b, "n": int(m.sum()), "mean_pred": p[m].mean(), "frac_pos": y[m].mean()})
    c = pd.DataFrame(rows)
    write_csv(c, "calibration.csv")
    write_csv(pd.DataFrame(rel), "calibration_reliability.csv")
    log(c.to_string())


# ----------------------------------------------------------------------
# Stage: explain (TreeSHAP)
# ----------------------------------------------------------------------
def _shap(model, X):
    import xgboost as xgb
    cols = model.feature_cols_
    contrib = model.model.get_booster().predict(xgb.DMatrix(X[cols].astype(float)), pred_contribs=True)
    return pd.DataFrame(contrib[:, :-1], columns=cols), contrib[:, -1]


def stage_explain():
    log("=== explain ===")
    from src.models.baselines import XGBFeatureSubsetModel as _M
    df, pool, feat_cols = load_pool()
    X, y, g = pool[feat_cols], pool["label"], pool["group_id"]
    final = _M(FULL_FEATURES).fit(X, y, g)
    sv, _ = _shap(final, X)
    imp = sv.abs().mean().sort_values(ascending=False).reset_index()
    imp.columns = ["feature", "mean_abs_shap"]
    group_of = {}
    for c in FLAT_FEATURES:
        group_of[c] = "flat"
    for c in TYPED_ACTION_FEATURES:
        group_of[c] = "typed_action"
    for c in MOTIF_FEATURES:
        group_of[c] = "motif"
    imp["group"] = imp.feature.map(group_of)
    write_csv(imp, "shap_global.csv")
    log(imp.head(12).to_string())

    # case study: incident co lead time lon nhat o theta=0.5 (+ Chibi neu co)
    res = load("loio_M1")
    online = {o["source_id"]: o for o in load("online_scores")}
    trajs = {t["source_id"]: t for t in load("trajectories")}
    per = pd.read_csv(TAB / "rq2_alerting_per_incident.csv")
    rows = []
    for inc in sorted(set(per.incident)):
        r = per[(per.incident == inc) & (per.theta == 0.5)]
        if r.empty:
            continue
        ka = int(r.k_alert.iloc[0])
        fold = res.folds[trajs[inc]["group_id"]]
        Xk = _features_for_prefixes(trajs[inc]["trajectory"], [ka], feat_cols)
        s, base = _shap(fold.model, Xk)
        top = s.iloc[0].sort_values(key=np.abs, ascending=False).head(5)
        rows.append({"incident": inc, "k_alert": ka, "score_raw": float(online[inc]["raw"][ka - 2]),
                     "score_platt": float(online[inc]["cal"][ka - 2]),
                     **{f"top{i + 1}": f"{f}={Xk.iloc[0][f]:.3g} ({v:+.2f})" for i, (f, v) in enumerate(top.items())}})
    cs = pd.DataFrame(rows)
    write_csv(cs, "case_study_shap.csv")
    log(cs.to_string())


# ----------------------------------------------------------------------
# Stage: stress (mimicry) + per bridge family
# ----------------------------------------------------------------------
def _inject_noise(traj, j, rng):
    """Chen j transfer nho (1% gia tri) toi dia chi moi ngay sau MOI action
    cua trajectory (cung token, +1s) — mo phong ke tan cong xen hanh vi binh
    thuong de pha motif/ty le loai hanh dong."""
    from src.trajectories.builder import Trajectory
    acts = []
    for i, a in enumerate(traj.actions):
        acts.append(a)
        for r in range(j):
            fake = a.model_copy(update={
                "timestamp": a.timestamp + timedelta(seconds=r + 1),
                "tx_hash": "0x" + format(rng.getrandbits(256), "064x"),
                "log_index": 0, "src": a.dst, "dst": "0x" + format(rng.getrandbits(160), "040x"),
                "event_type": "transfer", "amount_norm": math.log1p(0.01 * math.expm1(abs(a.amount_norm))),
                "protocol": None,
            })
            acts.append(fake)
    return Trajectory(trajectory_id=traj.trajectory_id, seed_address=traj.seed_address, actions=acts)


def stage_stress():
    log("=== stress ===")
    import random
    df, pool, feat_cols = load_pool()
    res = load("loio_M1")
    trajs = load("trajectories")
    online = {o["source_id"]: o for o in load("online_scores")}
    rows = []
    rng = random.Random(7)
    for j in (0, 1, 2, 4):
        for t in [t for t in trajs if t["label"] == 1]:
            fold = res.folds[t["group_id"]]
            tr = _inject_noise(t["trajectory"], j, rng) if j else t["trajectory"]
            n = len(tr)
            n0 = len(t["trajectory"])
            # checkpoint 25% cua trajectory GOC -> vi tri tuong ung sau khi chen
            k25 = max(2, int(math.ceil(0.25 * n0)) * (j + 1))
            ks = list(range(2, min(n, 400) + 1))
            sc = fold.calibrators["platt"](fold.model.predict_proba(_features_for_prefixes(tr, ks, feat_cols)))
            s25 = fold.calibrators["platt"](fold.model.predict_proba(_features_for_prefixes(tr, [min(k25, n)], feat_cols)))[0]
            rows.append({"j": j, "incident": t["source_id"], "max_score_first400": float(sc.max()),
                         "score_at_25pct": float(s25), "alert_0.5": bool((sc >= 0.5).any())})
    st = pd.DataFrame(rows)
    write_csv(st, "stress_mimicry_per_incident.csv")
    summ = st.groupby("j").agg(detect_rate_0_5=("alert_0.5", "mean"), mean_score_25=("score_at_25pct", "mean"),
                               median_score_25=("score_at_25pct", "median")).reset_index()
    write_csv(summ, "stress_mimicry.csv")
    log(summ.to_string())

    # per bridge family
    reg = pd.read_csv(REPO_ROOT / "metadata" / "incident_registry.csv").set_index("incident_id")
    per = pd.read_csv(TAB / "rq1_per_incident.csv").set_index("incident_id")
    al = pd.read_csv(TAB / "rq2_alerting_per_incident.csv")
    fam = []
    for inc in per.index:
        acts = [t for t in trajs if t["source_id"] == inc][0]["trajectory"].actions
        protos = sorted({a.protocol for a in acts if a.event_type in ("bridge_deposit", "bridge_withdraw") and a.protocol})
        mix = any(a.event_type == "mixer_or_exit" for a in acts)
        a5 = al[(al.incident == inc) & (al.theta == 0.5)]
        fam.append({"incident": inc, "chain": reg.loc[inc, "chain_primary"],
                    "bridge_families_observed": ";".join(protos) if protos else "none",
                    "mixer_observed": mix, "M1_pr_auc": per.loc[inc, "M1"], "B3p_pr_auc": per.loc[inc, "B3p"],
                    "before_endpoint_0.5": bool(a5.before_endpoint.iloc[0]) if len(a5) else None})
    write_csv(pd.DataFrame(fam), "per_bridge_family.csv")


# ----------------------------------------------------------------------
# Stage: builder sensitivity (T18) — rebuild tu cache voi cau hinh khac
# ----------------------------------------------------------------------
def stage_builder():
    log("=== builder ===")
    from dataclasses import replace
    base = load_trajectory_config()
    rows = []
    for depth in (1, 2):
        for share in (0.05, 0.10, 0.20):
            cfg = replace(base, min_tainted_share=share)
            items = load_rq1_trajectories(config=cfg, include_v2_complexity=True, require_complete_cache=True,
                                          max_iterations_positive=depth, max_iterations_negative=depth)
            rr = []
            for it in items:
                for spec, feats in extract_all_prefixes(it.trajectory):
                    feats = dict(feats)
                    feats.pop("prefix_len", None)
                    rr.append({"source_id": it.source_id, "group_id": it.group_id, "label": it.label,
                               "prefix_label": spec.label, "prefix_len": spec.length, **feats})
            d = dedupe_pooled_prefixes(pd.DataFrame(rr).fillna(0.0))
            fc = [c for c in d.columns if c not in ("source_id", "group_id", "label", "prefix_label", "prefix_len")]
            r = run_loio(m1(), d[fc], d.label, d.group_id)
            rb = run_loio(subset(FLAT_FEATURES), d[fc], d.label, d.group_id)
            pos_len = [len(it.trajectory) for it in items if it.label == 1]
            b = bootstrap_metric(d.label, r.oof_raw, d.group_id)
            rows.append({"expand_iterations": depth, "min_share": share, "n_rows": len(d),
                         "median_pos_len": float(np.median(pos_len)), "M1_pr_auc": b["point"],
                         "M1_ci_low": b["ci_low"], "M1_ci_high": b["ci_high"], "B3p_pr_auc": ap(d.label, rb.oof_raw)})
            log(rows[-1])
    write_csv(pd.DataFrame(rows), "builder_sensitivity.csv")


# ----------------------------------------------------------------------
# Stage: synth — benchmark TONG HOP (bao cao tach rieng khoi du lieu that)
# ----------------------------------------------------------------------
SYNTH_DIFFICULTY = (0.0, 0.25, 0.5, 0.75, 1.0)


def _prefix_frame(items):
    rows = []
    for it in items:
        for spec, feats in extract_all_prefixes(it.trajectory, include_endpoint_context=False):
            feats = dict(feats)
            feats.pop("prefix_len", None)
            rows.append({"trajectory_id": it.trajectory.trajectory_id, "source_id": it.source_id,
                         "group_id": it.group_id, "kind": it.kind, "chain": it.chain, "label": it.label,
                         "prefix_label": spec.label, "prefix_len": spec.length,
                         "trajectory_len": len(it.trajectory), **feats})
    return pd.DataFrame(rows).fillna(0.0)


def stage_synth():
    log("=== synth (CAGI-Synth, du lieu TONG HOP) ===")
    from src.synth.generator import generate
    df_real, pool_real, feat_cols = load_pool()
    real_model = XGBFeatureSubsetModel(FULL_FEATURES).fit(pool_real[feat_cols], pool_real["label"], pool_real["group_id"])
    rows = []
    for d in SYNTH_DIFFICULTY:
        items = generate(n_incidents=30, negatives_per_incident=40, difficulty=d, seed=2026)
        pool = dedupe_pooled_prefixes(_prefix_frame(items))
        X = pool.reindex(columns=feat_cols, fill_value=0.0)
        y, g = pool["label"], pool["group_id"]
        r = {"difficulty": d, "n_traj": len(items), "n_rows": len(pool), "pos_rate": float(y.mean())}
        for name, fac in (("M1", m1()), ("B3p", subset(FLAT_FEATURES)), ("B3", B3FlatGraphRandomForest),
                          ("B1", B1RuleBasedTypologyScore)):
            res = run_loio(fac, X, y, g)
            b = bootstrap_metric(y, res.oof_raw, g)
            r[f"{name}_pr_auc"], r[f"{name}_ci_low"], r[f"{name}_ci_high"] = b["point"], b["ci_low"], b["ci_high"]
        tr = real_model.predict_proba(X)
        b = bootstrap_metric(y, tr, g)
        r["M1_real_to_synth_pr_auc"], r["M1_real_to_synth_ci_low"], r["M1_real_to_synth_ci_high"] = b["point"], b["ci_low"], b["ci_high"]
        rows.append(r)
        log({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    write_csv(pd.DataFrame(rows), "synth_benchmark.csv")


# ----------------------------------------------------------------------
# Stage: gate (RQ3) + runtime (RQ4)
# ----------------------------------------------------------------------
def stage_gate():
    log("=== gate ===")
    trajs = load("trajectories")
    nxt = []
    for t in trajs:
        acts = t["trajectory"].actions
        nxt += [acts[i + 1].event_type for i in range(len(acts) - 1)]
    vc = pd.Series(nxt).value_counts()
    out = pd.DataFrame({"next_action_class": vc.index, "n": vc.values, "ratio": vc.values / vc.sum()})
    write_csv(out, "rq3_gate.csv")
    classes = ["transfer", "swap", "bridge_deposit", "bridge_withdraw", "lending", "split", "merge", "mixer_or_exit"]
    gate = {"n_transitions": int(vc.sum()), "c1_ge_1000": bool(vc.sum() >= 1000),
            "min_class_count": int(vc.min()), "c2_all_classes_ge_30": bool(vc.min() >= 30),
            "majority_ratio": float(vc.max() / vc.sum()), "c3_majority_lt_60": bool(vc.max() / vc.sum() < 0.6)}
    (TAB / "rq3_gate.json").write_text(json.dumps(gate, indent=1))
    log(gate)


def stage_runtime():
    log("=== runtime ===")
    import psutil
    df, pool, feat_cols = load_pool()
    trajs = load("trajectories")
    model = XGBFeatureSubsetModel(FULL_FEATURES).fit(pool[feat_cols], pool["label"], pool["group_id"])
    longest = max(trajs, key=lambda t: len(t["trajectory"]))["trajectory"]
    rows = []
    for n in (2, 5, 10, 25, 50, 100, 250, 500, 1000, len(longest)):
        if n > len(longest):
            continue
        times = []
        tracemalloc.start()
        for _ in range(15):
            t0 = time.perf_counter()
            X = _features_for_prefixes(longest, [n], feat_cols)
            model.predict_proba(X)
            times.append((time.perf_counter() - t0) * 1000)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows.append({"n_events": n, "median_ms": float(np.median(times)), "p95_ms": float(np.percentile(times, 95)),
                     "peak_mem_mb": peak / 1e6})
    rt = pd.DataFrame(rows)
    write_csv(rt, "runtime.csv")
    log(rt.to_string())
    hw = {"cpu": platform.processor() or platform.machine(), "n_cpu_logical": psutil.cpu_count(),
          "ram_gb": round(psutil.virtual_memory().total / 1e9, 1), "os": platform.platform(),
          "python": platform.python_version()}
    import sklearn, xgboost
    hw.update({"sklearn": sklearn.__version__, "xgboost": xgboost.__version__, "pandas": pd.__version__,
               "numpy": np.__version__})
    try:
        hw["cpu_model"] = [l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0]
    except Exception:
        pass
    (TAB / "runtime_hardware.json").write_text(json.dumps(hw, indent=1))


STAGES = {"dataset": stage_dataset, "rq1": stage_rq1, "spearman": stage_spearman, "seq": stage_seq, "rq2paired": stage_rq2paired, "rq2": stage_rq2, "calib": stage_calib,
          "explain": stage_explain, "stress": stage_stress, "builder": stage_builder,
          "synth": stage_synth, "gate": stage_gate, "runtime": stage_runtime}


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--stage", nargs="+", default=list(STAGES))
    ap_.add_argument("--from-export", action="store_true",
                     help="stage dataset doc data/processed/trajectories_v3.jsonl.gz thay vi data/raw")
    args = ap_.parse_args()
    TAB.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "src", "configs", "metadata"],
                                             cwd=REPO_ROOT, text=True).strip())
    except Exception:
        commit, dirty = "unknown", None
    for s in args.stage:
        t = time.time()
        if s == "dataset":
            stage_dataset(from_export=args.from_export)
        else:
            STAGES[s]()
        log(f"--- stage {s} xong trong {time.time() - t:.0f}s")
    manifest_path = TAB / "run_manifest.json"
    man = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    man.update({s: {"commit": commit, "src_dirty": dirty, "finished_utc": datetime.now(timezone.utc).isoformat()}
                for s in args.stage})
    manifest_path.write_text(json.dumps(man, indent=1))


if __name__ == "__main__":
    main()
