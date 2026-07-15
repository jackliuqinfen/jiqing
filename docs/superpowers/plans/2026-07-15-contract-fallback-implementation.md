# Contract Fallback Implementation Plan

**Goal:** Provide safe system OCR, external AI Markdown, and manual contract-intake paths without bypassing document review or creating fabricated project data.

**Architecture:** The immutable contract version plus `DocumentReviewWorkspace` remains the only formal project-creation path. External and manual values are suggestions with explicit source markers. Work without a stored contract is owner-scoped draft data only.

## Completed Work

- [x] Add versioned `project_intake_drafts` storage and recognition fallback provenance columns.
- [x] Keep SQLite and PostgreSQL canonical schemas in parity.
- [x] Parse exactly one fenced JSON block with `contract.v1` semantic-key whitelist.
- [x] Reject duplicate JSON keys, non-finite numbers, unknown fields, malformed payloads and oversized input.
- [x] Create manual/external review-ready jobs without synthetic OCR blocks, coordinates or confidence.
- [x] Persist `source_recognition_job_id`, fallback reason and fallback note.
- [x] Add owner-scoped draft create/list/read/save/abandon APIs.
- [x] Validate document ownership before a draft can attach a document version.
- [x] Allow a draft to be marked completed only with an existing, accessible formal project.
- [x] Add proactive version-level and failed-job-level manual/external review routes.
- [x] Add a three-path contract-intake chooser using the existing Arco-compatible UI.
- [x] Add fixed prompt copy, external Markdown paste and strict backend import.
- [x] Add fileless manual drafts, upload-failure draft preservation, recent-draft resume and abandon.
- [x] Route every file-backed path into the existing human review workspace.
- [x] Keep critical fields individually confirmed and use source-specific modification reasons.
- [x] Prevent polling network errors from using a running recognition job as a failed-job fallback source.
- [x] Add backend contract, permission, provenance, isolation and no-fake-project tests.
- [x] Add frontend utility tests and production TypeScript build verification.

## Release Verification

- [x] Backend unit/integration suite passes.
- [x] Frontend Node tests pass.
- [x] Vue type-check and Vite production build pass.
- [x] `git diff --check` passes.
- [ ] Deploy committed tracked files to production.
- [ ] Verify database migration, service health and public application load.
- [ ] Run authenticated production walk-through with a real contract: external AI import, manual draft resume and formal confirmation.

## Non-Negotiable Boundaries

- No stored contract means no formal project, project code, contract fact or lifecycle event.
- External AI output is never trusted as confirmed business data.
- Parsed Markdown is not persisted as a raw third-party response; only validated semantic values and provenance are stored.
- Existing contract confirmation remains the atomic formal project-creation boundary.
- No sample business records or synthetic OCR evidence are introduced.
