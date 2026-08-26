from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


RELEASE = Path(__file__).resolve().parents[1]
OUT = RELEASE / "figures/main"
ASSET_OUT = OUT

MODEL_ORDER = [
    ("deepseek-v3.2-thinking", "DeepSeek"),
    ("gemini-3-pro-preview-thinking", "Gemini"),
    ("gpt-5.2", "GPT-5.2"),
    ("gpt-oss-20b", "GPT-OSS-20B"),
    ("gpt-oss-120b", "GPT-OSS-120B"),
    ("kimi-k2-thinking", "Kimi"),
    ("MiniMax-M2.1", "MiniMax"),
    ("qwen3-30b-a3b-thinking-2507", "Qwen3-30B"),
    ("qwen3-235b-a22b-thinking-2507", "Qwen3-235B"),
    ("qwen3-next-80b-a3b-thinking", "Qwen3-Next"),
    ("deterministic-baseline", "Regex"),
]
DISPLAY = dict(MODEL_ORDER)

BLUE = "#2563A6"
TEAL = "#0F8B8D"
ORANGE = "#D97706"
PURPLE = "#7C3AED"
RED = "#C2413B"
SLATE = "#475569"
LIGHT = "#E7EEF5"
GRID = "#D7DEE7"


plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7.2,
        "axes.labelsize": 7.5,
        "axes.titlesize": 8.0,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 6.6,
        "ytick.labelsize": 6.6,
        "legend.fontsize": 6.4,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def save(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ASSET_OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(ASSET_OUT / f"{stem}.svg", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(ASSET_OUT / f"{stem}.png", dpi=600, bbox_inches="tight", pad_inches=0.04)
    fig.savefig(ASSET_OUT / f"{stem}.tiff", dpi=600, bbox_inches="tight", pad_inches=0.04)


def panel(ax: plt.Axes, label: str, x: float = -0.08, y: float = 1.04) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontweight="bold", fontsize=9, va="bottom")


def box(ax: plt.Axes, xy: tuple[float, float], width: float, height: float, title: str, subtitle: str, color: str) -> None:
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.015,rounding_size=0.02",
        linewidth=0.9,
        edgecolor=color,
        facecolor="white",
    )
    ax.add_patch(patch)
    ax.text(xy[0] + width / 2, xy[1] + height * 0.62, title, ha="center", va="center", fontweight="bold", fontsize=7.5, color=color)
    ax.text(xy[0] + width / 2, xy[1] + height * 0.30, subtitle, ha="center", va="center", fontsize=6.5, color=SLATE)


def figure1() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25), gridspec_kw={"width_ratios": [1.18, 1.0]})

    ax = axes[0]
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    panel(ax, "a")
    box(ax, (0.02, 0.66), 0.25, 0.20, "100 seeds", "20 real + 80 synthetic", BLUE)
    box(ax, (0.37, 0.66), 0.27, 0.20, "600 variants", "one H1–H6 variant\nper seed", ORANGE)
    box(ax, (0.73, 0.66), 0.25, 0.20, "700 instances", "100 originals +\n600 variants", TEAL)
    for start, end in [((0.27, 0.76), (0.37, 0.76)), ((0.64, 0.76), (0.73, 0.76))]:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10, linewidth=1.0, color=SLATE))
    box(ax, (0.08, 0.22), 0.34, 0.20, "Frozen audit policy", "H1–H6 PASS / FAIL / NA", PURPLE)
    box(ax, (0.58, 0.22), 0.34, 0.20, "Frozen evaluation", "11 systems\n4,200 pairs/model", BLUE)
    ax.add_patch(FancyArrowPatch((0.42, 0.32), (0.58, 0.32), arrowstyle="-|>", mutation_scale=10, linewidth=1.0, color=SLATE))
    ax.add_patch(FancyArrowPatch((0.85, 0.66), (0.75, 0.42), arrowstyle="-|>", mutation_scale=10, linewidth=1.0, color=SLATE))
    ax.text(0.5, 0.04, "Gold-applicable pairs: 3,328/model; Gold-NA pairs: 872/model", ha="center", fontsize=6.7, color=SLATE)

    ax = axes[1]
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    panel(ax, "b")
    ax.set_title("Operator-induced coupling", pad=12, fontweight="bold")
    nodes = {"H2": (0.18, 0.70), "H4": (0.78, 0.70), "H5": (0.50, 0.20)}
    for label, (x, y) in nodes.items():
        circle = plt.Circle((x, y), 0.10, facecolor=LIGHT, edgecolor=BLUE, linewidth=1.2)
        ax.add_patch(circle)
        ax.text(x, y, label, ha="center", va="center", fontsize=9, fontweight="bold", color=BLUE)

    arrows = [
        ("H2", "H4", "97 PASS→FAIL", RED, 0.12),
        ("H2", "H5", "82 PASS→NA", ORANGE, -0.08),
        ("H4", "H5", "82 PASS→NA", ORANGE, 0.08),
    ]
    for source, target, label, color, rad in arrows:
        start = nodes[source]
        end = nodes[target]
        arrow = FancyArrowPatch(
            start,
            end,
            connectionstyle=f"arc3,rad={rad}",
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.4,
            color=color,
            shrinkA=18,
            shrinkB=18,
        )
        ax.add_patch(arrow)
        midx = (start[0] + end[0]) / 2
        midy = (start[1] + end[1]) / 2 + (0.10 if source == "H2" and target == "H4" else 0.01)
        ax.text(midx, midy, label, ha="center", va="center", fontsize=6.6, color=color, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.4})
    ax.text(0.5, 0.94, "Off-target changes: H2 98/100; H4 85/100", ha="center", fontsize=6.8, color=SLATE)
    ax.text(0.5, 0.02, "Transitions characterize the constructed operators, not clinical co-occurrence.", ha="center", fontsize=6.5, color=SLATE)

    fig.tight_layout(w_pad=1.3)
    save(fig, "Figure_1")
    plt.close(fig)


