# Attachment Acceptance Report

Date: 2026-06-28

Target: production deployment at `http://121.4.36.112:8088`

## Result

Attachment capability passed the production API acceptance matrix after deploying commit `031e94f`.

## Verified

- `admin/admin` login is rejected with `401`.
- Valid admin login succeeds without exposing the token in logs.
- Audit project list is available for selecting a project under authenticated access.
- Text upload returns `201`, appears in the attachment list, previews as `text/plain`, downloads with the expected file content, and deletes successfully.
- PNG upload returns `201`, appears in the attachment list, and previews as `image/png`.
- PDF upload returns `201`, appears in the attachment list, and previews as `application/pdf`.
- Unknown binary upload returns `201`, appears in the attachment list, and preview is rejected with `415`.
- Unauthenticated preview is blocked with `401`.
- ZIP upload is rejected with `400`.
- Path-like filename upload such as `../name.txt` is rejected with `400`.
- All test attachments were deleted after the run.
- Server-side file scan found no `codex-attachment-check-*` leftovers under upload storage.

## Production Storage Check

- Upload root checked: `/data/jiqing-engineering/uploads`
- Temporary test leftovers: none found.
- Upload directory size after cleanup: `12K`
- Disk check: root filesystem `60G`, used `4.8G`, available `56G`.

## Notes

- A pre-deployment test exposed response-finalization timeouts on binary preview responses. Commit `031e94f` adds socket timeout handling and closes API/file responses explicitly; the production rerun confirmed image and PDF preview responses now complete normally.
- Office online preview remains out of scope. Office and unknown file types should use the download fallback.
