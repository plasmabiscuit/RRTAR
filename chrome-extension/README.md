# Chrome Extension

This directory is the browser-native RRTAR workspace for Grants.gov-side automation.

Why it lives at the project root:

- the dashboard and autofill runtime now live entirely inside Chrome
- the browser automation runtime needs to be packaged independently from the Python app
- keeping it buildless makes it easy to load unpacked during rapid iteration

## Layout

- `manifest.json`: extension manifest
- `src/background.js`: extension-wide state, file storage, and message handling
- `src/content.js`: Grants.gov page detection and automation dispatch
- `src/forms/`: per-form automation modules
- `src/dashboard.*`: full-page clientside dashboard
- `src/popup.*`: thin execution UI for detect/open-dashboard/autofill
- `src/options.*`: minimal extension info page

## Load in Chrome

1. Open `chrome://extensions`
2. Enable Developer mode
3. Click `Load unpacked`
4. Select this `chrome-extension/` directory

## Current scope

Current v1 behavior:

- detects supported Grants.gov forms by iframe URL pattern
- provides a full-page dashboard inside the extension for managing manifests and uploaded files
- keeps the popup as a thin execution surface
- previews the detected form and current stored manifest summary in the popup
- hard-blocks autofill when the loaded manifest form does not match the detected Grants.gov form
- fills the current form without clicking Grants.gov Save
- uploads supported attachments from clientside files stored by the extension

The form fillers are now browser-side ports of:

- `scripts/automate.py`
- `scripts/automate_budget.py`
- `scripts/automate_performance_site.py`

Known v1 constraints:

- PDF parsing/normalization has not been ported yet; manifests are currently imported as JSON
- the extension dashboard is the source of truth for manifest editing and pipeline state
- no auto-save is performed after fill
