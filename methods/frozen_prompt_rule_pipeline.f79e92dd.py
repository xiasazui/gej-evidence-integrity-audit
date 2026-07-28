from __future__ import annotations

import json
import time
import re
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from config import LLMConfig, load_llm_config_from_env, resolve_llm_config
from gej_audit.llm_client import OpenAICompatibleClient


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    level: str
    severity: Optional[str]
    definition: str


RULE_ORDER: List[str] = [
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
]

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


RULE_DEFINITIONS: Dict[str, RuleDefinition] = {
    "H1": RuleDefinition(
        rule_id="H1",
        level="Hard",
        severity="Major",
        definition=(
            "#### H1 组织学证据（Hard）\n"
            "\n"
            "- **触发条件**：病历出现 GEJ/贲门相关恶性肿瘤的确诊性表述。\n"
            "- **判定**：触发后，必须存在病理/活检描述且包含组织学类型关键词（腺癌/鳞癌/印戒细胞癌/神经内分泌癌等）；缺失 -> FAIL（Major）。\n"
        ),
    ),
    "H2": RuleDefinition(
        rule_id="H2",
        level="Hard",
        severity="Major",
        definition=(
            "#### H2 内镜所见证据（Hard）\n"
            "\n"
            "- **触发条件**：病历出现 GEJ/贲门相关恶性肿瘤的确诊性表述。\n"
            "- **判定**：触发后，必须存在内镜/胃镜结果描述（需包含部位/形态等要点），不接受仅写“做过胃镜/已行胃镜”。缺失 -> FAIL（Major）。\n"
        ),
    ),
    "H3": RuleDefinition(
        rule_id="H3",
        level="Hard",
        severity="Major",
        definition=(
            "#### H3 远处转移-诊断一致性（Hard）\n"
            "\n"
            "- **触发条件**：病历明确描述**远处转移**（肝/肺/骨/脑/腹膜转移，或远处淋巴结转移等），或出现 M1/IV期/晚期 等表述。\n"
            "- **判定**：触发后，诊断中需体现转移或分期（如“转移/M1/IV期/晚期”）；否则 -> FAIL（Major）。\n"
            "- **注意**：区域淋巴结肿大（N+、7/8/9 组等）不视为远处转移，不触发本条。\n"
        ),
    ),
    "H4": RuleDefinition(
        rule_id="H4",
        level="Hard",
        severity="Major",
        definition=(
            "#### H4 定位证据完整性（Hard）\n"
            "\n"
            "- **触发条件**：出现 GEJ/贲门癌/远端食管腺癌/贲门下胃癌 或 Siewert I/II/III 的确诊性表述。\n"
            "- **判定**：\n"
            "  1) 若诊断写明 **Siewert I/II/III** 或明确为 **远端食管腺癌/贲门癌/贲门下胃癌**：\n"
            "     - 必须提供可复核的 **Z线/齿状线相对距离证据**，满足其一即可：\n"
            "       - 肿瘤中心相对 Z线/齿状线距离（如“Z线上/下 X cm”“距齿状线 X cm”等）；或\n"
            "       - 病变 **上界/下界** 相对 Z线/齿状线距离（如“上界至齿状线上 0.5cm”“下界距Z线下 2cm”等）。\n"
            "       仅提供 CT/PET/MR 的部位描述不计入本条定位证据。缺失 -> FAIL（Critical）。\n"
            "  2) 若诊断仅写 **GEJ/胃食管结合部癌**：需提供可复核定位证据之一：\n"
            "     - 内镜定位（贲门/食管胃交界/EGJ/Z线附近/下段食管-贲门交界等），或\n"
            "     - 距门齿/切牙距离，或\n"
            "     - Z线/齿状线距离；\n"
            "     **不接受仅有 CT/PET/MR 的部位描述** 作为定位证据。\n"
            "     仅缺定位证据 -> FAIL（Major）。\n"
        ),
    ),
    "H5": RuleDefinition(
        rule_id="H5",
        level="Hard",
        severity="Critical",
        definition=(
            "#### H5 定位一致性（Siewert/GEJ 距离阈值）（Hard）\n"
            "\n"
            "- **触发条件**：病历同时存在以下两类信息之一：\n"
            "  1) 诊断写明 **Siewert I/II/III** 且记录了肿瘤中心相对 **Z线/齿状线** 的距离；或\n"
            "  2) 诊断为 **GEJ/胃食管结合部癌** 且记录了肿瘤中心相对 **Z线/齿状线** 的距离。\n"
            "  若仅有诊断而缺少距离信息：本条不做一致性判定 -> NA（缺失由定位证据规则处理）。\n"
            "  若仅提供“上界/下界至 Z线/齿状线距离”而未给出中心距离：本条同样 -> NA。\n"
            "- **判定**：以下任一不满足 -> FAIL（Critical）。\n"
            "  1) 若诊断写明 **Siewert I/II/III** 且已提供 Z线/齿状线距离：分型范围必须一致：\n"
            "     - I：Z线上 1-5cm\n"
            "     - II：Z线上 1cm ~ Z线下 2cm\n"
            "     - III：Z线下 2-5cm\n"
            "  2) 若诊断为 **GEJ/胃食管结合部癌** 且已提供 Z线/齿状线距离：\n"
            "     - 若距离超出 ±5cm 仍诊断 GEJ -> FAIL（Critical）。\n"
        ),
    ),
    "H6": RuleDefinition(
        rule_id="H6",
        level="Hard",
        severity="Major",
        definition=(
            "#### H6 病历要素与命名规范（Hard）\n"
            "\n"
            "- **触发条件**：所有病历。\n"
            "- **判定**：\n"
            "  1) 必备字段必须存在且内容**非空**：姓名、性别、年龄、主诉、现病史、既往史、过敏史、个人史、家族史、体格检查、辅助检查、诊断；缺任一或字段值为空（如“既往史:”冒号后为空）-> FAIL（Major）。\n"
            "  2) 诊断命名可复核为规范化恶性肿瘤诊断（含 C15/C16 等 ICD 样式，或部位+恶性性质明确）；否则 -> FAIL（Minor）。\n"
            "  - severity 规则：违反 1) => Major；仅违反 2) => Minor。\n"
        ),
    ),
}

