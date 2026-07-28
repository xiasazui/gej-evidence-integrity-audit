from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


_CJK_FONT_FALLBACK: List[str] = [
    "PingFang SC",
    "Hiragino Sans GB",
    "STHeiti",
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
    "Noto Sans CJK SC",
    "DejaVu Sans",
]

_RULES: List[str] = ["H1", "H2", "H3", "H4", "H5", "H6"]
_MODEL_LABELS: Dict[str, str] = {
    "MiniMax-M2.1": "MiniMax",
    "deepseek-v3.2-thinking": "DeepSeek",
    "deterministic-baseline": "Regex",
    "gemini-3-pro-preview-thinking": "Gemini",
    "gpt-5.2": "GPT-5.2",
    "gpt-oss-120b": "GPT-OSS-120B",
    "gpt-oss-20b": "GPT-OSS-20B",
    "kimi-k2-thinking": "Kimi",
    "qwen3-235b-a22b-thinking-2507": "Qwen3-235B",
    "qwen3-30b-a3b-thinking-2507": "Qwen3-30B",
    "qwen3-next-80b-a3b-thinking": "Qwen3-Next",
}
_TAXONOMY_DISPLAY_LABELS: Dict[str, str] = {
    "RULE_TRIGGER_BRANCH": "Rule-trigger/branch boundary misunderstanding",
    "NUMERIC_REASONING": "Numeric reasoning failure",
    "FORMAT_STRUCTURED": "Structured-output failure",
    "EVIDENCE_MISS": "Evidence miss",
    "EVIDENCE_HALLUCINATION": "Evidence hallucination",
}
_TAXONOMY_AXIS_LABELS: Dict[str, str] = {
    "RULE_TRIGGER_BRANCH": "Rule-trigger/branch\nboundary misunderstanding",
    "NUMERIC_REASONING": "Numeric reasoning\nfailure",
    "FORMAT_STRUCTURED": "Structured-output\nfailure",
    "EVIDENCE_MISS": "Evidence miss",
    "EVIDENCE_HALLUCINATION": "Evidence\nhallucination",
}
_ACTIONABILITY_DISPLAY_LABELS: Dict[str, str] = {
    "rule_text": "Rule-text clarification",
    "parser": "Parser/output handling",
    "label_guideline": "Guideline revision",
}
_ACTIONABILITY_AXIS_LABELS: Dict[str, str] = {
    "rule_text": "Rule-text\nclarification",
    "parser": "Parser/output\nhandling",
    "label_guideline": "Guideline\nrevision",
}
_PALETTE: Dict[str, str] = {
    "blue": "#0F4D92",
    "blue_mid": "#3775BA",
    "blue_soft": "#B4C0E4",
    "red": "#B64342",
    "red_soft": "#E9A6A1",
    "teal": "#42949E",
    "violet": "#8F5B9A",
    "gold": "#B8872A",
    "neutral_light": "#D8D8D8",
    "neutral_mid": "#767676",
    "neutral_dark": "#272727",
    "grid": "#D9D9D9",
}


def _configure_matplotlib_fonts() -> None:
    import matplotlib

    matplotlib.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": _CJK_FONT_FALLBACK,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.unicode_minus": False,
            "font.size": 7.0,
            "axes.labelsize": 7.3,
            "axes.titlesize": 7.5,
            "axes.linewidth": 0.55,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "xtick.labelsize": 6.7,
            "ytick.labelsize": 6.7,
            "xtick.major.width": 0.5,
            "ytick.major.width": 0.5,
            "legend.fontsize": 6.5,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _save_fig(fig, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=600, bbox_inches="tight", pad_inches=0.04)
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.05)
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight", pad_inches=0.05)
    fig.savefig(out_path.with_suffix(".tiff"), dpi=600, bbox_inches="tight", pad_inches=0.05)


def _annotate_panel(ax, label: str) -> None:
    ax.text(-0.10, 1.04, label.lower(), transform=ax.transAxes, fontsize=8.3, fontweight="bold", va="bottom")


