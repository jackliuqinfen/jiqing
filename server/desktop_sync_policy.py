DEFAULT_DESKTOP_SYNC_POLICY = {
    "enabled": False,
    "enabledByDefault": False,
    "allowedRoles": ["admin"],
    "allowedUserIds": [],
    "projectSelectionMode": "user_select",
    "allowedProjectRefs": [],
    "allowedCategoryKeys": [],
    "allowedExtensions": [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".jpg", ".jpeg", ".png", ".webp", ".txt",
    ],
    "maxFileSizeBytes": 100 * 1024 * 1024,
    "maxLocalStorageBytes": 10 * 1024 * 1024 * 1024,
    "pollIntervalSeconds": 300,
    "allowFolderSelection": True,
    "removeLocalFilesOnRevocation": False,
    "policyVersion": 1,
}

ALLOWED_ROLES = {"admin"}
ALLOWED_PROJECT_MODES = {"user_select", "admin_assigned"}


def _unique_strings(values):
    result = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _trusted_bool(value, default):
    return value if isinstance(value, bool) else default


def _bounded_int(value, default, minimum, maximum):
    if isinstance(value, bool):
        return default
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(maximum, normalized))


def _normalized_size_bytes(raw, display_key, bytes_key, default_bytes, maximum_bytes, unit_bytes):
    if display_key in raw:
        return _bounded_int(
            raw.get(display_key),
            default_bytes // unit_bytes,
            1,
            maximum_bytes // unit_bytes,
        ) * unit_bytes
    if bytes_key in raw:
        return _bounded_int(raw.get(bytes_key), default_bytes, unit_bytes, maximum_bytes)
    return default_bytes


def normalize_desktop_sync_policy(value):
    raw = value if isinstance(value, dict) else {}
    roles = [role for role in _unique_strings(raw.get("allowedRoles")) if role in ALLOWED_ROLES]
    extensions = []
    for item in _unique_strings(raw.get("allowedExtensions")):
        suffix = item.lower()
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        if suffix[1:].isalnum() and suffix not in extensions:
            extensions.append(suffix)
    max_file_size_bytes = _normalized_size_bytes(
        raw,
        "maxFileSizeMb",
        "maxFileSizeBytes",
        100 * 1024 * 1024,
        500 * 1024 * 1024,
        1024 * 1024,
    )
    max_local_storage_bytes = _normalized_size_bytes(
        raw,
        "maxLocalStorageGb",
        "maxLocalStorageBytes",
        10 * 1024 * 1024 * 1024,
        500 * 1024 * 1024 * 1024,
        1024 * 1024 * 1024,
    )
    return {
        **DEFAULT_DESKTOP_SYNC_POLICY,
        "enabled": _trusted_bool(raw.get("enabled"), False),
        "enabledByDefault": _trusted_bool(raw.get("enabledByDefault"), False),
        "allowedRoles": roles or ["admin"],
        "allowedUserIds": _unique_strings(raw.get("allowedUserIds")),
        "projectSelectionMode": (
            raw.get("projectSelectionMode")
            if raw.get("projectSelectionMode") in ALLOWED_PROJECT_MODES
            else "user_select"
        ),
        "allowedProjectRefs": _unique_strings(raw.get("allowedProjectRefs")),
        "allowedCategoryKeys": _unique_strings(raw.get("allowedCategoryKeys")),
        "allowedExtensions": extensions or list(DEFAULT_DESKTOP_SYNC_POLICY["allowedExtensions"]),
        "maxFileSizeBytes": max_file_size_bytes,
        "maxLocalStorageBytes": max_local_storage_bytes,
        "pollIntervalSeconds": _bounded_int(raw.get("pollIntervalSeconds"), 300, 60, 3600),
        "allowFolderSelection": _trusted_bool(raw.get("allowFolderSelection"), True),
        # The desktop client does not yet have a root-bound selective purge.
        # Keep the compatibility field fail-closed instead of promising remote recall.
        "removeLocalFilesOnRevocation": False,
        "policyVersion": _bounded_int(raw.get("policyVersion"), 1, 1, 2 ** 31 - 1),
    }


def effective_desktop_sync_policy(value, user):
    policy = normalize_desktop_sync_policy(value)
    user_id = str(user.get("id") or "")
    role = str(user.get("role") or "")
    allowed = role == "admin" or (
        user_id in policy["allowedUserIds"]
        and policy["projectSelectionMode"] == "admin_assigned"
    )
    return {**policy, "enabledForCurrentUser": bool(policy["enabled"] and allowed)}