COMPACT_RULE_TEXT: Dict[str, str] = {
    "H1": (
        "#### H1 组织学证据（Hard）\n"
        "- 触发：病历出现 GEJ/贲门相关恶性肿瘤的确诊性表述。\n"
        "- 判定：触发后必须出现病理/活检描述且包含组织学类型词（腺癌/鳞癌/印戒细胞癌/神经内分泌癌等）。缺失 -> FAIL（Major）。\n"
    ),
    "H2": (
        "#### H2 内镜所见证据（Hard）\n"
        "- 触发：病历出现 GEJ/贲门相关恶性肿瘤的确诊性表述。\n"
        "- 判定：触发后必须出现胃镜/内镜所见结果（需包含部位/形态要点）；仅写“已行/做过胃镜”不算。缺失 -> FAIL（Major）。\n"
    ),
    "H3": (
        "#### H3 远处转移-诊断一致性（Hard）\n"
        "- 触发：出现远处转移（肝/肺/骨/脑/腹膜/远处淋巴结转移等）或 M1/IV期/晚期。\n"
        "- 判定：触发后诊断中必须体现转移或分期（转移/M1/IV期/晚期）。否则 -> FAIL（Major）。\n"
        "- 注意：区域淋巴结 N+ 不算远处转移。\n"
    ),
    "H4": (
        "#### H4 定位证据完整性（Hard）\n"
        "- 触发：诊断出现 GEJ/贲门癌/远端食管腺癌/贲门下胃癌 或 Siewert I/II/III。\n"
        "- 判定：\n"
        "  1) 若诊断写明 Siewert I/II/III 或 远端食管腺癌/贲门癌/贲门下胃癌：必须给可复核 Z线/齿状线相对距离证据：中心距离或上/下界距离（任一即可）；缺失 -> FAIL（Critical）。\n"
        "  2) 若诊断仅写 GEJ：必须提供可复核定位证据之一（内镜定位/距门齿或切牙距离/Z线距离）；缺失 -> FAIL（Major）。\n"
        "  - 注意：CT/PET/MR 的部位描述不作为 H4 定位证据。\n"
    ),
    "H5": (
        "#### H5 定位一致性（Hard）\n"
        "- 触发：诊断(含 Siewert 或 GEJ) + 同时提供肿瘤中心的 Z线/齿状线距离。\n"
        "- 若只给上/下界距离而无中心距离：本条 NA。\n"
        "- 判定（任一不满足 -> FAIL Critical）：\n"
        "  1) Siewert I：Z线上1-5cm；II：Z线上1cm~Z线下2cm；III：Z线下2-5cm。\n"
        "  2) 诊断为 GEJ 且提供距离：若距离超出 ±5cm 仍诊断 GEJ -> FAIL。\n"
        "- 数值解释：Z线上xcm 记 d=+x；Z线下xcm 记 d=-x；“Z线上a~Z线下b”代表 d∈[-b,+a]。\n"
    ),
    "H6": (
        "#### H6 病历要素与命名规范（Hard）\n"
        "- 必备字段必须存在且非空：姓名、性别、年龄、主诉、现病史、既往史、过敏史、个人史、家族史、体格检查、辅助检查、诊断；缺任一或字段值为空 -> FAIL（Major）。\n"
        "- 诊断命名不规范（无法对应 C15/C16 或 部位+恶性性质不明确）-> FAIL（Minor）。\n"
    ),
}


@dataclass
class RuleCheck:
    rule_id: str
    level: str
    status: str
    severity: Optional[str] = None
    reason: Optional[str] = None
    evidence: List[str] | None = None