def _short_model_name(model_name: str) -> str:
    return _MODEL_LABELS.get(model_name, model_name)


def _taxonomy_display_name(label: str) -> str:
    return _TAXONOMY_DISPLAY_LABELS.get(label, label.replace("_", " ").title())


def _taxonomy_axis_label(label: str) -> str:
    return _TAXONOMY_AXIS_LABELS.get(label, _taxonomy_display_name(label))


def _actionability_display_name(label: str) -> str:
    return _ACTIONABILITY_DISPLAY_LABELS.get(label, label.replace("_", " ").title())


def _actionability_axis_label(label: str) -> str:
    return _ACTIONABILITY_AXIS_LABELS.get(label, _actionability_display_name(label))


def _taxonomy_counts_by_rule(taxonomy_dir: Path) -> Tuple[List[str], Dict[str, Counter[str]], Counter[str]]:
    counts_by_rule: Dict[str, Counter[str]] = defaultdict(Counter)
    actionability_counts: Counter[str] = Counter()
    for csv_path in sorted(taxonomy_dir.glob("*__taxonomy.csv")):
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                taxonomy_l1 = (row.get("taxonomy_l1") or "").strip()
                rule_id = (row.get("rule_id") or "").strip()
                actionability = (row.get("actionability") or "").strip()
                if taxonomy_l1 and rule_id:
                    counts_by_rule[rule_id][taxonomy_l1] += 1
                if actionability:
                    actionability_counts[actionability] += 1

    taxonomy_labels: List[str] = []
    seen: set[str] = set()
    for rule_id in _RULES:
        for taxonomy_l1, _count in counts_by_rule.get(rule_id, Counter()).most_common():
            if taxonomy_l1 not in seen:
                taxonomy_labels.append(taxonomy_l1)
                seen.add(taxonomy_l1)
    return taxonomy_labels, counts_by_rule, actionability_counts


