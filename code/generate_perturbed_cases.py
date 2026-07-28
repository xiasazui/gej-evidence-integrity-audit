from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple


REQUIRED_FIELDS: List[str] = [
    "姓名",
    "性别",
    "年龄",
    "主诉",
    "现病史",
    "既往史",
    "过敏史",
    "个人史",
    "家族史",
    "体格检查",
    "辅助检查",
    "诊断",
]


HISTOLOGY_TERMS_TO_CANCER: List[str] = [
    "印戒细胞癌",
    "神经内分泌癌",
    "鳞癌",
    "腺癌",
]

HISTOLOGY_TERMS_TO_REMOVE: List[str] = [
    "中-低分化",
    "中低分化",
    "低分化",
    "中分化",
    "高分化",
    "未分化",
    "神经内分泌",
    "印戒细胞",
    "分化",
]


GEJ_DIAG_HINT_RE = re.compile(r"(胃食管结合部|GEJ|贲门).{0,8}癌")


def _normalize_newlines(text: str) -> str:
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not s.endswith("\n"):
        s += "\n"
    return s


def _extract_int_from_name(name: str) -> int:
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def _set_or_append_line(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}[:：].*$")
    repl = f"{key}:{value}"
    if pattern.search(text):
        return pattern.sub(repl, text, count=1)

    m = re.search(r"(?m)^诊断[:：]", text)
    if m:
        return text[: m.start()] + repl + "\n" + text[m.start() :]

    return text.rstrip("\n") + "\n" + repl + "\n"


def _append_to_line(text: str, key: str, appendix: str, joiner: str = "；") -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}[:：](.*)$")
    m = pattern.search(text)
    if not m:
        return _set_or_append_line(text, key, appendix)

    current = (m.group(1) or "").strip()
    if not current:
        new_value = appendix
    elif appendix in current:
        return text
    else:
        new_value = current + joiner + appendix

    return pattern.sub(f"{key}:{new_value}", text, count=1)


def _get_diagnosis_value(text: str) -> str:
    m = re.search(r"(?m)^诊断[:：](.*)$", text)
    return (m.group(1) if m else "").strip()


def _set_diagnosis_value(text: str, value: str) -> str:
    return _set_or_append_line(text, "诊断", value.strip())


def _ensure_gej_cancer_diagnosis(text: str) -> str:
    dx = _get_diagnosis_value(text)
    if GEJ_DIAG_HINT_RE.search(dx):
        return text
    return _set_diagnosis_value(text, "胃食管结合部癌")


def _remove_clauses(text: str, patterns: List[re.Pattern[str]]) -> str:
    s = text
    for p in patterns:
        s = p.sub("", s)
    return s


def _strip_histology_terms(text: str) -> str:
    s = text
    for t in HISTOLOGY_TERMS_TO_CANCER:
        s = s.replace(t, "癌")
    for t in HISTOLOGY_TERMS_TO_REMOVE:
        s = s.replace(t, "")
    return s


def perturb_h1(text: str) -> str:
    s = _normalize_newlines(text)
    s = _ensure_gej_cancer_diagnosis(s)

    # Remove any explicit pathology/biopsy statements, and strip histology terms globally
    s = _remove_clauses(
        s,
        [
            re.compile(r"(?:活检病理|活检结果|活检提示|活检|病理(?:诊断)?|病检|组织学)[：: ]?[^。；;\n]*[。；;]?", re.IGNORECASE),
            re.compile(r"(?:免疫组化/分子|免疫组化|IHC)[：: ]?[^。；;\n]*[。；;]?", re.IGNORECASE),
        ],
    )
    s = _strip_histology_terms(s)

    # Make the absence explicit (without giving a histology type).
    s = _append_to_line(s, "辅助检查", "病理/活检：未提供组织学类型")

    # Ensure diagnosis does not itself provide a histology type (avoid LLM treating it as evidence).
    s = _set_diagnosis_value(s, _strip_histology_terms(_get_diagnosis_value(s)))
    s = _ensure_gej_cancer_diagnosis(s)
    return s


def perturb_h2(text: str) -> str:
    s = _normalize_newlines(text)
    s = _ensure_gej_cancer_diagnosis(s)

    # Remove endoscopy findings/details, leaving only an explicit "done but no report".
    s = _remove_clauses(
        s,
        [
            re.compile(r"(?:胃镜|内镜)[：: ]?[^。；;\n]*[。；;]?", re.IGNORECASE),
            re.compile(r"(?:定位)[：: ]?[^。；;\n]*[。；;]?", re.IGNORECASE),
            re.compile(r"(?:距门齿|距切牙)[^。；;\n]*?(?:cm|厘米)[^。；;\n]*[。；;]?", re.IGNORECASE),
            re.compile(r"\bEGJ\b[^。；;\n]*[。；;]?", re.IGNORECASE),
            re.compile(r"(?:Z线|齿状线)[^。；;\n]*?(?:cm|厘米)[^。；;\n]*[。；;]?", re.IGNORECASE),
        ],
    )

    s = _append_to_line(s, "辅助检查", "已行胃镜检查，但病历未记录任何所见/结果细节")
    return s