def _extract_first_json_object(text: str, allowed_status: Optional[set[str]] = None) -> Dict[str, Any]:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
        s = s.strip()

    def _unwrap(obj: Any) -> Any:
        def _extract_obj_from_text(raw_text: str) -> Optional[Dict[str, Any]]:
            t = str(raw_text or "").strip()
            if not t:
                return None
            if t.startswith("```"):
                t = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", t)
                t = re.sub(r"\n```\s*$", "", t)
                t = t.strip()

            try:
                maybe = json.loads(t)
                if isinstance(maybe, dict):
                    return maybe
            except Exception:
                pass

            dec = json.JSONDecoder()
            idx2 = 0
            while True:
                start2 = t.find("{", idx2)
                if start2 == -1:
                    return None
                try:
                    maybe2, end2 = dec.raw_decode(t[start2:])
                except json.JSONDecodeError:
                    idx2 = start2 + 1
                    continue
                if isinstance(maybe2, dict):
                    return maybe2
                idx2 = start2 + max(end2, 1)

        cur = obj
        for _ in range(3):
            if not isinstance(cur, dict):
                return cur
            if isinstance(cur.get("rule_id"), str) and cur.get("rule_id"):
                return cur

            # Common wrappers from some OpenAI-compatible gateways / models.
            for k in ("final", "output", "answer", "result", "data"):
                if k not in cur:
                    continue
                v = cur.get(k)
                if isinstance(v, dict):
                    cur = v
                    break
                if isinstance(v, str):
                    maybe_obj = _extract_obj_from_text(v)
                    if isinstance(maybe_obj, dict):
                        cur = maybe_obj
                        break
            else:
                return cur
        return cur

    decoder = json.JSONDecoder()

    try:
        obj = json.loads(s)
        obj = _unwrap(obj)
        if isinstance(obj, dict):
            rid = obj.get("rule_id")
            if isinstance(rid, str) and "?" in rid:
                raise ValueError("Schema placeholder JSON")
        return obj
    except Exception:
        pass

    idx = 0
    while True:
        start = s.find("{", idx)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(s[start:])
        except json.JSONDecodeError:
            idx = start + 1
            continue

        idx = start + max(end, 1)
        if not isinstance(obj, dict):
            continue

        rid = obj.get("rule_id")
        if isinstance(rid, str) and "?" in rid:
            continue

        obj = _unwrap(obj)
        return obj

    raise ValueError(f"No JSON object found in: {text[:500]}")


def _extract_siewert_ranges_from_definition(definition: str) -> Optional[Dict[str, Tuple[float, float]]]:
    s = str(definition or "")
    if "Siewert" not in s:
        return None
    if ("Z\u7ebf" not in s) and ("\u9f7f\u72b6\u7ebf" not in s):
        return None

    def _as_float(x: str) -> Optional[float]:
        try:
            return float(x)
        except Exception:
            return None

    ranges: Dict[str, Tuple[float, float]] = {}

    m1 = re.search(r"\bI\b\s*[\uFF1A:]\s*Z\u7ebf\s*\u4e0a\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*cm", s)
    if m1:
        a = _as_float(m1.group(1))
        b = _as_float(m1.group(2))
        if a is not None and b is not None:
            lo, hi = (a, b) if a <= b else (b, a)
            ranges["I"] = (lo, hi)

    m3 = re.search(r"\bIII\b\s*[\uFF1A:]\s*Z\u7ebf\s*\u4e0b\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*cm", s)
    if m3:
        a = _as_float(m3.group(1))
        b = _as_float(m3.group(2))
        if a is not None and b is not None:
            lo_u, hi_u = (a, b) if a <= b else (b, a)
            ranges["III"] = (-hi_u, -lo_u)

    m2 = re.search(
        r"\bII\b\s*[\uFF1A:]\s*Z\u7ebf\s*\u4e0a\s*(\d+(?:\.\d+)?)\s*cm\s*[~～\\-–—至]\s*Z\u7ebf\s*\u4e0b\s*(\d+(?:\.\d+)?)\s*cm",
        s,
    )
    if m2:
        up = _as_float(m2.group(1))
        down = _as_float(m2.group(2))
        if up is not None and down is not None:
            ranges["II"] = (-abs(down), abs(up))

    return ranges if ranges else None