def _write_benchmark_composition(composition_csv: Path, out_dir: Path) -> Path:
    """Draw the 100-seed to 700-instance construction without patient-level claims."""
    expected = {
        "real_original": {"n_instances": 20, "n_unique_seeds": 20},
        "synthetic_original": {"n_instances": 80, "n_unique_seeds": 80},
        "real_derived": {"n_instances": 120, "n_unique_seeds": 20},
        "synthetic_derived": {"n_instances": 480, "n_unique_seeds": 80},
    }
    with composition_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = {str(row.get("source_class") or "").strip(): dict(row) for row in csv.DictReader(handle)}
    if set(rows) != set(expected):
        raise SystemExit(f"Unexpected source classes in {composition_csv}: {sorted(rows)}")
    counts: Dict[str, int] = {}
    for source_class, expected_values in expected.items():
        row = rows[source_class]
        observed = {
            "n_instances": int(row.get("n_instances") or 0),
            "n_unique_seeds": int(row.get("n_unique_seeds") or 0),
        }
        if observed != expected_values:
            raise SystemExit(
                f"Composition mismatch for {source_class}: observed={observed}, expected={expected_values}"
            )
        counts[source_class] = observed["n_instances"]
    if sum(counts.values()) != 700:
        raise SystemExit(f"Composition total must be 700, got {sum(counts.values())}")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    _configure_matplotlib_fonts()
    matplotlib.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"]

    fig, ax = plt.subplots(figsize=(7.05, 3.25))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    real_edge = _PALETTE["blue"]
    real_face = "#EAF2F8"
    synthetic_edge = _PALETTE["gold"]
    synthetic_face = "#FBF4DF"
    final_edge = _PALETTE["neutral_dark"]
    final_face = "#F2F4F5"

    def box(
        x: float,
        y: float,
        w: float,
        h: float,
        edge: str,
        face: str,
        title: str,
        subtitle: str,
        *,
        dashed: bool = False,
    ) -> None:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.016",
            linewidth=0.9,
            linestyle=(0, (3.2, 2.0)) if dashed else "solid",
            edgecolor=edge,
            facecolor=face,
        )
        ax.add_patch(patch)
        ax.text(
            x + w / 2,
            y + h * 0.64,
            title,
            ha="center",
            va="center",
            fontsize=7.4,
            fontweight="bold",
            color=_PALETTE["neutral_dark"],
        )
        ax.text(
            x + w / 2,
            y + h * 0.29,
            subtitle,
            ha="center",
            va="center",
            fontsize=5.9,
            color=_PALETTE["neutral_mid"],
            linespacing=1.12,
        )

    ax.text(0.135, 0.955, "Seed records / templates", ha="center", va="center", fontsize=7.4, fontweight="bold")
    ax.text(0.505, 0.955, "Evaluation-instance layers", ha="center", va="center", fontsize=7.4, fontweight="bold")
    ax.text(0.865, 0.955, "Constructed benchmark", ha="center", va="center", fontsize=7.4, fontweight="bold")

    box(0.025, 0.575, 0.22, 0.255, real_edge, real_face, "20 de-identified real", "patient-level de-duplicated records\n(20 independent patients)")
    box(0.025, 0.225, 0.22, 0.255, synthetic_edge, synthetic_face, "80 script-generated", "synthetic templates\n(no real-file input)")

    box(0.385, 0.710, 0.24, 0.125, real_edge, "white", f"{counts['real_original']} real-original", "1 original per real seed")
    box(0.385, 0.545, 0.24, 0.125, real_edge, real_face, f"{counts['real_derived']} real-derived", "6 H1–H6 variants per real seed", dashed=True)
    box(0.385, 0.360, 0.24, 0.125, synthetic_edge, "white", f"{counts['synthetic_original']} synthetic-original", "1 original per synthetic seed")
    box(0.385, 0.195, 0.24, 0.125, synthetic_edge, synthetic_face, f"{counts['synthetic_derived']} synthetic-derived", "6 H1–H6 variants per template", dashed=True)

    # Branch each seed source into its retained original and six dependent variants.
    for seed_y, target_ys, edge in [
        (0.7025, (0.7725, 0.6075), real_edge),
        (0.3525, (0.4225, 0.2575), synthetic_edge),
    ]:
        ax.plot([0.245, 0.305], [seed_y, seed_y], color=edge, linewidth=0.9)
        ax.plot([0.305, 0.305], [min(target_ys), max(target_ys)], color=edge, linewidth=0.9)
        for target_y in target_ys:
            ax.annotate(
                "",
                xy=(0.382, target_y),
                xytext=(0.305, target_y),
                arrowprops={"arrowstyle": "-|>", "lw": 0.8, "color": edge, "mutation_scale": 7},
            )

    # Merge the four disclosed source layers into one benchmark total.
    output_centers = (0.7725, 0.6075, 0.4225, 0.2575)
    for y in output_centers:
        ax.plot([0.625, 0.695], [y, y], color=_PALETTE["neutral_mid"], linewidth=0.7)
    ax.plot([0.695, 0.695], [min(output_centers), max(output_centers)], color=_PALETTE["neutral_mid"], linewidth=0.8)
    ax.annotate(
        "",
        xy=(0.755, 0.515),
        xytext=(0.695, 0.515),
        arrowprops={"arrowstyle": "-|>", "lw": 0.9, "color": _PALETTE["neutral_mid"], "mutation_scale": 8},
    )

    final = FancyBboxPatch(
        (0.755, 0.335),
        0.22,
        0.36,
        boxstyle="round,pad=0.012,rounding_size=0.020",
        linewidth=1.05,
        edgecolor=final_edge,
        facecolor=final_face,
    )
    ax.add_patch(final)
    ax.text(0.865, 0.590, "700", ha="center", va="center", fontsize=18, fontweight="bold", color=real_edge)
    ax.text(0.865, 0.525, "evaluation instances", ha="center", va="center", fontsize=7.2, fontweight="bold")
    ax.plot([0.785, 0.945], [0.475, 0.475], color=_PALETTE["neutral_light"], linewidth=0.8)
    ax.text(0.865, 0.422, "100 originals + 600 variants", ha="center", va="center", fontsize=6.4)
    ax.text(0.865, 0.375, "100 seed clusters × 7", ha="center", va="center", fontsize=6.1, color=_PALETTE["neutral_mid"])

    note = FancyBboxPatch(
        (0.025, 0.025),
        0.95,
        0.105,
        boxstyle="round,pad=0.007,rounding_size=0.012",
        linewidth=0.65,
        edgecolor=_PALETTE["neutral_light"],
        facecolor="#FAFAFA",
    )
    ax.add_patch(note)
    ax.text(
        0.50,
        0.090,
        "Dependent by design: each seed contributes one original plus six rule-targeted variants; the 700 instances are not 700 patients or independent clinical records.",
        ha="center",
        va="center",
        fontsize=5.85,
        fontweight="bold",
        color=_PALETTE["neutral_dark"],
    )
    ax.text(
        0.50,
        0.052,
        "* Real records: one record per patient after patient-level de-duplication; derived variants do not represent additional patients.",
        ha="center",
        va="center",
        fontsize=5.35,
        color=_PALETTE["neutral_mid"],
    )

    fig.subplots_adjust(left=0.005, right=0.995, top=0.99, bottom=0.005)
    out_path = out_dir / "fig_benchmark_composition.png"
    _save_fig(fig, out_path)
    plt.close(fig)
    return out_path


