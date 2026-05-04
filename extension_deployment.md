 # Oracle Backend + Chrome Extension Plan

  ## Summary

  Use the Oracle Ubuntu host as a small processing API only. Keep Grants.gov interaction in a Chrome extension running in the user’s own browser tab.

  Given your server and the repo’s current shape, the first version should:

  - accept uploads/jobs from a small internal user group
  - run PDF extraction, normalization, and validation on the Oracle box
  - store files in external object storage rather than local disk
  - return a manifest the extension can use to fill Grants.gov in the user’s authenticated session

  This avoids the current blockers for end users:

  - no Python install
  - no venv
  - no containers
  - no admin rights
  - no remote Chrome/CDP dependency on the user machine beyond the extension itself

  ## Implementation Changes

  - Split the current app into two runtimes:
      - backend service on Oracle for extract, normalize, validate, artifact generation, and job tracking
      - Chrome extension for Grants.gov page detection, form filling, attachment coordination, and user-visible progress
  - Treat the current Python scripts as the domain engine:
      - keep parsing/normalization logic from scripts/extract*.py, scripts/normalize*.py, scripts/validate.py
      - remove the current assumption that run.py is the product entrypoint
      - do not carry forward Playwright/CDP attach as the primary automation path
  - Replace local filesystem workflow with storage abstraction:
      - uploaded PDFs go to object storage
      - generated XML/manifests/reports/screenshots go to object storage
      - backend stores only metadata, job state, and object keys locally
  - Add a thin job model:
      - queued, running, failed, completed
      - one job per uploaded form batch
      - retain logs and validation output per job
  - Keep selector-profile JSON files as the source of truth for field mapping where possible, but rewrite browser actions from Playwright calls to extension DOM
    operations.

  ## Backend Design

  - Stack target for the Oracle host:
      - Python API service
      - background worker in the same codebase/process family
      - SQLite is acceptable for v1 at 1-5 internal users
      - object storage for input/output artifacts
  - Backend responsibilities:
      - issue pre-signed upload targets or accept direct uploads
      - enqueue extraction/normalization/validation jobs
      - persist manifest JSON, validation summaries, and artifact references
      - expose a stable manifest payload for the extension
  - Public API surface:
      - POST /api/jobs
      - GET /api/jobs/{id}
      - GET /api/jobs/{id}/manifest
      - GET /api/jobs/{id}/validation
      - GET /api/jobs/{id}/artifacts
  - Non-goals for v1:
      - no hosted browser automation
      - no multi-tenant production auth system
      - no permanent local disk archive on the Oracle VM
  - Oracle host ops assumptions:
      - run behind a reverse proxy
      - use systemd services
      - keep app data paths separate from code
      - use object storage credentials scoped to one bucket/prefix for this app

  ## Extension Design

  - Extension responsibilities:
      - authenticate to the backend or accept a per-user API token
      - detect which Grants.gov form is open
      - fetch the prepared manifest for the selected job
      - fill fields and coordinate attachment uploads in the current tab
      - show actionable errors when selectors drift or required files are missing
  - Extension constraints:
      - it is not extension-only; backend remains required
      - it should operate only on Grants.gov origins
      - it should not depend on native messaging or a local companion in this version

  ## Test Plan

  - Backend equivalence tests:
      - run sample Key Person, Budget, and Performance Site PDFs through the new API path
      - confirm manifest output matches current local-script output shape
      - confirm validation reports and generated artifacts are preserved
  - Extension integration tests:
      - fill each supported Grants.gov form from a prepared manifest
      - verify required attachments map correctly
      - verify user-facing handling for expired session, wrong page, missing artifact, and selector mismatch
  - Backend operational tests:
      - multiple queued jobs for 1-5 users
      - object storage upload/download lifecycle
      - job retry after worker failure
      - cleanup of stale local temp files
  - Acceptance criteria:
      - a user with only Chrome and extension access can upload documents, wait for processing, open Grants.gov, and complete autofill without any local Python setup

  ## Assumptions

  - The Oracle host is dedicated enough to run a small internal API and worker continuously.
  - First release targets a trusted internal group of 1-5 users.
  - External object storage is available and preferred over local disk retention.
  - SQLite is sufficient for v1; move to Postgres only if concurrency or operational needs grow.
  - Existing Python extraction/normalization code is worth preserving; only the automation runtime should be replaced.

  # Backend Bootstrap Plan

  ## Summary

  Build a small Ubuntu-hosted processing backend for the current pipeline, installed via a bootstrap shell script that sets up system packages, a Python venv, app
  directories, config files, and systemd services.

  This backend is for:

  - PDF extraction
  - normalization
  - validation
  - serving config/reference data
  - exposing job status and manifest APIs

  It is not for:

  - browser automation
  - long-term storage of uploads/results
  - multi-user auth beyond one shared API key
  - public TLS/reverse-proxy setup in v1

  Persistent server-side data will be limited to:

  - schemas/
  - config/ mappings and selector profiles
  - data/contacts.json
  - lightweight app/job metadata
  - service logs

  Uploads and generated artifacts will be ephemeral temp files only.

  ## Implementation Changes

  - Add a backend app structure separate from run.py and scripts/ui.py.
      - Keep the existing domain logic in scripts/extract*.py, scripts/normalize*.py, scripts/validate.py
      - Wrap those modules behind API endpoints and a small job runner
  - Add a bootstrap script that performs:
      - apt install of required system packages
      - creation of a dedicated app user
      - creation of app directories under a fixed root such as /opt/rrtard and /var/lib/rrtard
      - Python venv creation and dependency install
      - creation of a .env or config file with the shared API key and runtime paths
      - installation of systemd units for API and worker
      - initial schema bootstrap from repo-pinned files, not mandatory live download
  - Replace repo-relative write assumptions with runtime path configuration.
      - Current scripts assume directories like review/, audit/, input-pdfs/, extracted-*
      - Backend wrapper should map these to temp job workdirs under /var/tmp/rrtard or /var/lib/rrtard/tmp
      - Persistent reference data should come from configured runtime paths, not the repo root
  - Add a lightweight metadata store.
      - SQLite for jobs, timestamps, status, manifest location, validation summary, and error text
      - No blob/file payload storage in the DB
  - Add single-key API auth.
      - One shared key in config
      - Require it on all API routes except optional health endpoint
  - Bind API on plain HTTP for internal testing.
      - Listen on 0.0.0.0:<port> or the private interface
      - Add CORS only for the extension origin(s) used in testing

  ## Backend Interfaces

  - API endpoints:
      - GET /health
      - GET /config/reference
        Returns form versions, role mappings, selector profile metadata, and contacts summary if needed by the extension/admin tooling
      - POST /jobs/keyperson
      - POST /jobs/budget
      - POST /jobs/performance-site
        Accept uploaded PDFs and enqueue processing
      - GET /jobs/{id}
        Returns job state, timestamps, and error summary
      - GET /jobs/{id}/manifest
        Returns normalized manifest JSON
      - GET /jobs/{id}/validation
        Returns validation report summary and warnings/errors
  - Runtime directories:
      - persistent:
          - /var/lib/rrtard/config
          - /var/lib/rrtard/data
          - /var/lib/rrtard/schemas
          - /var/lib/rrtard/db
      - ephemeral:
          - /var/lib/rrtard/tmp/jobs/<job-id>/...
  - Bootstrap-installed system dependencies:
      - python3
      - python3-venv
      - python3-dev
      - build-essential
      - poppler-utils for pdftotext
      - qpdf and libqpdf-dev to avoid pikepdf runtime/build surprises on Ubuntu 20.04
      - any small helper tools required by the chosen API server
  - Python runtime:
      - venv-managed install from a backend requirements lock or requirements.txt
      - API server and worker run as separate systemd services
  - Service model:
      - rrtard-api.service
      - rrtard-worker.service
      - worker can be simple polling against SQLite in v1 rather than introducing Redis/Celery

  ## Test Plan

  - Bootstrap validation:
      - fresh Ubuntu 20.04 VM can run the script end-to-end without manual package or path fixes
      - both systemd services start cleanly
      - /health responds successfully with API key auth behavior as expected
  - Domain equivalence:
      - sample Key Person PDF batch produces same manifest shape as current local workflow
      - sample Budget PDF batch produces same manifest shape
      - sample Performance Site PDF batch produces same manifest shape
      - schema validation and warnings remain consistent with existing scripts
  - Filesystem behavior:
      - persistent refs exist after restart: schemas, config, contacts, SQLite DB
      - temp job directories are created during processing and removed after completion/failure cleanup
  - Auth and access:
      - requests without the shared API key are rejected
      - requests with the key succeed
      - API is reachable on the VM’s private HTTP address for extension testing
  - Failure cases:
      - missing contacts.json
      - missing schema files
      - malformed or unsupported PDF
      - pdftotext unavailable
      - worker restart during an in-flight job

  ## Assumptions

  - First release is internal-only and can use private HTTP without TLS.
  - A single shared API key is sufficient.
  - Uploaded PDFs and generated outputs do not need to persist after job completion.
  - Server-side persistence is limited to schemas, mapping/config files, contacts.json, and SQLite metadata.
  - Existing Python extraction/normalization/validation code will be reused rather than rewritten now.
  - The bootstrap script should target repeatable setup on Ubuntu 20.04 with systemd + venv, not containers.


