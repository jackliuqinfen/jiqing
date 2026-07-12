# Lifecycle Runtime Foundation Acceptance Report

Date: 2026-07-12

## Release scope

This release establishes the first protected lifecycle runtime foundation. It does not claim to deliver the complete configurable form/workflow engine described in the long-term design.

Included:

- fixed protected project lifecycle policy and stage gates;
- versioned, idempotent lifecycle transitions and immutable event records;
- migration checksum and concurrency protection;
- lifecycle snapshot, validation, and transition APIs;
- direct project-status write protection;
- audit-start stage and submitted-amount gates;
- desktop and mobile lifecycle status/transition UI;
- structured audit-start errors and partial-safe batch audit initiation;
- settlement wizard acceptance/audit ordering gate;
- design and implementation planning documents.

Excluded from this release:

- full configurable stage-form and visual workflow administration;
- AI document recognition;
- stage-aware document-directory templates and inherited per-project overrides.

## Automated acceptance

### Backend

Command:

```text
python -m unittest discover -s server/tests -v
```

Result: `50` tests passed, `0` failures, exit code `0`.

Covered acceptance paths include:

- a valid `awarded -> contract_signed` transition;
- idempotent replay returning the original event without a duplicate event row;
- missing contract facts/current contract attachment returning `422` blockers;
- stale lifecycle version returning `409` with current version metadata;
- direct project-status update returning `422`;
- audit start before `pending_submission` returning `422`;
- audit start requiring a positive submitted amount;
- anonymous audit reads returning `401`;
- partial project updates preserving project data and audit linkage;
- concurrent audit-start requests creating only one audit record;
- audit progress rejecting stage skips and synchronizing the project lifecycle;
- settlement facts being rejected when they exceed the project lifecycle;
- migration checksum, retry, rollback, and idempotency behavior.

Command:

```text
python -m py_compile server/audit_api.py server/lifecycle.py server/lifecycle_repository.py server/migrations.py
```

Result: exit code `0`.

Windows-specific verification also confirmed that API contract tests release SQLite file handles after completion. The connection context now commits or rolls back and always closes the connection.

### Frontend

Command:

```text
node --experimental-strip-types --test test/auditEligibility.test.ts test/task4bLifecycleSafety.test.ts
```

Result: `6` tests passed, `0` failures, exit code `0`.

The focused tests cover:

- audit-start candidate eligibility and skipped reasons;
- omission of backend-managed lifecycle/audit linkage fields from normal edits;
- fixed lifecycle defaults for normal project creation;
- preservation of all loaded mobile pages during lifecycle refresh;
- lifecycle snapshot refresh remaining independent from ancillary refresh failures.

Command:

```text
npm.cmd run build
```

Result: exit code `0`; `vue-tsc` passed and Vite transformed `3411` modules. Two known non-fatal Arco bundled-CSS minifier warnings remain for `-scroll-position-right` and `-scroll-position-left`.

## Browser acceptance

An isolated local database and authenticated QA session were used. No production data was read or changed, and no sample project data is shipped in the product.

Verified on desktop:

- an empty database renders a true empty state;
- normal project creation fixes the initial stage to `已中标` and does not ask audit questions;
- the project detail shows current stage `已中标`, lifecycle version `0`, and backend-provided next stage `已签订合同`;
- transition validation displays the two real blockers: positive contract amount and current contract attachment;
- confirmation is disabled while blockers exist;
- audit linkage is not created automatically.

Verified at a `390 x 844` mobile viewport:

- the dedicated mobile project route loads after authentication;
- project status is read-only and cannot be edited through the normal project update form;
- the same lifecycle status and transition modal are available;
- backend blockers are displayed and confirmation remains disabled;
- settlement status remains independently editable.

No browser console errors were observed in the checked desktop and mobile paths.

## Known residual issue

The legacy project document-category model still marks globally required categories as missing regardless of project stage. In the QA project at `已中标`, future categories such as first-audit and second-audit materials were still counted in the missing-document total.

This does not bypass the new lifecycle API gates, but it does not satisfy the long-term rule that future-stage documents must not count as missing. It must be addressed by the stage-aware document-template/configuration work rather than by inventing a hard-coded category-stage mapping in this foundation release.

## Release scope guard

Only lifecycle, settlement-gate, related frontend, test, and design/acceptance files should be staged. The following local paths are unrelated or generated and must remain uncommitted:

- `.superpowers/`
- `design-audits/`
- `reports/`
- `review_results.json`