def _write_f1_vs_grounding(eval_viz: Dict[str, Any], out_dir: Path) -> Path:
    models = [str(x) for x in (eval_viz.get("models") or [])]
    macro_f1 = [float(x) for x in (eval_viz.get("macro") or {}).get("f1", [])]
    evidence_rates = [float(x) for x in (eval_viz.get("evidence_in_text_rate") or [])]

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _configure_matplotlib_fonts()

    fig, ax = plt.subplots(figsize=(3.55, 2.75))
    order = sorted(range(len(models)), key=lambda idx: macro_f1[idx], reverse=True)
    top3 = set(order[:3])

    from matplotlib import patheffects as pe

    x_min = min(macro_f1) - 0.03
    max_x = max(macro_f1)
    right_col_x = max_x + 0.025
    x_max = max_x + 0.08
    y_min = max(min(evidence_rates) - 0.06, 0.0)
    y_max = min(max(evidence_rates) + 0.04, 1.04)

    # Place most labels in a right-side column and enforce a minimum vertical
    # separation to avoid text/point overlap and improve readability.
    right_col_indices = [i for i, x in enumerate(macro_f1) if x >= 0.94]
    desired_y = {i: evidence_rates[i] for i in right_col_indices}
    min_sep = 0.018
    margin = 0.01
    placed_y: Dict[int, float] = {}
    prev_y: float | None = None
    for idx in sorted(right_col_indices, key=lambda i: desired_y[i], reverse=True):
        y = desired_y[idx]
        if prev_y is not None and y > prev_y - min_sep:
            y = prev_y - min_sep
        placed_y[idx] = y
        prev_y = y
    if placed_y:
        min_label_y = min(placed_y.values())
        max_label_y = max(placed_y.values())
        if min_label_y < y_min + margin:
            shift = (y_min + margin) - min_label_y
            for k in list(placed_y):
                placed_y[k] += shift
        if max_label_y > y_max - margin:
            shift = max_label_y - (y_max - margin)
            for k in list(placed_y):
                placed_y[k] -= shift

    for idx, model_name in enumerate(models):
        color = _PALETTE["blue"] if idx in top3 else (_PALETTE["gold"] if model_name == "deterministic-baseline" else _PALETTE["neutral_mid"])
        size = 28 if idx in top3 else 21
        x = macro_f1[idx]
        y = evidence_rates[idx]
        ax.scatter(x, y, s=size, color=color, edgecolor="white", linewidth=0.7, zorder=4)
        if idx in placed_y:
            label_x, label_y = right_col_x, placed_y[idx]
            ha, va = "left", "center"
        else:
            label_x, label_y = x + 0.015, y + 0.006
            ha, va = "left", "center"
        annotation = ax.annotate(
            _short_model_name(model_name),
            (x, y),
            xytext=(label_x, label_y),
            textcoords="data",
            fontsize=5.9,
            color=_PALETTE["neutral_dark"],
            ha=ha,
            va=va,
            annotation_clip=False,
            bbox={"boxstyle": "round,pad=0.10", "facecolor": "white", "edgecolor": "none", "alpha": 0.82},
            arrowprops={"arrowstyle": "-", "color": "#A8A8A8", "lw": 0.45, "shrinkA": 3, "shrinkB": 3},
        )
        annotation.set_path_effects([pe.Stroke(linewidth=2.0, foreground="white"), pe.Normal()])

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("Macro-F1")
    ax.set_ylabel("Evidence-in-text rate")
    ax.grid(color=_PALETTE["grid"], alpha=0.65, linewidth=0.45)
    fig.tight_layout()
    out_path = out_dir / "fig_f1_vs_evidence_grounding.png"
    _save_fig(fig, out_path)
    plt.close(fig)
    return out_path


