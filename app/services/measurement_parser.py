"""
Best-effort parser that turns OCR'd lab-report text into structured
measurement rows (test name / value / unit / reference range).

OCR table output is messy and inconsistent across labs — this is
intentionally conservative: it only emits a row when a line clearly
matches "Name  Value  Unit  (Ref-Range)" on ONE line. Multi-line or
multi-column table layouts that OCR mangles will be skipped rather than
guessed at. This is genuinely a partial solution, not a full table parser
— flagged here rather than pretending otherwise.
"""

import re

_LINE_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 /\-\(\)]{2,40}?)\s{1,}"
    r"(?P<value>-?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>[a-zA-Zµ%/0-9]{0,12})?\s*"
    r"(?:\(?\s*(?P<ref_min>-?\d+(?:\.\d+)?)\s*[-–to]{1,3}\s*(?P<ref_max>-?\d+(?:\.\d+)?)\s*\)?)?\s*$"
)


def parse_measurements(text: str) -> list[dict]:
    results: list[dict] = []
    if not text:
        return results

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or len(line) < 4:
            continue

        match = _LINE_PATTERN.match(line)
        if not match:
            continue

        name = match.group("name").strip()
        if len(name) < 2:
            continue

        try:
            value_numeric = float(match.group("value"))
        except (TypeError, ValueError):
            continue

        unit = (match.group("unit") or "").strip() or None
        ref_min_raw = match.group("ref_min")
        ref_max_raw = match.group("ref_max")
        ref_min = float(ref_min_raw) if ref_min_raw else None
        ref_max = float(ref_max_raw) if ref_max_raw else None

        entry = {
            "test_name": name,
            "value_numeric": value_numeric,
            "unit": unit,
            "reference_min": ref_min,
            "reference_max": ref_max,
        }

        if ref_min is not None and ref_max is not None:
            if value_numeric < ref_min:
                entry["abnormal_flag"] = "low"
            elif value_numeric > ref_max:
                entry["abnormal_flag"] = "high"
            else:
                entry["abnormal_flag"] = "normal"

        results.append(entry)

    return results