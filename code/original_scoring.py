"""Snippet matching functions of the original evaluation, reproduced unchanged.

_normalize_for_contains          exact matching after whitespace removal
_evidence_item_in_text_lenient   lenient matching (punctuation removed; parts split at
                                 line breaks or '||'; contiguous match of at least 12
                                 characters covering at least 80% of the part)
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import List

def _normalize_for_contains(text: str) -> str:
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", "", s)


def _normalize_for_lenient_contains(text: str) -> str:
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    out_chars: List[str] = []
    for ch in s:
        if ch.isspace():
            continue
        if unicodedata.category(ch).startswith("P"):
            continue
        out_chars.append(ch)
    return "".join(out_chars)


def _split_evidence_parts(evidence_item: str) -> List[str]:
    s = str(evidence_item or "").strip()
    if not s:
        return []
    # Some models concatenate multiple snippets in a single evidence item.
    parts = re.split(r"\s*(?:\|\||｜｜)\s*", s)
    out: List[str] = []
    for part in parts:
        for ln in str(part).splitlines():
            t = ln.strip()
            if t:
                out.append(t)
    return out or [s]


def _loose_part_in_text(part: str, hay_lenient: str, min_lcs_ratio: float = 0.8) -> bool:
    ev = _normalize_for_lenient_contains(part)
    if not ev or not hay_lenient:
        return False
    if ev in hay_lenient:
        return True
    # For very short strings, fuzzy matching is too error-prone.
    if len(ev) < 12:
        return False
    sm = difflib.SequenceMatcher(None, ev, hay_lenient, autojunk=False)
    m = sm.find_longest_match(0, len(ev), 0, len(hay_lenient))
    if m.size < 12:
        return False
    return (float(m.size) / float(len(ev))) >= float(min_lcs_ratio)


def _evidence_item_in_text_lenient(evidence_item: str, hay_lenient: str) -> bool:
    parts = _split_evidence_parts(evidence_item)
    if not parts:
        return False
    return all(_loose_part_in_text(part, hay_lenient) for part in parts)


