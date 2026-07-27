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

ALLOWED_ROLES = {"admin", "editor", "viewer"}
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
    file_mb = max(1, min(500, int(raw.get("maxFileSizeMb", 100) or 100)))
    storage_gb = max(1, min(500, int(raw.get("maxLocalStorageGb", 10) or 10)))
    interval = max(60, min(3600, int(raw.get("pollIntervalSeconds", 300) or 300)))
    return {
        **DEFAULT_DESKTOP_SYNC_POLICY,
        "enabled": bool(raw.get("enabled", False)),
        "enabledByDefault": bool(raw.get("enabledByDefault", False)),
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
        "maxFileSizeBytes": file_mb * 1024 * 1024,
        "maxLocalStorageBytes": storage_gb * 1024 * 1024 * 1024,
        "pollIntervalSeconds": interval,
        "allowFolderSelection": bool(raw.get("allowFolderSelection", True)),
        "removeLocalFilesOnRevocation": bool(raw.get("removeLocalFilesOnRevocation", False)),
        "policyVersion": max(1, int(raw.get("policyVersion", 1) or 1)),
    }


def effective_desktop_sync_policy(value, user):
    policy = normalize_desktop_sync_policy(value)
    user_id = str(user.get("id") or "")
    role = str(user.get("role") or "")
    allowed = role in policy["allowedRoles"] or user_id in policy["allowedUserIds"]
    return {**policy, "enabledForCurrentUser": bool(policy["enabled"] and allowed)}
