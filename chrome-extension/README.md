# Chrome Extension

This directory is the browser-native RRTAR Dashboard for Grants.gov-side automation.

How it works:

- the dashboard and autofill runtimes operate entirely inside Chrome
- the browser runtimes are packaged independently from the Python process that run server-side
- Updating the extension is only necessary for UI changes; backend changes are automatically pushed to the server. 

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
5. Click on the icon to open the popup, then select the settings icon.
6. On this screen you will enter the backend url if not present (https://150.230.162.179.sslip.io)
7. Add the contents of API-key.txt that was provided to you in the API Key input.

If you need to request an API-key, please email cabates@tntech.edu 

## Current scope

Current v1 behavior:

- detects supported Grants.gov forms by iframe URL pattern
- provides a full-page dashboard inside the extension for managing manifests and uploaded files
- bundles `contacts.json` inside the extension and can append Key Person entries directly from local contact search
- keeps the popup as a thin execution surface
- previews the detected form and current stored manifest summary in the popup
- hard-blocks autofill when the loaded manifest form does not match the detected Grants.gov form
- fills the current form without clicking Grants.gov Save
- uploads supported attachments from clientside files stored by the extension

The form fillers are browser-side ports of:

- `scripts/automate.py`
- `scripts/automate_budget.py`
- `scripts/automate_performance_site.py`

This project is still in development. Double check any automated inputs before saving. 

## Known Constraints

- Budgets currently do not enter dates for project periods
- There will be an unused personnel in each period due that will need to be removed due to the default behavior of the webforms. Use this as an oportunity to confirm the accuracy of the manifest/automate step for each period. 
