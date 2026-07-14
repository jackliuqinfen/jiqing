"""Typed, source-preserving normalization for recognized lifecycle facts."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .schemas import schema_for_version


_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "壹": 1,
    "二": 2,
    "贰": 2,
    "两": 2,
    "三": 3,
    "叁": 3,
    "四": 4,
    "肆": 4,
    "五": 5,
    "伍": 5,
    "六": 6,
    "陆": 6,
    "七": 7,
    "柒": 7,
    "八": 8,
    "捌": 8,
    "九": 9,
    "玖": 9,
}
_SMALL_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
_SECTION_UNITS = {"万": 10000, "萬": 10000, "亿": 100000000, "億": 100000000}


def normalize_extracted_fields(fields, schema_version):
    schema = schema_for_version(schema_version)
    normalized = []
    for field in fields:
        semantic_key = str(_get(field, "semantic_key") or "").strip()
        if semantic_key not in schema.field_types:
            raise ValueError(
                f"semantic key {semantic_key!r} is not part of {schema.version}"
            )
        raw_value = str(_get(field, "raw_value") or "")
        try:
            normalized_value = _normalize_value(
                raw_value, schema.field_types[semantic_key]
            )
            validation_status = "valid"
            validation_errors = []
        except (ValueError, InvalidOperation):
            normalized_value = None
            validation_status = "invalid"
            validation_errors = ["field_normalization_failed"]
        normalized.append(
            {
                "semantic_key": semantic_key,
                "raw_value": raw_value,
                "normalized_value": normalized_value,
                "confidence": _get(field, "confidence"),
                "anchors": tuple(_get(field, "anchors") or ()),
                "source_kind": str(_get(field, "source_kind") or "ocr"),
                "validation_status": validation_status,
                "validation_errors": validation_errors,
            }
        )
    return normalized


def materialize_schema_fields(fields, schema_version):
    """Add empty review rows for schema fields omitted by the OCR provider."""
    schema = schema_for_version(schema_version)
    by_key = {field["semantic_key"]: field for field in fields}
    materialized = []
    for semantic_key in schema.field_types:
        field = by_key.get(semantic_key)
        if field is not None:
            materialized.append(field)
            continue
        materialized.append(
            {
                "semantic_key": semantic_key,
                "raw_value": "",
                "normalized_value": None,
                "confidence": None,
                "anchors": (),
                "source_kind": "manual",
                "validation_status": "valid",
                "validation_errors": [],
            }
        )
    return materialized


def normalize_money_to_fen(value):
    text = _compact(value)
    if not text:
        raise ValueError("empty money")
    if any(character in _CHINESE_DIGITS for character in text):
        return _chinese_money_to_fen(text)
    cleaned = (
        text.replace("人民币", "")
        .replace("RMB", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace(",", "")
    )
    multiplier = Decimal("100")
    if "万元" in cleaned or cleaned.endswith("万"):
        multiplier *= Decimal("10000")
    number_match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
    if not number_match:
        raise ValueError("invalid money")
    fen = Decimal(number_match.group(0)) * multiplier
    if fen != fen.to_integral_value():
        raise ValueError("money has sub-fen precision")
    return int(fen)


def normalize_date(value):
    text = str(value or "").strip()
    match = re.search(
        r"(?P<year>\d{4})\s*(?:年|[-./／])\s*(?P<month>\d{1,2})\s*(?:月|[-./／])\s*(?P<day>\d{1,2})\s*日?",
        text,
    )
    if not match:
        raise ValueError("invalid date")
    year, month, day = (int(match.group(name)) for name in ("year", "month", "day"))
    import datetime

    parsed = datetime.date(year, month, day)
    return parsed.isoformat()


def normalize_percentage(value):
    text = _compact(value).replace("％", "%")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        raise ValueError("invalid percentage")
    result = Decimal(match.group(0))
    if "%" in text:
        result /= Decimal("100")
    if result < 0:
        raise ValueError("negative percentage")
    return _decimal_text(result)


def _normalize_value(raw_value, field_type):
    if field_type in {"money", "money_uppercase"}:
        return normalize_money_to_fen(raw_value)
    if field_type == "date":
        return normalize_date(raw_value)
    if field_type == "percentage":
        return normalize_percentage(raw_value)
    if field_type == "clauses":
        paragraphs = [line.strip() for line in str(raw_value).splitlines() if line.strip()]
        if not paragraphs:
            raise ValueError("empty clauses")
        return paragraphs
    text = str(raw_value or "").strip()
    if not text:
        raise ValueError("empty text")
    return text


def _chinese_money_to_fen(value):
    text = _compact(value).replace("人民币", "").replace("圆", "元")
    text = text.replace("整", "").replace("正", "")
    if "元" in text:
        integer_text, fraction_text = text.split("元", 1)
    else:
        integer_text, fraction_text = text, ""
    yuan = _chinese_integer(integer_text) if integer_text else 0
    jiao = _digit_before_unit(fraction_text, "角")
    fen = _digit_before_unit(fraction_text, "分")
    return yuan * 100 + jiao * 10 + fen


def _chinese_integer(value):
    total = 0
    section = 0
    number = 0
    seen = False
    for character in value:
        if character in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[character]
            seen = True
        elif character in _SMALL_UNITS:
            unit = _SMALL_UNITS[character]
            section += (number or 1) * unit
            number = 0
            seen = True
        elif character in _SECTION_UNITS:
            section += number
            total += section * _SECTION_UNITS[character]
            section = 0
            number = 0
            seen = True
    if not seen:
        raise ValueError("invalid uppercase money")
    return total + section + number


def _digit_before_unit(value, unit):
    index = value.find(unit)
    if index <= 0:
        return 0
    return _CHINESE_DIGITS.get(value[index - 1], 0)


def _compact(value):
    return re.sub(r"\s+", "", str(value or ""))


def _decimal_text(value):
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", ""} else text


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