def figure2() -> None:
    data = json.loads((RELEASE / "data/aggregate/gold_eval_models_summary.json").read_text(encoding="utf-8"))
    summary_rows = load_csv(RELEASE / "data/tables/table_model_performance_summary.csv")
    summary = {row["model_identifier"]: row for row in summary_rows}
    metric_index = {model: idx for idx, model in enumerate(data["models"])}
    ordered = sorted(MODEL_ORDER, key=lambda item: float(summary[item[0]]["macro_f1"]))
    labels = [display for _model, display in ordered]
    y = np.arange(len(ordered))

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.65), gridspec_kw={"width_ratios": [1.0, 1.18, 0.76]})

    ax = axes[0]
    macro = np.array([float(summary[model]["macro_f1"]) for model, _ in ordered])
    micro = np.array([float(summary[model]["micro_f1"]) for model, _ in ordered])
    ax.scatter(macro, y + 0.13, s=20, color=BLUE, label="Macro-F1", zorder=3)
    ax.scatter(micro, y - 0.13, s=20, color=ORANGE, marker="s", label="Micro-F1", zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0.74, 1.01)
    ax.set_xlabel("FAIL-class F1 among Gold-applicable pairs")
    ax.grid(axis="x", color=GRID, linewidth=0.5)
    ax.legend(loc="lower right")
    panel(ax, "a")

    ax = axes[1]
    coverage = np.array([float(summary[model]["evidence_coverage"]) for model, _ in ordered])
    conditional = np.array([float(summary[model]["conditional_item_recoverability"]) for model, _ in ordered])
    all_snippet = np.array([float(summary[model]["all_snippet_recoverability"]) for model, _ in ordered])
    ax.scatter(coverage, y + 0.22, s=18, color=TEAL, marker="o", label="Evidence coverage", zorder=3)
    ax.scatter(conditional, y, s=18, color=PURPLE, marker="D", label="Conditional item recoverability", zorder=3)
    ax.scatter(all_snippet, y - 0.22, s=18, color=RED, marker="s", label="All-snippet recoverability", zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.set_xlim(0.50, 1.02)
    ax.set_xlabel("Evidence endpoint")
    ax.grid(axis="x", color=GRID, linewidth=0.5)
    ax.legend(loc="upper left", borderaxespad=0.35)
    panel(ax, "b")

    ax = axes[2]
    categories = ["Lexical\nrating", "Semantic\nsupport"]
    yes = [50 / 96, 90 / 96]
    partial = [41 / 96, 0]
    no = [5 / 96, 6 / 96]
    x = np.arange(2)
    ax.bar(x, yes, color=TEAL, label="Yes / sufficient")
    ax.bar(x, partial, bottom=yes, color="#E5B553", label="Partial")
    ax.bar(x, no, bottom=np.array(yes) + np.array(partial), color=RED, label="No / insufficient")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Proportion of targeted outputs")
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_yticklabels(["0", "0.5", "1.0"])
    ax.text(0, yes[0] / 2, "50/96", color="white", ha="center", va="center", fontsize=6.7, fontweight="bold")
    ax.text(1, yes[1] / 2, "90/96", color="white", ha="center", va="center", fontsize=6.7, fontweight="bold")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=1)
    panel(ax, "c")

    fig.tight_layout(w_pad=0.9)
    save(fig, "Figure_2")
    plt.close(fig)