def _case_snippet_for_rule(rule_id: str, case_text: str) -> str:
    s = (case_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not s:
        return ""

    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]

    def _uniq_keep(items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for it in items:
            key = it.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    # Always keep a little header + diagnosis line if present.
    header_keys = ("姓名", "性别", "年龄", "科别", "主诉", "诊断")

    def _is_key_line(ln: str, keys: Tuple[str, ...]) -> bool:
        for k in keys:
            if re.search(rf"^{re.escape(k)}\s*[:：]", ln):
                return True
        return False

    keep: List[str] = []
    for ln in lines:
        if _is_key_line(ln, header_keys):
            keep.append(ln)

    # Rule-specific snippets.
    kw: List[str] = []
    if rule_id == "H1":
        kw = ["病理", "活检", "组织学", "免疫组化", "IHC", "腺癌", "鳞癌", "印戒", "神经内分泌", "分化"]
    elif rule_id == "H2":
        kw = ["胃镜", "内镜", "所见", "溃疡", "隆起", "肿物", "新生物", "EGJ", "距门齿", "距切牙", "Z线", "齿状线"]
    elif rule_id == "H3":
        kw = ["转移", "远处", "M1", "IV", "Ⅳ", "晚期", "肝", "肺", "骨", "脑", "腹膜", "PET", "CT", "MRI"]
    elif rule_id in ("H4", "H5"):
        kw = ["Siewert", "Z线", "齿状线", "距门齿", "距切牙", "EGJ", "贲门", "远端食管", "贲门下胃"]
    elif rule_id == "H6":
        kw = list(REQUIRED_FIELDS)

    if kw:
        pat = re.compile("|".join(re.escape(k) for k in kw), re.IGNORECASE)
        for ln in lines:
            if pat.search(ln):
                keep.append(ln)

    keep = _uniq_keep(keep)

    max_lines_raw = (os.getenv("LLM_CASE_SNIPPET_MAX_LINES") or "").strip()
    try:
        max_lines = int(max_lines_raw) if max_lines_raw else 40
    except ValueError:
        max_lines = 40
    if max_lines < 5:
        max_lines = 5

    snippet = "\n".join(keep[:max_lines])
    if not snippet:
        snippet = "\n".join(lines[:max_lines])

    return snippet.strip()


def _build_rule_agent_messages(rule: RuleDefinition, case_text: str) -> List[Dict[str, str]]:
    schema = (
        f'{{"rule_id":"{rule.rule_id}","level":"Hard","status":"PASS|FAIL|NA",'
        '"severity":"Major|Minor|Critical|null","reason":"string|null","evidence":["..."]}'
    )
    guide = (
        "Hard：不适用/未触发 -> NA；触发且满足 -> PASS；触发且缺失/不一致 -> FAIL。\n"
        "NA/PASS：severity=null, reason=null, evidence=[].\n"
        "FAIL：severity 必填(Major/Minor/Critical), reason 必填, evidence 从原文摘录(≤3条, 每条≤80字)。"
    )

    if rule.rule_id in ("H4", "H5") or ("Siewert" in rule.definition and "Z\u7ebf" in rule.definition):
        ranges = _extract_siewert_ranges_from_definition(rule.definition)
        if ranges and all(k in ranges for k in ("I", "II", "III")):
            r1 = ranges["I"]
            r2 = ranges["II"]
            r3 = ranges["III"]
            range_hint = (
                "Siewert/Z-line hint: interpret 'Z线上xcm' as d=+x and 'Z线下xcm' as d=-x; compare using d. "
                f"Ranges in this rule: I[{r1[0]:+.1f},{r1[1]:+.1f}], II[{r2[0]:+.1f},{r2[1]:+.1f}], III[{r3[0]:+.1f},{r3[1]:+.1f}] (cm)."
            )
        else:
            range_hint = (
                "Siewert/Z-line hint: interpret 'Z线上xcm' as d=+x and 'Z线下xcm' as d=-x; "
                "an interval like 'Z线上a ~ Z线下b' means d∈[-b,+a], not 'd>=+a'."
            )
        guide = guide + "\n" + range_hint

    sys = (
        "你是门诊病历‘诊断证据完整性审计’系统的规则审计智能体。\n"
        "严格依据给定规则定义进行检查。\n"
        "只输出严格 JSON 对象，禁止输出任何解释、分析或 Markdown。"
    )

    case_text_for_prompt = case_text
    snippet_env = (os.getenv("LLM_CASE_SNIPPET_MODE") or "").strip().lower()
    if snippet_env in ("1", "true", "yes", "on"):
        snippet = _case_snippet_for_rule(rule.rule_id, case_text)
        if snippet:
            case_text_for_prompt = "（仅截取与本规则相关的片段）\n" + snippet

    compact_env = (os.getenv("LLM_COMPACT_RULE_PROMPT") or "").strip().lower()
    rule_text = rule.definition
    if compact_env in ("1", "true", "yes", "on"):
        rule_text = COMPACT_RULE_TEXT.get(rule.rule_id, rule.definition)

    user = (
        f"规则定义：\n{rule_text}\n\n"
        f"病历文本：\n{case_text_for_prompt}\n\n"
        f"{guide}\n"
        "约束：reason 只能陈述事实，不要出现‘建议/请/应当/需要’等措辞；不要输出多余字段。\n"
        f"输出 JSON 必须匹配：{schema}"
    )

    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]


def _escape_md_table_cell(text: str) -> str:
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    s = s.replace("|", "\\|")
    s = s.replace("\n", "<br>")
    return s


def _sanitize_reason_text(reason: str) -> str:
    s = str(reason or "").strip()
    if not s:
        return ""
    s = re.sub(r"(建议|请|需要|需|应)\s*(补充|补全|完善|记录|注明|填写)", "缺少", s)
    s = re.sub(r"^(建议|请|需要|需|应)[：: ]+", "", s)
    return s.strip()


