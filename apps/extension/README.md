# ApplyAI Job Importer

Manifest V3 browser extension for candidate job capture.

The extension does not scrape, bypass authentication, or submit forms. It reads only the active tab URL after the user clicks the extension and opens the authenticated ApplyAI `/import-job` workspace. The existing server-side public-URL safety, robots, redirect, structured-data and canonicalization pipeline performs the actual import.

## Local use

1. Open the browser extensions page and enable developer mode.
2. Load this directory as an unpacked extension.
3. Set the ApplyAI web URL in the popup.
4. Visit a public employer job page and choose **Open in ApplyAI**.

Production store packaging/signing is a deployment/distribution concern; the extension source is self-contained here.
