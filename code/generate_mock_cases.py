from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class SiewertSpec:
    siewert: str
    z_cm_range: Tuple[float, float]
    incisor_cm_range: Tuple[float, float]
    icd: str


SIEWERT_SPECS: List[SiewertSpec] = [
    SiewertSpec(siewert="I", z_cm_range=(1.0, 5.0), incisor_cm_range=(35.0, 39.0), icd="C15"),
    SiewertSpec(siewert="II", z_cm_range=(-2.0, 1.0), incisor_cm_range=(39.0, 42.0), icd="C16"),
    SiewertSpec(siewert="III", z_cm_range=(-5.0, -2.0), incisor_cm_range=(42.0, 45.0), icd="C16"),
]

SURNAMES: List[str] = [
    "赵",
    "钱",
    "孙",
    "李",
    "周",
    "吴",
    "郑",
    "王",
    "冯",
    "陈",
    "褚",
    "卫",
    "蒋",
    "沈",
    "韩",
    "杨",
    "朱",
    "秦",
    "尤",
    "许",
    "何",
    "吕",
    "施",
    "张",
    "孔",
    "曹",
    "严",
    "华",
    "金",
    "魏",
    "陶",
    "姜",
    "戚",
    "谢",
    "邹",
    "喻",
    "柏",
    "水",
    "窦",
    "章",
    "云",
    "苏",
    "潘",
    "葛",
    "奚",
    "范",
    "彭",
    "郎",
    "鲁",
    "韦",
    "昌",
    "马",
    "苗",
    "凤",
    "花",
    "方",
    "俞",
    "任",
    "袁",
    "柳",
    "鲍",
    "史",
    "唐",
    "费",
    "廉",
    "岑",
    "薛",
    "雷",
    "贺",
    "倪",
    "汤",
    "滕",
    "殷",
    "罗",
    "毕",
    "郝",
    "邬",
    "安",
    "常",
    "乐",
    "于",
    "时",
    "傅",
    "皮",
    "卞",
    "齐",
    "康",
    "伍",
    "余",
    "元",
    "卜",
    "顾",
    "孟",
    "平",
    "黄",
    "和",
    "穆",
    "萧",
    "尹",
    "姚",
    "邵",
    "湛",
    "汪",
    "祁",
    "毛",
    "禹",
    "狄",
    "米",
    "贝",
    "明",
    "臧",
]

GIVEN_CHARS: List[str] = [
    "伟",
    "芳",
    "娜",
    "敏",
    "静",
    "丽",
    "强",
    "磊",
    "军",
    "洋",
    "勇",
    "艳",
    "杰",
    "娟",
    "涛",
    "明",
    "超",
    "秀",
    "霞",
    "平",
    "刚",
    "桂",
    "英",
    "辉",
    "鹏",
    "婷",
    "晨",
    "浩",
    "宇",
    "欣",
    "雪",
    "鑫",
    "凯",
    "健",
    "斌",
    "玲",
    "丹",
    "博",
    "莹",
    "东",
    "旭",
    "坤",
]

CHIEF_COMPLAINTS: List[str] = [
    "进食哽噎伴体重下降2月余",
    "吞咽困难1月余",
    "上腹部疼痛不适3周",
    "反酸烧心伴进食不适1月余",
    "乏力、纳差伴体重下降1月余",
    "体检胃镜发现食管-贲门占位10天",
]

ENDOSCOPY_SHAPES: List[str] = [
    "环周不规则溃疡隆起型肿物",
    "溃疡型新生物，表面糜烂出血",
    "菜花样隆起伴溃疡形成",
    "巨大溃疡，边缘隆起，覆白苔",
]

DIFFS: List[str] = ["高分化", "中分化", "中-低分化", "低分化"]

REGIMENS: List[str] = [
    "XELOX",
    "SOX",
    "FOLFOX",
]

IMMUNO_DRUGS: List[str] = [
    "信迪利单抗",
    "替雷利珠单抗",
    "帕博利珠单抗",
]

