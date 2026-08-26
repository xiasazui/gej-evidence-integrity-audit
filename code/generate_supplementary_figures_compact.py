#!/usr/bin/env python3
"""Build five non-redundant composite supplementary figures from frozen data."""

from __future__ import annotations

import csv
import json
import argparse
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


RELEASE = Path(__file__).resolve().parents[1]
OUT = RELEASE / "reproduced_figures/supplementary"

COLORS = {
    "blue": "#2B6CB0",
    "cyan": "#2A9D8F",
    "orange": "#E76F51",
    "gold": "#E9C46A",
    "purple": "#756BB1",
    "grey": "#7A7A7A",
    "light": "#EAF2F8",
    "dark": "#253746",
}

MODEL_LABELS = {
    "MiniMax-M2.1": "MiniMax",
    "deepseek-v3.2-thinking": "DeepSeek",
    "deterministic-baseline": "Deterministic",
    "gemini-3-pro-preview-thinking": "Gemini",
    "gpt-5.2": "GPT-5.2",
    "gpt-oss-120b": "GPT-OSS-120B",
    "gpt-oss-20b": "GPT-OSS-20B",
    "kimi-k2-thinking": "Kimi",
    "qwen3-235b-a22b-thinking-2507": "Qwen3-235B",
    "qwen3-30b-a3b-thinking-2507": "Qwen3-30B",
    "qwen3-next-80b-a3b-thinking": "Qwen3-Next",
}

