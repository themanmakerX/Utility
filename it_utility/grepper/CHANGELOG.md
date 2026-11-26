# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Remove generated cache artifacts, duplicate contribution guidance, and obsolete documentation/screenshots; consolidate accurate usage guidance in the root README.
- Correct package metadata to require Python 3.10+, matching the source syntax, and point the documentation URL to the root README.
- Add improved README, CONTRIBUTING, CODE_OF_CONDUCT, issue/PR templates, and CI workflow.
- Refresh the desktop UI with a colourful indigo/cyan theme, app header, clearer controls, engine badge, and animated search progress.
- Distinguish completed, cancelled, and failed searches in the UI.
- Throttle directory activity messages to reduce Tkinter rendering overhead during large scans.
- Guarantee worker failures release the UI and allow another search.
- Flush pending queues when a paused search is cancelled.
- Validate that the selected search directory exists before starting work.
- Maximize the application on launch and provide a Focus workspace toggle that collapses filters so Results and Details can use the full window.
- Place Results and Details side by side with a draggable 68/32 split so both panels use the full workspace height, and reduce queue batch sizes to preserve responsiveness during high-volume searches.
- Remove the decorative branding banner and tighten outer/search-panel spacing so the workspace starts near the top and leaves more room for Results and Details.
- Compact the Search workspace to three primary rows and move secondary limits, patterns, text-match options, and engine controls into a collapsed Advanced filters accordion.
- Place search actions alongside the active mode fields instead of consuming a separate row.
- Fix directory-only `.gitignore` rules so ignored folders are pruned at their root.
- Cancel workers safely when tabs or the application close, and neutralize scheduled UI callbacks for closed tabs.
- Restore a useful empty state after zero-result searches and prevent placeholder rows from being exported or opened.
- Add the missing result double-click action and make file-extension filtering case-insensitive.
- Prevent mode changes and unsafe result-state resets while a search is running.
- Make worker exception logging independent of cross-thread Tk variable access so error cleanup cannot hang.
- Add explicit idle/running/paused/cancelling button states with stable colours and clearly greyed disabled actions.
- Keep the Start search style stable under the pointer instead of replacing its accent style on hover.
- Replace the dedicated mode-radio row with a compact readonly Mode dropdown beside Choose folder.
- Freeze elapsed time and visible file/match counters while paused, then exclude accumulated pause duration after resume.
- Stop the indeterminate progress animation while paused or cancelling and restart it only on resume.

## [0.1.1]
- Fix GitHub Actions CI to install package before tests.
- Fix PyPI publish workflow to build and upload with twine.