RESPONSE_WORDS: List[str] = ["PR", "SD"]

BIOMARKER_PROFILES: List[Tuple[str, str, str, int]] = [
    ("0", "pMMR", "MSS", 2),
    ("1+", "pMMR", "MSS", 5),
    ("2+", "pMMR", "MSS", 10),
    ("3+", "pMMR", "MSS", 1),
    ("0", "dMMR", "MSI-H", 15),
 ]

PAST_HISTORY: List[str] = [
    "无特殊",
    "高血压",
    "2型糖尿病",
    "慢阻肺",
    "脑出血术后",
]

PERSONAL_HISTORY: List[str] = [
    "无特殊",
    "长期吸烟史20年",
    "饮酒史10年，已戒酒",
    "长期吸烟史30年，已戒烟",
]

FAMILY_HISTORY: List[str] = [
    "否认肿瘤家族史",
    "无特殊",
]

PHYSICAL_EXAMS: List[str] = [
    "一般情况可",
    "消瘦",
    "家属咨询",
    "无特殊",
]


def _pick_name(rng: random.Random) -> str:
    surname = rng.choice(SURNAMES)
    given_len = 2 if rng.random() < 0.85 else 1
    given = "".join(rng.choice(GIVEN_CHARS) for _ in range(given_len))
    return surname + given


def _rand_date(rng: random.Random, start: date, end: date) -> date:
    if end <= start:
        return start
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def _rand_float_step(rng: random.Random, lo: float, hi: float, step: float = 0.1) -> float:
    if hi < lo:
        lo, hi = hi, lo
    n = int(round((hi - lo) / step))
    return round(lo + step * rng.randint(0, max(n, 0)), 1)


def _format_z_distance(z_cm: float) -> str:
    if z_cm >= 0:
        return f"Z线上{z_cm:.1f}cm"
    return f"Z线下{abs(z_cm):.1f}cm"


def _choose_stage(rng: random.Random) -> Tuple[str, str]:
    candidates: List[Tuple[str, str]] = [
        ("cT2N0M0", "II期"),
        ("cT3N+M0", "III期"),
        ("cT3-4N+M0", "III期"),
    ]
    return rng.choice(candidates)