mpl.rcParams.update(
    {
        "font.family": "Arial",
        "font.size": 8.5,
        "axes.titlesize": 10,
        "axes.labelsize": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.fontsize": 7.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.06,
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def panel(ax, letter: str, title: str) -> None:
    ax.text(-0.10, 1.08, letter, transform=ax.transAxes, fontsize=12, fontweight="bold", va="top")
    ax.set_title(title, loc="left", fontweight="bold", pad=8)


def heatmap(ax, values: np.ndarray, row_labels: list[str], col_labels: list[str], title: str,
            vmin: float = 0.0, vmax: float = 1.0, cmap: str = "Blues", annotate: bool = False) -> None:
    mesh = ax.pcolormesh(np.arange(values.shape[1] + 1), np.arange(values.shape[0] + 1), values,
                         cmap=cmap, vmin=vmin, vmax=vmax, shading="flat")
    ax.set_xticks(np.arange(len(col_labels)) + 0.5, col_labels)
    ax.set_yticks(np.arange(len(row_labels)) + 0.5, row_labels)
    ax.invert_yaxis()
    ax.tick_params(length=0)
    ax.set_title(title, loc="left", fontweight="bold", pad=8)
    if annotate:
        midpoint = (vmin + vmax) / 2
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                val = values[i, j]
                ax.text(j + 0.5, i + 0.5, f"{val:.2f}", ha="center", va="center",
                        fontsize=6.5, color="white" if val > midpoint else COLORS["dark"])
    cb = plt.colorbar(mesh, ax=ax, fraction=0.026, pad=0.02)
    cb.ax.tick_params(labelsize=7)


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(OUT / f"{stem}.png", dpi=300)
    fig.savefig(OUT / f"{stem}.pdf")
    fig.savefig(OUT / f"{stem}.svg")
    fig.savefig(OUT / f"{stem}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def figure_s1() -> None:
    data = json.loads((RELEASE / "data/aggregate/gold_dataset_summary.json").read_text())
    dist = data["case_level_summary"]["fail_rules_per_case_distribution"]
    labels = data["labels_distribution"]

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25), gridspec_kw={"width_ratios": [0.9, 1.45]})
    ax = axes[0]
    xs = [0, 1, 2, 3, 4]
    ys = [dist[str(x)] for x in xs]
    bars = ax.bar(xs, ys, color=[COLORS["grey"]] + [COLORS["blue"]] * 4, width=0.68)
    for b, y in zip(bars, ys):
        ax.text(b.get_x() + b.get_width() / 2, y + 9, str(y), ha="center", fontsize=8)
    ax.set_xlabel("Gold FAIL rules per case")
    ax.set_ylabel("Cases")
    ax.set_xticks(xs)
    ax.set_ylim(0, max(ys) * 1.15)
    panel(ax, "a", "Case-level audit burden")

    ax = axes[1]
    rules = list(labels)
    pass_n = np.array([labels[r]["PASS"] for r in rules])
    fail_n = np.array([labels[r]["FAIL"] for r in rules])
    na_n = np.array([labels[r]["NA"] for r in rules])
    y = np.arange(len(rules))
    ax.barh(y, pass_n, color=COLORS["cyan"], label="PASS")
    ax.barh(y, fail_n, left=pass_n, color=COLORS["orange"], label="FAIL")
    ax.barh(y, na_n, left=pass_n + fail_n, color="#C9CED6", label="NA")
    for i, (p, f, n) in enumerate(zip(pass_n, fail_n, na_n)):
        if f:
            ax.text(p + f / 2, i, str(f), ha="center", va="center", fontsize=7, color="white", fontweight="bold")
        if n:
            ax.text(p + f + n / 2, i, str(n), ha="center", va="center", fontsize=7, color=COLORS["dark"])
    ax.set_yticks(y, rules)
    ax.invert_yaxis()
    ax.set_xlabel("Gold rule-instance pairs (n = 700 per rule)")
    ax.legend(frameon=False, ncol=3, loc="lower right")
    panel(ax, "b", "Gold label composition by rule")
    fig.suptitle("Supplementary Figure S1 | Benchmark and Gold-label structure", fontsize=11, fontweight="bold", y=1.02)
    fig.tight_layout()
    save(fig, "Figure_S1_benchmark_gold_structure")


def figure_s2() -> None:
    d = json.loads((RELEASE / "data/aggregate/gold_eval_models_summary.json").read_text())
    models = d["models"]
    names = [MODEL_LABELS[m] for m in models]
    sens = np.array(d["macro"]["sensitivity"])
    spec = np.array(d["macro"]["specificity"])

    fig = plt.figure(figsize=(7.2, 8.6))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 1.15, 1.15], hspace=0.44)
    ax = fig.add_subplot(gs[0])
    for i, (x, y) in enumerate(zip(spec, sens)):
        c = COLORS["grey"] if models[i] == "deterministic-baseline" else COLORS["blue"]
        ax.scatter(x, y, s=34, color=c, edgecolor="white", linewidth=0.5, zorder=3)
        if models[i] in {"gpt-5.2", "deterministic-baseline", "gemini-3-pro-preview-thinking", "gpt-oss-20b"}:
            offsets = {
                "gpt-5.2": (5, 4),
                "deterministic-baseline": (5, 4),
                "gemini-3-pro-preview-thinking": (-18, 8),
                "gpt-oss-20b": (5, -9),
            }
            ax.annotate(names[i], (x, y), xytext=offsets[models[i]], textcoords="offset points", fontsize=6.8)
    ax.set_xlabel("FAIL-class macro-specificity")
    ax.set_ylabel("FAIL-class macro-sensitivity")
    ax.set_xlim(max(0.74, spec.min() - 0.02), 1.008)
    ax.set_ylim(max(0.74, sens.min() - 0.02), 1.008)
    ax.grid(color="#E5E7EB", linewidth=0.6)
    panel(ax, "a", "Model-level discrimination")

    ax = fig.add_subplot(gs[1])
    heatmap(ax, np.array(d["matrix"]["sensitivity"]), names, d["rules"], "b   FAIL sensitivity by model and rule",
            vmin=0.55, vmax=1.0, cmap="Blues", annotate=True)
    ax = fig.add_subplot(gs[2])
    heatmap(ax, np.array(d["matrix"]["specificity"]), names, d["rules"], "c   FAIL specificity by model and rule",
            vmin=0.55, vmax=1.0, cmap="YlGn", annotate=True)
    fig.suptitle("Supplementary Figure S2 | Model discrimination diagnostics", fontsize=11, fontweight="bold", y=0.995)
    save(fig, "Figure_S2_model_discrimination")


