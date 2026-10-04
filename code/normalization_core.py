"""Citation-format categories used for format-normalized evidence locatability.

Snippets and records are compared after whitespace removal, without case folding.
A snippet is
  verbatim        a substring of the record;
  field_prefix    a substring after removing a leading label of at most 12 characters
                  followed by a full- or half-width colon;
  ellipsis_join   two or more parts separated by an ellipsis, each a substring of the
                  record (optionally after label removal);
  non_locatable   otherwise.
The primary categorizer does not check that a label is a record field or that joined
parts occur in source order; categorize_strict adds both checks.
"""
import json
import re

PREFIX = re.compile(r"^[^:：]{1,12}[:：](.+)$")
RECOVERABLE = {"verbatim", "field_prefix", "ellipsis_join"}


def ws(text):
    return re.sub(r"\s+", "", text)


def categorize(snip, text):
    s = ws(snip)
    if not s:
        return "empty"
    if s in text:
        return "verbatim"
    match = PREFIX.match(s)
    if match and match.group(1) in text:
        return "field_prefix"
    parts = [p for p in re.split(r"…+|\.{3,}|⋯+", s) if p]
    ok = []
    for part in parts:
        match = PREFIX.match(part)
        ok.append(part in text or bool(match and match.group(1) in text))
    if len(parts) > 1 and all(ok):
        return "ellipsis_join"
    return "non_locatable"


def categorize_strict(snip, text, allowed_prefixes):
    """Stricter variant: whitelisted record headings and ordered, non-overlapping parts."""
    s = ws(snip)
    if not s:
        return "empty"
    if s in text:
        return "verbatim"

    def alternatives(part):
        options = [part]
        match = PREFIX.match(part)
        if match:
            prefix = re.split(r"[:：]", part, maxsplit=1)[0]
            if prefix in allowed_prefixes:
                options.append(match.group(1))
        return options

    options = alternatives(s)
    if len(options) > 1 and options[1] in text:
        return "field_prefix"
    parts = [p for p in re.split(r"…+|\.{3,}|⋯+", s) if p]
    if len(parts) < 2:
        return "non_locatable"
    cursor = 0
    for part in parts:
        ends = []
        for candidate in alternatives(part):
            start = text.find(candidate, cursor)
            if start >= 0:
                ends.append(start + len(candidate))
        if not ends:
            return "non_locatable"
        cursor = min(ends)
    return "ellipsis_join"


def snippets(result):
    return [item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            for item in (result.get("evidence") or [])]