def _build_case_text(
    *,
    idx: int,
    rng: random.Random,
    require_treatment: bool,
) -> str:
    sex = "男" if rng.random() < 0.72 else "女"
    age = rng.randint(45, 82)
    name = _pick_name(rng)

    spec = rng.choice(SIEWERT_SPECS)
    z_cm = _rand_float_step(rng, spec.z_cm_range[0], spec.z_cm_range[1], step=0.1)
    incisor_cm = _rand_float_step(rng, spec.incisor_cm_range[0], spec.incisor_cm_range[1], step=0.1)

    chief = rng.choice(CHIEF_COMPLAINTS)
    shape = rng.choice(ENDOSCOPY_SHAPES)
    diff = rng.choice(DIFFS)

    endo_date = _rand_date(rng, date(2025, 1, 10), date(2025, 11, 30))
    ct_date = endo_date + timedelta(days=rng.randint(5, 30))

    tnm, stage = _choose_stage(rng)

    present_lines: List[str] = []
    present_lines.append(
        f"{endo_date.isoformat()}胃镜：距门齿{incisor_cm:.1f}cm处EGJ/贲门可见{shape}，管腔轻度狭窄，可见接触性出血。"
    )
    present_lines.append(
        f"定位：肿瘤中心距齿状线/ Z线{_format_z_distance(z_cm)}，Siewert {spec.siewert}型。"
    )
    present_lines.append(f"活检病理：{diff}腺癌。")

    her2, mmr, msi, pdl1_cps = rng.choice(BIOMARKER_PROFILES)
    present_lines.append(f"免疫组化/分子：HER2({her2})；MMR({mmr})；MSI({msi})；PD-L1 CPS {pdl1_cps}。")
    present_lines.append(
        f"{ct_date.isoformat()}增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：{tnm}，{stage}。"
    )
    present_lines.append("PET-CT：未见明确远处转移。")

    treatment_text: Optional[str] = None
    if require_treatment:
        regimen = rng.choice(REGIMENS)
        immuno = rng.choice(IMMUNO_DRUGS)
        cycles = rng.randint(2, 6)
        last_date = ct_date + timedelta(days=rng.randint(10, 80))
        resp = rng.choice(RESPONSE_WORDS)
        treatment_text = (
            f"已行新辅助治疗：{regimen}+{immuno}共{cycles}周期；末次用药{last_date.isoformat()}；复查影像评效{resp}。"
        )

    if treatment_text:
        present_lines.append(treatment_text)

    past = rng.choice(PAST_HISTORY)
    allergy = "否认过敏史"
    personal = rng.choice(PERSONAL_HISTORY)
    family = rng.choice(FAMILY_HISTORY)
    physical = rng.choice(PHYSICAL_EXAMS)

    diagnosis = f"Siewert {spec.siewert}型胃食管结合部腺癌（{spec.icd}）；临床分期{stage}"

    lines: List[str] = []
    lines.append(f"姓名:{name}")
    lines.append(f"性别:{sex}")
    lines.append(f"年龄:{age}岁")
    lines.append("科别:胃肠外科门诊")
    lines.append(f"主诉:{chief}")
    lines.append("现病史:" + "".join(present_lines))
    lines.append(f"既往史:{past}")
    lines.append(f"过敏史:{allergy}")
    lines.append(f"个人史:{personal}")
    lines.append(f"家族史:{family}")
    lines.append(f"体格检查:{physical}")
    lines.append("辅助检查:见现病史")
    lines.append(f"诊断:{diagnosis}")

    return "\n".join(lines) + "\n"


def _basic_validate(text: str) -> List[str]:
    required_fields = [
        "姓名:",
        "性别:",
        "年龄:",
        "主诉:",
        "现病史:",
        "既往史:",
        "过敏史:",
        "个人史:",
        "家族史:",
        "体格检查:",
        "辅助检查:",
        "诊断:",
    ]
    missing = [f for f in required_fields if f not in text]

    if "胃镜" not in text and "内镜" not in text:
        missing.append("内镜描述")
    if "活检" not in text and "病理" not in text:
        missing.append("病理/活检描述")
    if "腺癌" not in text and "鳞癌" not in text and "分化" not in text:
        missing.append("组织学类型词")

    if "Z线" not in text and "齿状线" not in text:
        missing.append("Z线/齿状线距离")

    if "Siewert" in text and ("Z线上" not in text and "Z线下" not in text):
        missing.append("Siewert需要Z线距离")

    for k in ("HER2", "MMR", "MSI", "PD-L1"):
        if k not in text:
            missing.append(f"标志物字段缺失:{k}")

    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20251220)
    parser.add_argument("--out_dir", default="data/mock_cases_80")
    parser.add_argument("--treatment_ratio", type=float, default=0.6)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.n <= 0:
        raise SystemExit("--n must be > 0")
    if not (0.0 <= float(args.treatment_ratio) <= 1.0):
        raise SystemExit("--treatment_ratio must be between 0 and 1")

    rng = random.Random(int(args.seed))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, int(args.n) + 1):
        require_treatment = rng.random() < float(args.treatment_ratio)
        text = _build_case_text(idx=i, rng=rng, require_treatment=require_treatment)
        problems = _basic_validate(text)
        if problems:
            raise SystemExit(f"Generated case {i} failed validation: {problems}")

        out_path = out_dir / f"模拟病历{i}.md"
        if out_path.exists() and not args.overwrite:
            raise SystemExit(f"File already exists: {out_path}. Use --overwrite to replace.")
        out_path.write_text(text, encoding="utf-8")

    print(f"Generated {args.n} cases in: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
