"""Stage-aware project document requirement policy."""

from server.lifecycle import STAGE_ORDER


DEFAULT_REQUIRED_FROM_STAGE = {
    "contract": "contract_signed",
    "drawing": "under_construction",
    "settlement_book": "pending_submission",
    "visa_change": "pending_submission",
    "first_audit": "first_audit",
    "second_audit": "second_audit",
    "payment": "conclusion",
    "other": "archived",
}

_STAGE_RANK = {stage: index for index, stage in enumerate(STAGE_ORDER)}


def default_required_from_stage(category_key):
    """Return the conservative default start stage for a document category."""
    return DEFAULT_REQUIRED_FROM_STAGE.get(category_key, STAGE_ORDER[0])


def normalize_required_from_stage(category_key, configured_stage):
    """Return a valid stage without allowing an unknown value into policy checks."""
    if configured_stage in _STAGE_RANK:
        return configured_stage
    return default_required_from_stage(category_key)


def applicable_required_categories(categories, project_stage):
    """Return enabled required categories that apply at ``project_stage``."""
    current_rank = _STAGE_RANK.get(project_stage)
    if current_rank is None:
        return []

    applicable = []
    for category in categories:
        if not _value(category, "enabled", True) or not _value(category, "required", False):
            continue
        category_key = _value(category, "category_key", "")
        required_from_stage = normalize_required_from_stage(
            category_key,
            _value(category, "required_from_stage", ""),
        )
        if _STAGE_RANK[required_from_stage] <= current_rank:
            applicable.append(category)
    return applicable


def _value(record, key, default=None):
    if hasattr(record, "keys") and key in record.keys():
        return record[key]
    if isinstance(record, dict):
        return record.get(key, default)
    return default