def figure3() -> None:
    data = json.loads((RELEASE / "data/aggregate/gold_eval_models_summary.json").read_text(encoding="utf-8"))
    applicability_rows = load_csv(RELEASE / "data/tables_supp/table_s25a_applicability_metrics.csv")
    applicability = {row["model_identifier"]: row for row in applicability_rows}
    index = {model: idx for idx, model in enumerate(data["models"])}
    ordered = sorted(MODEL_ORDER, key=lambda item: float(data["macro"]["f1"][index[item[0]]]), reverse=True)
    labels = [display for _model, display in ordered]
    matrix = np.array([data["matrix"]["f1"][index[model]] for model, _display in ordered], dtype=float)

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.35), gridspec_kw={"width_ratios": [1.36, 1.0, 1.0]})
    ax = axes[0]
    image = ax.pcolormesh(
        np.arange(matrix.shape[1] + 1),
        np.arange(matrix.shape[0] + 1),
        matrix,
        vmin=0.0,
        vmax=1.0,
        cmap="Blues",
        shading="flat",
        rasterized=False,
    )
    ax.set_xlim(0, matrix.shape[1])
    ax.set_ylim(matrix.shape[0], 0)
    ax.set_xticks(np.arange(6) + 0.5)
    ax.set_xticklabels(data["rules"])
    ax.set_yticks(np.arange(len(labels)) + 0.5)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Audit rule")
    ax.set_title("FAIL-class F1")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix[row, col]
            color = "white" if value > 0.68 else "#1F2937"
            ax.text(col + 0.5, row + 0.5, f"{value:.2f}", ha="center", va="center", fontsize=5.4, color=color)
    cax = ax.inset_axes([1.02, 0.14, 0.045, 0.65])
    cmap = plt.get_cmap("Blues")
    for band in range(20):
        lower = band / 20
        cax.add_patch(Rectangle((0, lower), 1, 1 / 20, facecolor=cmap((band + 0.5) / 20), edgecolor="none"))
    cax.set_xlim(0, 1)
    cax.set_ylim(0, 1)
    cax.set_xticks([])
    cax.yaxis.tick_right()
    cax.set_yticks(np.linspace(0, 1, 6))
    cax.tick_params(labelsize=6, width=0.4, length=2)
    panel(ax, "a", y=1.10)

    ax = axes[1]
    for rank, (model, display) in enumerate(ordered, start=1):
        i = index[model]
        x = float(data["macro"]["specificity"][i])
        y = float(data["macro"]["sensitivity"][i])
        color = SLATE if model == "deterministic-baseline" else BLUE
        ax.scatter(x, y, s=34, color=color, zorder=3)
        if display in {"GPT-5.2", "Regex"}:
            ax.annotate(display, (x, y), xytext=(4, 2), textcoords="offset points", fontsize=5.8)
    ax.set_xlim(0.72, 1.01)
    ax.set_ylim(0.72, 1.01)
    ax.set_xlabel("FAIL-class macro-specificity")
    ax.set_ylabel("FAIL-class macro-sensitivity")
    ax.set_title("Gold-applicable discrimination")
    ax.grid(color=GRID, linewidth=0.5)
    panel(ax, "b", x=-0.18, y=1.10)

    ax = axes[2]
    for model, display in ordered:
        row = applicability[model]
        x = float(row["na_specificity"])
        y = float(row["applicability_sensitivity"])
        color = SLATE if model == "deterministic-baseline" else TEAL
        ax.scatter(x, y, s=34, color=color, zorder=3)
        if display in {"GPT-OSS-20B", "MiniMax", "Regex"}:
            ax.annotate(display, (x, y), xytext=(4, -6 if display in {"Regex", "MiniMax"} else 2), textcoords="offset points", fontsize=5.8)
    ax.set_xlim(0.86, 1.005)
    ax.set_ylim(0.994, 1.0003)
    ax.set_xlabel("Gold-NA specificity")
    ax.set_ylabel("Gold-applicable sensitivity")
    ax.set_title("Applicability classification")
    ax.grid(color=GRID, linewidth=0.5)
    panel(ax, "c", x=-0.18, y=1.10)

    fig.tight_layout(w_pad=1.0)
    save(fig, "Figure_3")
    plt.close(fig)


def main() -> None:
    global OUT, ASSET_OUT
    parser = argparse.ArgumentParser(description="Regenerate the three V3 main figures from frozen aggregate inputs.")
    parser.add_argument("--out_dir", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.out_dir
    ASSET_OUT = args.out_dir
    figure1()
    figure2()
    figure3()
    print(json.dumps({"figures": 3, "pdf_dir": str(OUT), "asset_dir": str(ASSET_OUT)}))


if __name__ == "__main__":
    main()