def _strip_stage_and_metastasis_from_dx(dx: str) -> str:
    s = dx
    s = re.sub(r"(转移|M1|m1|IV期|Ⅳ期|晚期)", "", s)
    s = re.sub(r"(临床分期|分期|cTNM|TNM|cT\d+[^；;，, ]*)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[ⅠⅡⅢⅣⅤVI]+期", "", s)
    s = re.sub(r"\b[IVX]+\b\s*期", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[0-9]+\s*期", "", s)
    parts = re.split(r"[；;]", s)
    s = (parts[0] if parts else s).strip()
    s = re.sub(r"\s{2,}", " ", s).strip("；;，, ")
    return s.strip()


def perturb_h3(text: str) -> str:
    s = _normalize_newlines(text)
    s = _ensure_gej_cancer_diagnosis(s)

    # Inject a clear distant-metastasis signal (M1) but keep diagnosis free of metastasis/stage language.
    s = _append_to_line(s, "辅助检查", "增强CT提示肝脏多发转移（M1）")

    dx = _get_diagnosis_value(s)
    dx2 = _strip_stage_and_metastasis_from_dx(dx)
    if not dx2:
        dx2 = "胃食管结合部癌"
    s = _set_diagnosis_value(s, dx2)
    s = _ensure_gej_cancer_diagnosis(s)
    return s


def _ensure_siewert_in_dx(dx: str, default_type: str = "II") -> str:
    if re.search(r"Siewert\s*[I|II|III]+", dx, flags=re.IGNORECASE):
        return dx
    base = dx.strip()
    if not base or not re.search(r"(胃食管结合部|GEJ|贲门)", base):
        base = "胃食管结合部癌"
    return f"Siewert {default_type}型{base}"


def perturb_h4(text: str) -> str:
    s = _normalize_newlines(text)

    dx = _get_diagnosis_value(s)
    dx = _strip_stage_and_metastasis_from_dx(dx)
    dx = _ensure_siewert_in_dx(dx, default_type="II")
    s = _set_diagnosis_value(s, dx)

    # Remove Z-line / dentate-line distance so that Siewert-type diagnosis lacks required distance evidence.
    s = _remove_clauses(
        s,
        [
            re.compile(r"(?:肿瘤中心)?\s*(?:距)?(?:齿状线|Z线)[^。；;\n]*?(?:cm|厘米)[^。；;\n]*[。；;]?", re.IGNORECASE),
            re.compile(r"(?:Z线上|Z线下|齿状线上|齿状线下)\s*\d+(?:\.\d+)?\s*(?:cm|厘米)", re.IGNORECASE),
        ],
    )
    return s


def perturb_h5(text: str) -> str:
    s = _normalize_newlines(text)

    # Ensure this rule is triggered: diagnosis must be GEJ or Siewert, and distance must exist.
    dx = _get_diagnosis_value(s)
    dx = _strip_stage_and_metastasis_from_dx(dx)
    if not re.search(r"(Siewert|胃食管结合部|GEJ)", dx, flags=re.IGNORECASE):
        dx = "胃食管结合部癌"
    s = _set_diagnosis_value(s, dx)

    # Remove existing Z-line / dentate-line distances, then inject an out-of-range one (>|5| cm).
    s = _remove_clauses(
        s,
        [
            re.compile(r"(?:肿瘤中心)?\s*(?:距)?(?:齿状线|Z线)[^。；;\n]*?(?:cm|厘米)[^。；;\n]*[。；;]?", re.IGNORECASE),
            re.compile(r"(?:Z线上|Z线下|齿状线上|齿状线下)\s*\d+(?:\.\d+)?\s*(?:cm|厘米)", re.IGNORECASE),
        ],
    )
    s = _append_to_line(s, "辅助检查", "定位：肿瘤中心距齿状线/Z线 Z线下6.0cm")
    return s


def perturb_h6(text: str) -> str:
    s = _normalize_newlines(text)
    # Remove one mandatory field line to force a Major failure.
    for key in ["过敏史", "体格检查", "个人史", "家族史", "既往史"]:
        pat = re.compile(rf"(?m)^{re.escape(key)}[:：].*(?:\n|$)")
        if pat.search(s):
            s = pat.sub("", s, count=1)
            break
    return s


def _validate_target_violation(text: str, rule_id: str) -> Tuple[bool, str]:
    s = text
    dx = _get_diagnosis_value(s)

    if rule_id == "H1":
        if not GEJ_DIAG_HINT_RE.search(dx):
            return False, "diagnosis not GEJ/cardia cancer"
        if re.search(r"(病理|活检).{0,30}(腺癌|鳞癌|印戒|神经内分泌|分化)", s):
            return False, "pathology/histology evidence still present"
        if re.search(r"(腺癌|鳞癌|印戒细胞癌|神经内分泌癌)", dx):
            return False, "diagnosis still contains histology type"
        return True, ""

    if rule_id == "H2":
        if not GEJ_DIAG_HINT_RE.search(dx):
            return False, "diagnosis not GEJ/cardia cancer"
        if re.search(r"(胃镜|内镜)[：: ].{0,60}(可见|溃疡|隆起|肿物|新生物)", s):
            return False, "endoscopy findings still present"
        if re.search(r"(距门齿|距切牙).{0,30}(cm|厘米)", s):
            return False, "incisor distance still present (may be treated as endoscopy detail)"
        if re.search(r"\bEGJ\b", s, flags=re.IGNORECASE):
            return False, "EGJ marker still present"
        return True, ""

    if rule_id == "H3":
        if not re.search(r"(肝转移|肺转移|骨转移|脑转移|腹膜转移|远处淋巴结转移|M1)", s):
            return False, "no distant-metastasis signal"
        if re.search(r"(转移|M1|IV期|Ⅳ期|晚期|分期)", dx):
            return False, "diagnosis still reflects metastasis/stage"
        return True, ""

    if rule_id == "H4":
        if not re.search(r"Siewert", dx, flags=re.IGNORECASE):
            return False, "diagnosis missing Siewert"
        if re.search(r"(Z线|齿状线).{0,10}(上|下)?\s*\d+(?:\.\d+)?\s*(cm|厘米)", s):
            return False, "Z-line/dentate distance still present"
        return True, ""

    if rule_id == "H5":
        if not re.search(r"(Siewert|胃食管结合部|GEJ)", dx, flags=re.IGNORECASE):
            return False, "diagnosis missing GEJ/Siewert"
        if not re.search(r"(Z线|齿状线).{0,20}下\s*6(?:\.0)?\s*(cm|厘米)", s):
            return False, "out-of-range distance not present"
        return True, ""

    if rule_id == "H6":
        missing = [k for k in REQUIRED_FIELDS if f"{k}:" not in s and f"{k}：" not in s]
        if not missing:
            return False, "no mandatory field removed"
        return True, ""

    return False, f"unknown rule_id: {rule_id}"


@dataclass(frozen=True)
class Seed:
    seed_id: str
    source_path: Path
    text: str


def _load_seeds(real_glob: str, mock_dir: str, mock_glob: str) -> List[Seed]:
    root = Path(__file__).resolve().parent
    real_paths = sorted(root.glob(real_glob), key=lambda p: _extract_int_from_name(p.name))
    mock_paths = sorted((root / mock_dir).glob(mock_glob), key=lambda p: _extract_int_from_name(p.name))

    seeds: List[Seed] = []
    for p in real_paths:
        idx = _extract_int_from_name(p.name)
        sid = f"real_{idx:02d}"
        seeds.append(Seed(seed_id=sid, source_path=p, text=p.read_text(encoding="utf-8")))
    for p in mock_paths:
        idx = _extract_int_from_name(p.name)
        sid = f"mock_{idx:03d}"
        seeds.append(Seed(seed_id=sid, source_path=p, text=p.read_text(encoding="utf-8")))
    return seeds


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PASS→FAIL perturbed cases for H1-H6.")
    parser.add_argument("--real_glob", default="data/real_cases_20/病历*.md")
    parser.add_argument("--mock_dir", default="data/mock_cases_80")
    parser.add_argument("--mock_glob", default="模拟病历*.md")
    parser.add_argument("--out_dir", default="data/perturb_cases_600")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    seeds = _load_seeds(args.real_glob, args.mock_dir, args.mock_glob)
    if not seeds:
        raise SystemExit("No seed cases found.")

    out_dir = Path(args.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not args.overwrite:
        raise SystemExit(f"Output dir not empty: {out_dir} (use --overwrite)")
    out_dir.mkdir(parents=True, exist_ok=True)

    perturbations: Dict[str, Callable[[str], str]] = {
        "H1": perturb_h1,
        "H2": perturb_h2,
        "H3": perturb_h3,
        "H4": perturb_h4,
        "H5": perturb_h5,
        "H6": perturb_h6,
    }

    manifest: List[Dict[str, str]] = []
    total = 0

    for seed in seeds:
        for rid, fn in perturbations.items():
            out_name = f"{seed.seed_id}_{rid}.md"
            out_path = out_dir / out_name

            pert = fn(seed.text)
            ok, msg = _validate_target_violation(pert, rid)
            if not ok:
                raise SystemExit(f"Validation failed for {out_name}: {msg}")

            out_path.write_text(pert, encoding="utf-8")
            manifest.append(
                {
                    "seed_id": seed.seed_id,
                    "rule_id": rid,
                    "source_path": str(seed.source_path),
                    "out_path": str(out_path),
                }
            )
            total += 1

    payload = {"total_cases": total, "seed_count": len(seeds), "per_seed": len(perturbations), "cases": manifest}
    (out_dir / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"seed_count": len(seeds), "generated": total, "out_dir": str(out_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
