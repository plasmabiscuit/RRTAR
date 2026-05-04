# Chrome Extension

This directory is the v1 Chrome extension workspace for Grants.gov-side automation.

Why it lives at the project root:

- the Oracle VM is backend-only in the current deployment plan
- the browser automation runtime needs to be packaged independently from the Python app
- keeping it buildless for v1 makes it easy to load unpacked in Chrome during backend bring-up

## Layout

- `manifest.json`: extension manifest
- `src/background.js`: backend API access and extension-wide message handling
- `src/content.js`: Grants.gov page detection and automation dispatch
- `src/forms/`: per-form automation modules
- `src/popup.*`: operator UI for choosing a job and triggering autofill
- `src/options.*`: backend URL and API key settings

## Current backend assumption

Default backend URL:

- `http://100.117.80.82:8081`

That is the Tailscale address provided for the Oracle VM. The extension stores this value in Chrome storage and allows it to be changed in the options page.

## Load in Chrome

1. Open `chrome://extensions`
2. Enable Developer mode
3. Click `Load unpacked`
4. Select this `chrome-extension/` directory

## Current scope

This scaffold is intentionally thin:

- detects supported Grants.gov forms by iframe URL pattern
- fetches manifests from the backend
- provides popup/options plumbing
- defines per-form modules where the current Playwright logic can be ported

It does not yet fully replace the existing Playwright fillers. The next implementation step is porting the DOM-write logic from:

- `scripts/automate.py`
- `scripts/automate_budget.py`
- `scripts/automate_performance_site.py`

## Important deployment caveat

The repo does not yet contain the `backend/` package referenced by the bootstrap examples. If the VM bootstrap was run with:

- `backend.main:app`
- `backend.worker`

then the systemd services will fail until those modules are added.