def _write_rule_distribution_and_kappa(gold_dataset_summary: Dict[str, Any], kappa: Dict[str, Any], out_dir: Path) -> Path:
    distribution = gold_dataset_summary.get("labels_distribution") if isinstance(gold_dataset_summary.get("labels_distribution"), dict) else {}
    per_rule_kappa = kappa.get("per_rule") if isinstance(kappa.get("per_rule"), dict) else {}

    pass_counts: List[int] = []
    fail_counts: List[int] = []
    na_counts: List[int] = []
    kappas: List[float] = []
    for rule_id in _RULES:
        row = distribution.get(rule_id, {}) if isinstance(distribution.get(rule_id), dict) else {}
        pass_counts.append(int(row.get("PASS") or 0))
        fail_counts.append(int(row.get("FAIL") or 0))
        na_counts.append(int(row.get("NA") or 0))
        kappas.append(float((per_rule_kappa.get(rule_id) or {}).get("kappa") or 0.0))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _configure_matplotlib_fonts()

    fig, axes = plt.subplots(1, 2, figsize=(6.7, 2.45), gridspec_kw={"width_ratios": [1.35, 1.0]})

    ax = axes[0]
    xs = np.arange(len(_RULES))
    ax.bar(xs, pass_counts, color=_PALETTE["teal"], label="PASS")
    ax.bar(xs, fail_counts, bottom=pass_counts, color=_PALETTE["red"], label="FAIL")
    bottoms = [p + f for p, f in zip(pass_counts, fail_counts)]
    ax.bar(xs, na_counts, bottom=bottoms, color=_PALETTE["neutral_light"], label="NA")
    ax.set_xticks(xs)
    ax.set_xticklabels(_RULES)
    ax.set_ylabel("Count")
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.02), handlelength=1.0, columnspacing=1.0)
    ax.grid(axis="y", color=_PALETTE["grid"], alpha=0.65, linewidth=0.45)
    for idx, value in enumerate(fail_counts):
        ax.text(xs[idx], pass_counts[idx] + value / 2, str(value), ha="center", va="center", color="white", fontsize=6.2, fontweight="bold")
    _annotate_panel(ax, "A")

    ax = axes[1]
    ax.bar(xs, kappas, color=_PALETTE["blue"], alpha=0.92)
    ax.set_xticks(xs)
    ax.set_xticklabels(_RULES)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Cohen's κ")
    ax.grid(axis="y", color=_PALETTE["grid"], alpha=0.65, linewidth=0.45)
    for idx, value in enumerate(kappas):
        ax.text(xs[idx], value + 0.02, f"{value:.3f}", ha="center", va="bottom", fontsize=6.1)
    _annotate_panel(ax, "B")

    fig.tight_layout(rect=(0, 0, 1, 0.91), w_pad=1.0)
    out_path = out_dir / "fig_rule_distribution_and_kappa.png"
    _save_fig(fig, out_path)
    plt.close(fig)
    return out_path