def _normalize_hard_status(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""

    u = s.upper()

    if u in ("NA", "N/A", "NOT_APPLICABLE", "NOTAPPLICABLE", "NOT-APPLICABLE"):
        return "NA"

    if u in ("PASS", "OK", "YES", "TRUE", "Y", "1"):
        return "PASS"
    if u in ("FAIL", "NO", "FALSE", "N", "0"):
        return "FAIL"

    # Some models may output Soft-like status for Hard rules.
    if u in ("SILENT",):
        return "NA"
    if u in ("TRIGGER",):
        return "FAIL"

    # Common Chinese variants.
    if s in ("不适用", "无", "不涉及", "不相关", "未触发", "不触发"):
        return "NA"
    if s in ("通过", "合格", "满足", "是", "符合"):
        return "PASS"
    if s in ("不通过", "不合格", "不满足", "否", "不符合"):
        return "FAIL"

    if "PASS" in u and "FAIL" not in u:
        return "PASS"
    if "FAIL" in u and "PASS" not in u:
        return "FAIL"

    return u if u in ("PASS", "FAIL", "NA") else ""


def _extract_http_status_from_error(err: Optional[str]) -> Optional[int]:
    if not err:
        return None
    m = re.search(r"http=(?P<code>-?\d+)\b", str(err))
    if not m:
        return None
    try:
        return int(m.group("code"))
    except ValueError:
        return None


def _render_table_report(rule_results: List[Dict[str, Any]]) -> str:
    hard_fails = [r for r in rule_results if r.get("level") == "Hard" and str(r.get("status") or "").upper() == "FAIL"]
    blocked = "是" if len(hard_fails) > 0 else "否"

    lines: List[str] = []
    lines.append("# 审计报告")
    lines.append("")
    lines.append("## 摘要")
    lines.append(f"- 阻断提交：{blocked}")
    lines.append(f"- Hard FAIL：{len(hard_fails)}")
    lines.append("")

    lines.append("## 规则结果")
    lines.append("")
    lines.append("| 规则 | 结果 | 原因 |")
    lines.append("| --- | --- | --- |")

    for r in rule_results:
        rid = str(r.get("rule_id") or "").strip()
        status = str(r.get("status") or "").strip().upper()
        rule_cell = _escape_md_table_cell(rid)
        result_cell = _escape_md_table_cell(status)

        reason_cell = ""
        actionable = r.get("level") == "Hard" and status == "FAIL"
        if actionable:
            sev = str(r.get("severity") or "").strip()
            reason = str(r.get("reason") or "").strip()
            if sev and r.get("level") == "Hard":
                reason = f"{sev}：{reason}" if reason else sev
            reason_cell = _escape_md_table_cell(reason)

        lines.append(f"| {rule_cell} | {result_cell} | {reason_cell} |")

    lines.append("")
    return "\n".join(lines)


def run_llm_rule_audit(
    case_text: str,
    cfg: Optional[LLMConfig] = None,
    model: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    t0_total = time.perf_counter()

    wanted_order = list(RULE_ORDER)
    rules: List[RuleDefinition] = [RULE_DEFINITIONS[r] for r in wanted_order]

    max_workers_env = (os.getenv("LLM_RULE_MAX_WORKERS") or "").strip()
    try:
        max_workers = int(max_workers_env) if max_workers_env else len(rules)
    except ValueError:
        max_workers = len(rules)

    if max_workers < 1:
        max_workers = 1
    if max_workers > len(rules):
        max_workers = len(rules)

    if cfg is None:
        cfg = resolve_llm_config(model) if model else load_llm_config_from_env()

    client = OpenAICompatibleClient(cfg)

    json_mode_env = (os.getenv("LLM_JSON_MODE") or "1").strip().lower()
    use_json_mode = json_mode_env not in ("0", "false", "no", "off")

    json_repair_env = (os.getenv("LLM_JSON_REPAIR") or "1").strip().lower()
    use_json_repair = json_repair_env not in ("0", "false", "no", "off")

    max_in_flight_raw = (os.getenv("LLM_MAX_IN_FLIGHT") or "").strip()
    try:
        max_in_flight = int(max_in_flight_raw) if max_in_flight_raw else 2
    except ValueError:
        max_in_flight = 2
    if max_in_flight < 1:
        max_in_flight = 1
    inflight = threading.Semaphore(max_in_flight)

    results_by_id: Dict[str, Dict[str, Any]] = {}
    usage_by_id: Dict[str, Dict[str, Any]] = {}
    latency_s_by_id: Dict[str, float] = {}

    def _error_result(rule: RuleDefinition, err: str) -> Dict[str, Any]:
        msg = err.strip()
        if len(msg) > 400:
            msg = msg[:400]
        reason = f"规则审计失败：{msg}" if msg else "规则审计失败"
        return {
            "rule_id": rule.rule_id,
            "level": "Hard",
            "status": "FAIL",
            "severity": rule.severity,
            "reason": reason,
            "evidence": [],
        }

    def _one(rule: RuleDefinition) -> Tuple[str, Dict[str, Any], Dict[str, Any], float]:
        messages = _build_rule_agent_messages(rule, case_text)

        retries = 5
        retry_sleep_seconds = 2.0

        total_usage: Dict[str, Any] = {}
        total_elapsed_s = 0.0
        last_err: Optional[str] = None

        def _merge_usage(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                dst[k] = int(dst.get(k) or 0) + int(src.get(k) or 0)
            details = src.get("completion_tokens_details")
            if isinstance(details, dict):
                dst_details = dst.get("completion_tokens_details")
                if not isinstance(dst_details, dict):
                    dst_details = {}
                    dst["completion_tokens_details"] = dst_details
                dst_details["reasoning_tokens"] = int(dst_details.get("reasoning_tokens") or 0) + int(
                    details.get("reasoning_tokens") or 0
                )

        def _repair_json(raw_text: str) -> str:
            schema = (
                f'{{"rule_id":"{rule.rule_id}","level":"Hard","status":"PASS|FAIL|NA",'
                '"severity":"Major|Minor|Critical|null","reason":"string|null","evidence":["..."]}'
            )
            sys = "你是一个JSON修复器。你只输出严格JSON，不要输出任何解释、分析或Markdown代码块。"
            user = (
                "把下面这段模型输出转换为严格JSON对象。\n"
                f"要求：输出必须是单个 JSON 对象，字段与取值范围必须匹配：{schema}\n"
                "额外约束：\n"
                "- 若无法从原始输出判断 PASS/FAIL/NA：输出 FAIL。\n"
                "- NA/PASS 时：reason=null 且 evidence=[].\n"
                "- evidence 最多 3 条，每条不超过 80 字符。\n"
                "原始输出：\n"
                f"{(raw_text or '')[:8000]}"
            )

            with inflight:
                fixed, _, _ = client.chat_with_usage(
                    [{"role": "system", "content": sys}, {"role": "user", "content": user}],
                    json_mode=use_json_mode,
                )
            return fixed

        for attempt_idx in range(retries + 1):
            if attempt_idx > 0:
                sleep_s = retry_sleep_seconds
                status_code = _extract_http_status_from_error(last_err)
                if status_code == 429:
                    sleep_s = max(sleep_s, 8.0)
                time.sleep(sleep_s)

            try:
                with inflight:
                    raw, usage, call_elapsed_s = client.chat_with_usage(messages, json_mode=use_json_mode)
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                continue

            total_elapsed_s += float(call_elapsed_s or 0.0)
            if isinstance(usage, dict):
                _merge_usage(total_usage, usage)

            try:
                data = _extract_first_json_object(raw)
                if not isinstance(data, dict):
                    raise ValueError("Parsed JSON is not an object")
            except Exception as e:
                if not use_json_repair:
                    last_err = f"{type(e).__name__}: {e}"
                    continue
                try:
                    fixed = _repair_json(raw)
                    data = _extract_first_json_object(fixed)
                    if not isinstance(data, dict):
                        raise ValueError("Parsed JSON is not an object")
                except Exception as e2:
                    last_err = f"{type(e2).__name__}: {e2}"
                    continue

            status_raw = data.get("status")
            if status_raw is None:
                status_raw = data.get("result")

            status = _normalize_hard_status(status_raw)
            if status == "" and use_json_repair:
                try:
                    fixed2 = _repair_json(raw)
                    data2 = _extract_first_json_object(fixed2)
                    if isinstance(data2, dict):
                        data = data2
                        status_raw2 = data.get("status")
                        if status_raw2 is None:
                            status_raw2 = data.get("result")
                        status = _normalize_hard_status(status_raw2)
                except Exception:
                    pass

            if status == "":
                last_err = "Missing/invalid status for Hard rule"
                continue

            data["status"] = status

            if data.get("rule_id") != rule.rule_id:
                data["rule_id"] = rule.rule_id
            data["level"] = rule.level

            evidence = data.get("evidence")
            if evidence is None:
                evidence = data.get("evidences")
            if evidence is None:
                data["evidence"] = []
            elif isinstance(evidence, str):
                data["evidence"] = [evidence]
            elif not isinstance(evidence, list):
                data["evidence"] = [str(evidence)]

            reason = data.get("reason")
            if reason is None:
                reason = data.get("message")
            if reason is None:
                reason = data.get("why")
            if reason is None:
                reason = data.get("explanation")
            if reason is not None:
                reason = _sanitize_reason_text(str(reason))
                if reason == "":
                    reason = None
            data.pop("message", None)

            if rule.level == "Hard":
                if data.get("status") == "FAIL":
                    if data.get("severity") in (None, ""):
                        data["severity"] = rule.severity
                else:
                    data["severity"] = None

            actionable = data.get("status") == "FAIL"

            if actionable and reason is None and attempt_idx < retries:
                last_err = "Missing reason for actionable result"
                continue

            if actionable:
                data["reason"] = reason or "未提供原因"
            else:
                data["reason"] = None
                data["evidence"] = []

            return rule.rule_id, data, total_usage, total_elapsed_s

        return rule.rule_id, _error_result(rule, last_err or "规则审计失败"), total_usage, total_elapsed_s

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_rule = {ex.submit(_one, r): r for r in rules}
        for fut in as_completed(future_to_rule):
            rule = future_to_rule[fut]
            try:
                rid, data, usage, call_elapsed_s = fut.result()
            except Exception as e:
                rid, data, usage, call_elapsed_s = rule.rule_id, _error_result(rule, f"{type(e).__name__}: {e}"), {}, 0.0
            results_by_id[rid] = data
            usage_by_id[rid] = usage
            latency_s_by_id[rid] = float(call_elapsed_s)

    rule_results: List[Dict[str, Any]] = []
    for rid in wanted_order:
        data = results_by_id.get(rid)
        if data is None:
            data = _error_result(RULE_DEFINITIONS[rid], "Missing rule result")
        rule_results.append(data)

    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    reasoning_tokens = 0
    for u in usage_by_id.values():
        if not isinstance(u, dict):
            continue
        prompt_tokens += int(u.get("prompt_tokens") or 0)
        completion_tokens += int(u.get("completion_tokens") or 0)
        total_tokens += int(u.get("total_tokens") or 0)
        details = u.get("completion_tokens_details")
        if isinstance(details, dict):
            reasoning_tokens += int(details.get("reasoning_tokens") or 0)

    t1_total = time.perf_counter()
    elapsed_s = float(t1_total - t0_total)
    tokens_per_s = (float(total_tokens) / elapsed_s) if elapsed_s > 0 else None
    completion_tokens_per_s = (float(completion_tokens) / elapsed_s) if elapsed_s > 0 else None

    metrics: Dict[str, Any] = {
        "model": cfg.model,
        "elapsed_s": elapsed_s,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "tokens_per_s": tokens_per_s,
        "completion_tokens_per_s": completion_tokens_per_s,
    }

    report_md = _render_table_report(rule_results)
    return report_md, rule_results, metrics


def run_llm_single_prompt_audit(
    case_text: str,
    cfg: Optional[LLMConfig] = None,
    model: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    t0_total = time.perf_counter()

    wanted_order = list(RULE_ORDER)
    rules: List[RuleDefinition] = [RULE_DEFINITIONS[r] for r in wanted_order]

    if cfg is None:
        cfg = resolve_llm_config(model) if model else load_llm_config_from_env()

    client = OpenAICompatibleClient(cfg)

    json_mode_env = (os.getenv("LLM_JSON_MODE") or "1").strip().lower()
    use_json_mode = json_mode_env not in ("0", "false", "no", "off")

    json_repair_env = (os.getenv("LLM_JSON_REPAIR") or "1").strip().lower()
    use_json_repair = json_repair_env not in ("0", "false", "no", "off")

    def _error_result(rule: RuleDefinition, err: str) -> Dict[str, Any]:
        msg = (err or "").strip()
        if len(msg) > 400:
            msg = msg[:400]
        reason = f"规则审计失败：{msg}" if msg else "规则审计失败"
        return {
            "rule_id": rule.rule_id,
            "level": "Hard",
            "status": "FAIL",
            "severity": rule.severity,
            "reason": reason,
            "evidence": [],
        }

    def _repair_json(raw_text: str) -> str:
        schema_rule = (
            '{"rule_id":"H1|H2|H3|H4|H5|H6","level":"Hard","status":"PASS|FAIL|NA",'
            '"severity":"Major|Minor|Critical|null","reason":"string|null","evidence":["..."]}'
        )
        schema_top = f'{{"rule_results":[{schema_rule}, "..."]}}'
        sys = "你是一个JSON修复器。你只输出严格JSON，不要输出任何解释、分析或Markdown代码块。"
        user = (
            "把下面这段模型输出转换为严格JSON对象。\n"
            f"要求：输出必须是单个 JSON 对象，字段与取值范围必须匹配：{schema_top}\n"
            "额外约束：\n"
            "- 若无法从原始输出判断 PASS/FAIL/NA：输出 FAIL。\n"
            "- NA/PASS 时：reason=null 且 evidence=[].\n"
            "- evidence 最多 3 条，每条不超过 80 字符。\n"
            "原始输出：\n"
            f"{(raw_text or '')[:12000]}"
        )
        fixed, _, _ = client.chat_with_usage(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            json_mode=use_json_mode,
        )
        return fixed

    rule_text = "\n\n".join(COMPACT_RULE_TEXT.get(r.rule_id, r.definition).strip() for r in rules)
    schema_rule = (
        '{"rule_id":"H1|H2|H3|H4|H5|H6","level":"Hard","status":"PASS|FAIL|NA",'
        '"severity":"Major|Minor|Critical|null","reason":"string|null","evidence":["..."]}'
    )
    guide = (
        "Hard：不适用/未触发 -> NA；触发且满足 -> PASS；触发且缺失/不一致 -> FAIL。\n"
        "NA/PASS：severity=null, reason=null, evidence=[].\n"
        "FAIL：severity 必填(Major/Minor/Critical), reason 必填, evidence 从原文摘录(≤3条, 每条≤80字)。"
    )

    sys = (
        "你是门诊病历‘诊断证据完整性审计’系统。\n"
        "你需要一次性完成 H1-H6 六条 Hard 规则的判定。\n"
        "只输出严格 JSON 对象，禁止输出任何解释、分析或 Markdown。"
    )
    user = (
        "规则定义（H1-H6）：\n"
        f"{rule_text}\n\n"
        "病历文本：\n"
        f"{case_text}\n\n"
        f"{guide}\n"
        f"输出 JSON 必须匹配：{{\"rule_results\":[{schema_rule},\"...\"]}}"
    )

    usage_total: Dict[str, Any] = {}
    total_elapsed_s = 0.0

    try:
        raw, usage, call_elapsed_s = client.chat_with_usage(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            json_mode=use_json_mode,
        )
        total_elapsed_s += float(call_elapsed_s or 0.0)
        if isinstance(usage, dict):
            usage_total = dict(usage)
    except Exception as e:
        rule_results = [_error_result(r, f"{type(e).__name__}: {e}") for r in rules]
        report_md = _render_table_report(rule_results)
        metrics = {
            "model": cfg.model,
            "elapsed_s": float(time.perf_counter() - t0_total),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "tokens_per_s": None,
            "completion_tokens_per_s": None,
        }
        return report_md, rule_results, metrics

    try:
        data = _extract_first_json_object(raw)
        if not isinstance(data, dict):
            raise ValueError("Parsed JSON is not an object")
    except Exception as e:
        if not use_json_repair:
            rule_results = [_error_result(r, f"{type(e).__name__}: {e}") for r in rules]
            report_md = _render_table_report(rule_results)
            metrics = {
                "model": cfg.model,
                "elapsed_s": float(time.perf_counter() - t0_total),
                "prompt_tokens": int(usage_total.get("prompt_tokens") or 0),
                "completion_tokens": int(usage_total.get("completion_tokens") or 0),
                "reasoning_tokens": int((usage_total.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
                if isinstance(usage_total.get("completion_tokens_details"), dict)
                else 0,
                "total_tokens": int(usage_total.get("total_tokens") or 0),
                "tokens_per_s": None,
                "completion_tokens_per_s": None,
            }
            return report_md, rule_results, metrics

        try:
            fixed = _repair_json(raw)
            data = _extract_first_json_object(fixed)
            if not isinstance(data, dict):
                raise ValueError("Parsed JSON is not an object")
        except Exception as e2:
            rule_results = [_error_result(r, f"{type(e2).__name__}: {e2}") for r in rules]
            report_md = _render_table_report(rule_results)
            metrics = {
                "model": cfg.model,
                "elapsed_s": float(time.perf_counter() - t0_total),
                "prompt_tokens": int(usage_total.get("prompt_tokens") or 0),
                "completion_tokens": int(usage_total.get("completion_tokens") or 0),
                "reasoning_tokens": int((usage_total.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
                if isinstance(usage_total.get("completion_tokens_details"), dict)
                else 0,
                "total_tokens": int(usage_total.get("total_tokens") or 0),
                "tokens_per_s": None,
                "completion_tokens_per_s": None,
            }
            return report_md, rule_results, metrics

    rr = data.get("rule_results")
    if rr is None:
        rr = data.get("results")
    if rr is None:
        rr = data.get("rules")
    if not isinstance(rr, list):
        rr = []

    by_id: Dict[str, Dict[str, Any]] = {}
    for item in rr:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("rule_id") or "").strip()
        if rid not in wanted_order:
            continue

        status = _normalize_hard_status(item.get("status") if item.get("status") is not None else item.get("result"))
        if status == "":
            by_id[rid] = _error_result(RULE_DEFINITIONS[rid], "Missing/invalid status for Hard rule")
            continue

        item["rule_id"] = rid
        item["level"] = "Hard"
        item["status"] = status

        evidence = item.get("evidence")
        if evidence is None:
            evidence = item.get("evidences")
        if evidence is None:
            item["evidence"] = []
        elif isinstance(evidence, str):
            item["evidence"] = [evidence]
        elif not isinstance(evidence, list):
            item["evidence"] = [str(evidence)]

        reason = item.get("reason")
        if reason is None:
            reason = item.get("message")
        if reason is None:
            reason = item.get("why")
        if reason is None:
            reason = item.get("explanation")

        if reason is not None:
            reason = _sanitize_reason_text(str(reason))
            if reason == "":
                reason = None
        item.pop("message", None)

        if status == "FAIL":
            if item.get("severity") in (None, ""):
                item["severity"] = RULE_DEFINITIONS[rid].severity
            item["reason"] = reason or "未提供原因"
            item["evidence"] = [str(x)[:80] for x in (item.get("evidence") or [])][:3]
        else:
            item["severity"] = None
            item["reason"] = None
            item["evidence"] = []

        by_id[rid] = item

    rule_results: List[Dict[str, Any]] = []
    for rid in wanted_order:
        rule_results.append(by_id.get(rid) or _error_result(RULE_DEFINITIONS[rid], "Missing rule result"))

    prompt_tokens = int(usage_total.get("prompt_tokens") or 0)
    completion_tokens = int(usage_total.get("completion_tokens") or 0)
    total_tokens = int(usage_total.get("total_tokens") or 0)
    reasoning_tokens = 0
    details = usage_total.get("completion_tokens_details")
    if isinstance(details, dict):
        reasoning_tokens = int(details.get("reasoning_tokens") or 0)

    elapsed_s = float(time.perf_counter() - t0_total)
    tokens_per_s = (float(total_tokens) / elapsed_s) if elapsed_s > 0 else None
    completion_tokens_per_s = (float(completion_tokens) / elapsed_s) if elapsed_s > 0 else None

    metrics: Dict[str, Any] = {
        "model": cfg.model,
        "elapsed_s": elapsed_s,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "tokens_per_s": tokens_per_s,
        "completion_tokens_per_s": completion_tokens_per_s,
    }

    report_md = _render_table_report(rule_results)
    return report_md, rule_results, metrics
