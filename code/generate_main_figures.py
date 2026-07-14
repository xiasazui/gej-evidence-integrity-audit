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


def _write_case_level_burden(gold_dataset_summary: Dict[str, Any], out_dir: Path) -> Path:
    case_summary = gold_dataset_summary.get("case_level_summary") if isinstance(gold_dataset_summary.get("case_level_summary"), dict) else {}
    blocked_rate = float(gold_dataset_summary.get("gold_blocked_rate_any_fail") or 0.0)
    n_cases = int(gold_dataset_summary.get("n_labeled_cases") or gold_dataset_summary.get("n_case_files") or 0)
    blocked_cases = int(round(n_cases * blocked_rate))
    reviewable_cases = max(n_cases - blocked_cases, 0)

    fail_distribution_raw = case_summary.get("fail_rules_per_case_distribution") if isinstance(case_summary.get("fail_rules_per_case_distribution"), dict) else {}
    fail_distribution = {int(k): int(v) for k, v in fail_distribution_raw.items()}
    only_one_fail = case_summary.get("only_one_fail_rule_counts") if isinstance(case_summary.get("only_one_fail_rule_counts"), dict) else {}
    ordered_single_fail = sorted(((rule_id, int(count)) for rule_id, count in only_one_fail.items()), key=lambda item: (-item[1], item[0]))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _configure_matplotlib_fonts()

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.35), gridspec_kw={"width_ratios": [1.0, 1.12, 1.35]})

    ax = axes[0]
    ax.bar([0], [blocked_cases], color=_PALETTE["red"], width=0.58, label="Any FAIL")
    ax.bar([0], [reviewable_cases], bottom=[blocked_cases], color=_PALETTE["teal"], width=0.58, label="No FAIL")
    ax.set_ylim(0, max(n_cases, 1))
    ax.set_xticks([0])
    ax.set_xticklabels(["Cases"])
    ax.set_ylabel("Count")
    ax.text(0, blocked_cases / 2, f"{blocked_cases}\n({blocked_rate * 100:.1f}%)", ha="center", va="center", color="white", fontsize=6.8, fontweight="bold")
    ax.text(0, blocked_cases + reviewable_cases / 2, f"{reviewable_cases}\n({(1 - blocked_rate) * 100:.1f}%)", ha="center", va="center", color="white", fontsize=6.8, fontweight="bold")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2, handlelength=1.0, columnspacing=1.0)
    ax.grid(axis="y", color=_PALETTE["grid"], alpha=0.65, linewidth=0.45)
    _annotate_panel(ax, "A")

    ax = axes[1]
    xs = sorted(fail_distribution)
    ys = [fail_distribution[x] for x in xs]
    ax.bar(range(len(xs)), ys, color=_PALETTE["blue"], alpha=0.92)
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([str(x) for x in xs])
    ax.set_xlabel("Failed rules per case")
    ax.set_ylabel("Count")
    ax.grid(axis="y", color=_PALETTE["grid"], alpha=0.65, linewidth=0.45)
    for idx, value in enumerate(ys):
        ax.text(idx, value + max(n_cases * 0.005, 2), str(value), ha="center", va="bottom", fontsize=6.3)
    _annotate_panel(ax, "B")

    ax = axes[2]
    xs2 = np.arange(len(ordered_single_fail))
    ys2 = [count for _rule_id, count in ordered_single_fail]
    ax.bar(xs2, ys2, color=_PALETTE["violet"], alpha=0.9)
    ax.set_xticks(xs2)
    ax.set_xticklabels([rule_id for rule_id, _count in ordered_single_fail])
    ax.set_xlabel("Rule among cases with exactly one FAIL")
    ax.set_ylabel("Count")
    ax.grid(axis="y", color=_PALETTE["grid"], alpha=0.65, linewidth=0.45)
    for idx, value in enumerate(ys2):
        ax.text(idx, value + 1.5, str(value), ha="center", va="bottom", fontsize=6.3)
    _annotate_panel(ax, "C")

    fig.tight_layout(rect=(0, 0, 1, 0.91), w_pad=1.0)
    out_path = out_dir / "fig_case_level_burden.png"
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
    parser.add_argument("--out_dir", default="results/paper/figures")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gold_dataset_summary = _load_json(Path(args.gold_dataset_summary_json))
    eval_viz = _load_json(Path(args.gold_eval_viz_json))
    kappa = _load_json(Path(args.kappa_json))
    taxonomy_dir = Path(args.taxonomy_dir)

    wrote = [
        str(_write_case_level_burden(gold_dataset_summary, out_dir)),
        str(_write_f1_vs_grounding(eval_viz, out_dir)),
        str(_write_rule_distribution_and_kappa(gold_dataset_summary, kappa, out_dir)),
        str(_write_taxonomy_by_rule(taxonomy_dir, out_dir)),
    ]
    print(json.dumps({"wrote": wrote}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
