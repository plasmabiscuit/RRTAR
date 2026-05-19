# R&RTAR Chrome Extension

This extension is a browser-native RRTAR Dashboard for Grants.gov-side automation.

How it works:

- the dashboard and autofill runtimes operate entirely inside Chrome
- the browser runtimes keep files in local storage while sending requests to an Oracle vm for various Python doc processing sripts.
- Schemas are fetched from the grants.gov document repository for up to date mappings.
-  Data from documents sent server-side are never saved; the client sends a blob as a request and the manifest is sent back.  
- Updating the extension is only necessary for Automation and UI changes; backend changes are automatically pushed to the server. 

## Layout

- `manifest.json`: extension manifest
- `src/background.js`: extension-wide state, file storage, and message handling
- `src/content.js`: Grants.gov page detection and automated entry
- `src/forms/`: per-form automation 
- `src/dashboard.*`: full-page clientside dashboard
- `src/popup.*`: thin execution UI for detect/open-dashboard/autofill
- `src/options.*`: minimal extension settings page

## Load in Chrome

1. Open `chrome://extensions`
2. Enable Developer mode by clicking the Developer mode toggle switch in the top-right corner of the Extensions menu.
3. Click `Load unpacked`
4. Select the `chrome-extension/` directory from the extracted .zip
5. Click on the icon to open the popup, then select the settings icon.
6. On this screen you will enter the backend url if not present (autofilled by default)
7. Add the contents of API-key.txt that was provided to you in the API Key input.

If you need to request an API-key, please email Caleb Bates in Sponsored Programs 

## Current Build

Current v0.1 behavior:

- detects supported Grants.gov forms by iframe URL pattern for RR Key Person, Prime/Sub Budget, and Performance Site forms
- provides a full-page dashboard inside the extension for managing manifests and uploaded files
- bundles `contacts.json` inside the extension and can append Key Person entries directly from local contact search
- Quick popup as a quick execution option
- previews the detected form and current stored manifest summary in the popup
- hard-blocks autofill when the loaded manifest form does not match the detected Grants.gov form
- fills the current form without clicking Grants.gov Save
- uploads supported attachments from clientside files stored by the extension



This project is still in development. Double check any automated inputs before saving. 

## Known Constraints

- Budgets currently do not enter dates for project periods
- There will be an unused personnel in each period due that will need to be removed due to the default behavior of the webforms. Use this as an oportunity to confirm the accuracy of the manifest/automate step for each period. 