def figure_s3() -> None:
    base = RELEASE / "data/tables_supp"
    na_rows = read_csv(base / "table_predicted_na_rates.csv")
    app_rows = read_csv(base / "table_s25a_applicability_metrics.csv")
    policy_rows = read_csv(base / "table_pred_na_policy_sensitivity.csv")

    model_ids = list(dict.fromkeys(r["model"] for r in na_rows))
    rules = list(dict.fromkeys(r["rule"] for r in na_rows))
    na_matrix = np.array([[float(next(r["pred_na_rate_on_gold_applicable"] for r in na_rows
                                      if r["model"] == m and r["rule"] == h)) for h in rules] for m in model_ids])
    names = [MODEL_LABELS.get(m, m) for m in model_ids]

    fig = plt.figure(figsize=(7.2, 8.8))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.3, 1.0, 1.25], hspace=0.46)
    ax = fig.add_subplot(gs[0])
    heatmap(ax, na_matrix, names, rules, "a   Predicted NA rate on Gold-applicable pairs",
            vmin=0, vmax=max(0.02, na_matrix.max()), cmap="Oranges", annotate=True)

    ax = fig.add_subplot(gs[1])
    for row in app_rows:
        x = float(row["na_specificity"])
        y = float(row["applicability_sensitivity"])
        name = "Deterministic" if row["model"] in {"Regex", "deterministic-baseline"} else row["model"]
        c = COLORS["grey"] if "Deterministic" in name else COLORS["purple"]
        ax.scatter(x, y, s=35, color=c, edgecolor="white", linewidth=0.5)
        if name in {"GPT-OSS-20B", "MiniMax", "Deterministic", "Gemini"}:
            offsets = {"GPT-OSS-20B": (5, 3), "MiniMax": (5, 2), "Deterministic": (-40, -12), "Gemini": (5, -10)}
            ax.annotate(name, (x, y), xytext=offsets[name], textcoords="offset points", fontsize=6.8)
    ax.set_xlabel("Gold-NA specificity")
    ax.set_ylabel("Gold-applicable sensitivity")
    ax.set_xlim(min(float(r["na_specificity"]) for r in app_rows) - 0.015, 1.005)
    ax.set_ylim(min(float(r["applicability_sensitivity"]) for r in app_rows) - 0.005, 1.0005)
    ax.grid(color="#E5E7EB", linewidth=0.6)
    panel(ax, "b", "Applicability discrimination")

    ax = fig.add_subplot(gs[2])
    policies = ["as_pass", "exclude", "as_fail"]
    policy_labels = ["NA as PASS", "exclude NA", "NA as FAIL"]
    pol_models = list(dict.fromkeys(r["model"] for r in policy_rows))
    for m in pol_models:
        vals = [float(next(r["macro_f1"] for r in policy_rows if r["model"] == m and r["pred_na_policy"] == p)) for p in policies]
        if m == "deterministic-baseline":
            c, lw, z = COLORS["grey"], 1.7, 4
        elif m == "gpt-5.2":
            c, lw, z = COLORS["orange"], 1.7, 4
        else:
            c, lw, z = COLORS["blue"], 0.8, 2
        ax.plot(range(3), vals, marker="o", markersize=3, linewidth=lw, alpha=0.78, color=c, zorder=z)
    ax.set_xticks(range(3), policy_labels)
    ax.set_ylabel("FAIL-class macro-F1")
    ax.set_xlim(-0.1, 2.1)
    ax.set_ylim(min(float(r["macro_f1"]) for r in policy_rows) - 0.02, 1.005)
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.6)
    handles = [
        mpl.lines.Line2D([], [], color=COLORS["blue"], marker="o", markersize=3, label="Other LLM systems"),
        mpl.lines.Line2D([], [], color=COLORS["orange"], marker="o", markersize=3, label="GPT-5.2"),
        mpl.lines.Line2D([], [], color=COLORS["grey"], marker="o", markersize=3, label="Deterministic baseline"),
    ]
    ax.legend(handles=handles, frameon=False, ncol=3, loc="lower left")
    panel(ax, "c", "Predicted-NA policy sensitivity")
    fig.suptitle("Supplementary Figure S3 | Applicability and predicted-NA sensitivity", fontsize=11, fontweight="bold", y=0.995)
    save(fig, "Figure_S3_applicability_predNA")