def _write_taxonomy_by_rule(taxonomy_dir: Path, out_dir: Path) -> Path:
    taxonomy_labels, counts_by_rule, actionability_counts = _taxonomy_counts_by_rule(taxonomy_dir)
    if not taxonomy_labels:
        raise SystemExit(f"No taxonomy rows found under: {taxonomy_dir}")

    matrix = np.array([[counts_by_rule.get(rule_id, Counter()).get(label, 0) for rule_id in _RULES] for label in taxonomy_labels], dtype=float)
    actionability_items = sorted(actionability_counts.items(), key=lambda item: (-item[1], item[0]))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _configure_matplotlib_fonts()

    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.75), gridspec_kw={"width_ratios": [1.45, 0.8]})

    ax = axes[0]
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(np.arange(len(_RULES)))
    ax.set_xticklabels(_RULES)
    ax.set_yticks(np.arange(len(taxonomy_labels)))
    ax.set_yticklabels([_taxonomy_axis_label(label) for label in taxonomy_labels], fontsize=6.2)
    ax.set_xlabel("Rule")
    ax.set_ylabel("Primary error mechanism")
    for row_idx in range(matrix.shape[0]):
        for col_idx in range(matrix.shape[1]):
            value = int(matrix[row_idx, col_idx])
            color = "white" if value >= max(matrix.max() * 0.45, 1) else _PALETTE["neutral_dark"]
            ax.text(col_idx, row_idx, str(value), ha="center", va="center", fontsize=5.9, color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.set_ylabel("Count", rotation=90)
    _annotate_panel(ax, "A")

    ax = axes[1]
    xs = np.arange(len(actionability_items))
    ys = [count for _name, count in actionability_items]
    ax.bar(xs, ys, color=_PALETTE["gold"], alpha=0.9)
    ax.set_xticks(xs)
    ax.set_xticklabels([_actionability_axis_label(name) for name, _count in actionability_items], fontsize=6.1)
    ax.set_ylabel("Count")
    ax.grid(axis="y", color=_PALETTE["grid"], alpha=0.65, linewidth=0.45)
    for idx, value in enumerate(ys):
        ax.text(idx, value + 1.2, str(value), ha="center", va="bottom", fontsize=6.2)
    _annotate_panel(ax, "B")

    fig.tight_layout(w_pad=1.6)
    out_path = out_dir / "fig_taxonomy_by_rule_and_actionability.png"
    _save_fig(fig, out_path)
    plt.close(fig)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold_dataset_summary_json", default="results/paper/gold_dataset_summary.json")
    parser.add_argument("--gold_eval_viz_json", default="data/gold/gold_700/gold_eval_viz/gold_eval_models_summary.json")
    parser.add_argument("--kappa_json", default="results/gold_eval/kappa_final_vs_b.json")
    parser.add_argument("--taxonomy_dir", default="results/paper/error_taxonomy")
    parser.add_argument(
        "--composition_csv",
        default="results/paper/dataset_composition_reanalysis_20260714/table_source_composition_4_layers.csv",
    )
    parser.add_argument("--out_dir", default="results/paper/figures")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gold_dataset_summary = _load_json(Path(args.gold_dataset_summary_json))
    eval_viz = _load_json(Path(args.gold_eval_viz_json))
    kappa = _load_json(Path(args.kappa_json))
    taxonomy_dir = Path(args.taxonomy_dir)

    wrote = [
        str(_write_benchmark_composition(Path(args.composition_csv), out_dir)),
        str(_write_f1_vs_grounding(eval_viz, out_dir)),
        str(_write_rule_distribution_and_kappa(gold_dataset_summary, kappa, out_dir)),
        str(_write_taxonomy_by_rule(taxonomy_dir, out_dir)),
    ]
    print(json.dumps({"wrote": wrote}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