def figure_s4() -> None:
    base = RELEASE / "data/tables_supp"
    boot = read_csv(base / "table_s1_seed_cluster_bootstrap_selected.csv")
    evidence = read_csv(base / "table_evidence_endpoints_full700_aggregate.csv")
    snippets = read_csv(base / "table_s25b_snippet_count_sensitivity.csv")

    fig = plt.figure(figsize=(7.2, 9.4))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.25, 1.35, 1.15], hspace=0.48)

    ax = fig.add_subplot(gs[0])
    rows = boot[::-1]
    y = np.arange(len(rows))
    deltas = np.array([float(r["macro_f1_delta_a_minus_b"]) for r in rows])
    low = np.array([float(r["macro_f1_delta_ci95_low"]) for r in rows])
    high = np.array([float(r["macro_f1_delta_ci95_high"]) for r in rows])
    labels = [f"{r['bootstrap_scope'].replace('_seeds','').replace('_',' ')}: {MODEL_LABELS.get(r['model_a'],r['model_a'])} − {MODEL_LABELS.get(r['model_b'],r['model_b'])}" for r in rows]
    ax.errorbar(deltas, y, xerr=[deltas - low, high - deltas], fmt="o", color=COLORS["blue"], ecolor=COLORS["grey"], capsize=2)
    ax.axvline(0, color="#444444", linewidth=0.8, linestyle="--")
    ax.set_yticks(y, labels)
    ax.set_xlabel("Difference in FAIL-class macro-F1 (95% cluster-bootstrap CI)")
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.6)
    panel(ax, "a", "Seed-cluster uncertainty")

    ax = fig.add_subplot(gs[1])
    ev_names = [MODEL_LABELS.get(r["model"], r["model"]) for r in evidence]
    order = np.argsort([float(r["all_snippet_recoverability"]) for r in evidence])
    y = np.arange(len(evidence))
    metrics = [
        ("evidence_coverage", "Evidence coverage", COLORS["cyan"], "o"),
        ("conditional_item_recoverability", "Conditional item recoverability", COLORS["blue"], "s"),
        ("all_snippet_recoverability", "All-snippet recoverability", COLORS["orange"], "^")
    ]
    for j, (key, label, color, marker) in enumerate(metrics):
        vals = [float(evidence[i][key]) for i in order]
        ax.scatter(vals, y + (j - 1) * 0.18, s=24, label=label, color=color, marker=marker)
    ax.set_yticks(y, [ev_names[i] for i in order])
    ax.set_xlabel("Proportion")
    ax.set_xlim(0.55, 1.015)
    ax.legend(frameon=False, ncol=1, loc="lower right")
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.6)
    panel(ax, "b", "Evidence-traceability endpoints")

    ax = fig.add_subplot(gs[2])
    groups = ["0", "1", "2", "3+"]
    endpoint_keys = [
        ("first_snippet_recoverability", "First snippet", COLORS["cyan"]),
        ("all_snippet_recoverability", "All snippets", COLORS["orange"]),
        ("mean_recoverable_proportion", "Mean recoverable proportion", COLORS["purple"]),
    ]
    for key, label, color in endpoint_keys:
        vals = []
        for group in groups:
            finite = [float(r[key]) for r in snippets if r["snippet_count"] == group and r[key] not in ("", None)]
            vals.append(float(np.mean(finite)) if finite else np.nan)
        ax.plot(range(4), vals, marker="o", linewidth=1.8, label=label, color=color)
    ax.set_xticks(range(4), groups)
    ax.set_xlabel("Returned snippets per predicted FAIL (public synthetic layer)")
    ax.set_ylabel("Mean recoverability across systems")
    ax.set_ylim(0, 1.05)
    ax.grid(color="#E5E7EB", linewidth=0.6)
    ax.legend(frameon=False, ncol=1, loc="lower right")
    panel(ax, "c", "Sensitivity to snippet count")
    fig.suptitle("Supplementary Figure S4 | Uncertainty and evidence robustness", fontsize=11, fontweight="bold", y=0.995)
    save(fig, "Figure_S4_uncertainty_evidence")


def figure_s5() -> None:
    base = RELEASE / "data/tables_supp"
    semantic = read_csv(base / "table_s12_semantic_sufficiency_overall.csv")[0]
    taxonomy = read_csv(base / "table_taxonomy_l1_counts.csv")
    action = read_csv(base / "table_taxonomy_actionability_counts.csv")

    fig = plt.figure(figsize=(7.2, 8.4))
    gs = fig.add_gridspec(3, 1, height_ratios=[0.9, 1.35, 1.15], hspace=0.58)
    ax = fig.add_subplot(gs[0])
    labels = ["Lexically recoverable", "Semantically sufficient", "Recoverable but insufficient"]
    vals = [float(semantic["lexical_recoverability_rate"]), float(semantic["semantic_sufficiency_rate"]),
            float(semantic["recoverable_but_not_sufficient_rate"])]
    bars = ax.barh(range(3), vals, color=[COLORS["blue"], COLORS["cyan"], COLORS["orange"]])
    ax.set_yticks(range(3), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Proportion of the 96 reviewed citations")
    for b, v in zip(bars, vals):
        ax.text(min(v + 0.02, 0.94), b.get_y() + b.get_height() / 2, f"{v:.3f}", va="center", fontsize=8)
    panel(ax, "a", "Targeted semantic review")

    mid = gs[1].subgridspec(1, 2, width_ratios=[1.45, 0.85], wspace=0.48)
    ax = fig.add_subplot(mid[0])
    mech = sorted(taxonomy, key=lambda r: int(r["n"]))
    act = sorted(action, key=lambda r: int(r["n"]))
    mech_y = np.arange(len(mech))
    bars = ax.barh(mech_y, [int(r["n"]) for r in mech], color=COLORS["purple"], alpha=0.9)
    ax.set_yticks(mech_y, [r["Primary error mechanism"] for r in mech])
    for b, r in zip(bars, mech):
        ax.text(int(r["n"]) + 2, b.get_y() + b.get_height() / 2, r["n"], va="center", fontsize=7)
    ax.set_xlabel("Items in targeted mechanism sample (n = 214)")
    panel(ax, "b", "Primary error mechanism")
    ax2 = fig.add_subplot(mid[1])
    ax2.barh(range(len(act)), [int(r["n"]) for r in act], color=COLORS["gold"])
    ax2.set_yticks(range(len(act)), [r["Actionability category"] for r in act], fontsize=7)
    ax2.set_xlabel("Items (n)")
    ax2.set_title("Actionability", loc="left", fontsize=9, fontweight="bold")
    for i, r in enumerate(act):
        ax2.text(int(r["n"]) + 2, i, r["n"], va="center", fontsize=7)

    ax = fig.add_subplot(gs[2])
    ax.axis("off")
    panel(ax, "c", "Reviewer-facing audit workflow")
    steps = [
        ("1", "Read the record", "Apply frozen\nH1–H6 rules"),
        ("2", "Inspect predicted FAIL", "Check rule branch\nand applicability"),
        ("3", "Verify evidence", "Confirm verbatim\nrecord support"),
        ("4", "Resolve action", "Accept, correct,\nor escalate"),
    ]
    x0s = np.linspace(0.02, 0.77, 4)
    for i, (num, title, body) in enumerate(steps):
        x0 = x0s[i]
        rect = mpl.patches.FancyBboxPatch((x0, 0.25), 0.20, 0.48,
                                          boxstyle="round,pad=0.012,rounding_size=0.02",
                                          linewidth=1.0, edgecolor=COLORS["blue"], facecolor="#F4F8FC",
                                          transform=ax.transAxes)
        ax.add_patch(rect)
        ax.text(x0 + 0.10, 0.62, num, transform=ax.transAxes, ha="center", va="center",
                fontsize=12, fontweight="bold", color=COLORS["blue"])
        ax.text(x0 + 0.10, 0.49, title, transform=ax.transAxes, ha="center", va="center",
                fontsize=8, fontweight="bold")
        ax.text(x0 + 0.10, 0.36, body, transform=ax.transAxes, ha="center", va="center",
                fontsize=6.4, linespacing=1.15)
        if i < 3:
            ax.annotate("", xy=(x0s[i + 1] - 0.01, 0.49), xytext=(x0 + 0.21, 0.49), xycoords=ax.transAxes,
                        arrowprops=dict(arrowstyle="->", color=COLORS["grey"], linewidth=1.1))
    ax.text(0.5, 0.08, "Evidence traceability supports correction; it does not replace clinical review.",
            transform=ax.transAxes, ha="center", fontsize=7.5, color=COLORS["dark"])
    fig.suptitle("Supplementary Figure S5 | Human review, error taxonomy, and workflow", fontsize=11, fontweight="bold", y=0.995)
    save(fig, "Figure_S5_human_review_taxonomy_workflow")


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.out_dir
    OUT.mkdir(parents=True, exist_ok=True)
    figure_s1()
    figure_s2()
    figure_s3()
    figure_s4()
    figure_s5()
    print(f"Wrote five composite supplementary figures to {OUT}")


if __name__ == "__main__":
    main()
